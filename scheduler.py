#!/usr/bin/env python3
"""
Scheduler for automated grant scraping.
Runs on a configurable schedule using cron syntax.
"""

import os
import time
import logging
from datetime import datetime
from croniter import croniter
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('outputs/logs/scheduler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def run_scraper():
    """Execute the incremental scraper"""
    logger.info("="*70)
    logger.info("Starting scheduled scrape run")
    logger.info("="*70)

    try:
        # Run the incremental update script
        result = subprocess.run(
            [sys.executable, 'scripts/run_incremental_update.py'],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )

        if result.returncode == 0:
            logger.info("Scrape completed successfully")
            logger.info(result.stdout)
        else:
            logger.error(f"Scrape failed with return code {result.returncode}")
            logger.error(result.stderr)

    except subprocess.TimeoutExpired:
        logger.error("Scrape timed out after 1 hour")
    except Exception as e:
        logger.error(f"Scrape failed with exception: {e}", exc_info=True)

    logger.info("="*70)


def main():
    """Main scheduler loop"""
    # Get schedule from environment (cron format)
    schedule = os.environ.get('SCRAPER_SCHEDULE', '0 */6 * * *')  # Default: every 6 hours
    run_on_startup = os.environ.get('RUN_ON_STARTUP', 'true').lower() == 'true'

    logger.info(f"Scheduler starting with cron schedule: {schedule}")
    logger.info(f"Run on startup: {run_on_startup}")

    # Validate cron expression
    try:
        cron = croniter(schedule, datetime.now())
    except Exception as e:
        logger.error(f"Invalid cron expression '{schedule}': {e}")
        sys.exit(1)

    # Run immediately on startup if configured
    if run_on_startup:
        logger.info("Running initial scrape on startup...")
        run_scraper()

    # Main scheduling loop
    while True:
        try:
            # Calculate next run time
            cron = croniter(schedule, datetime.now())
            next_run = cron.get_next(datetime)

            # Calculate sleep time
            sleep_seconds = (next_run - datetime.now()).total_seconds()

            logger.info(f"Next run scheduled for: {next_run.isoformat()}")
            logger.info(f"Sleeping for {sleep_seconds:.0f} seconds ({sleep_seconds/3600:.2f} hours)")

            # Sleep until next run
            time.sleep(max(sleep_seconds, 0))

            # Run scraper
            run_scraper()

        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)
            # Sleep for 5 minutes before retrying
            time.sleep(300)


if __name__ == "__main__":
    main()
