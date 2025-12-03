#!/bin/bash
# Wrapper script for cron job execution

# Set paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Setup logging
LOG_DIR="$SCRIPT_DIR/outputs/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Activate virtual environment if you're using one
# source venv/bin/activate

echo "========================================" >> "$LOG_DIR/cron.log"
echo "Starting scraper run at $(date)" >> "$LOG_DIR/cron.log"
echo "========================================" >> "$LOG_DIR/cron.log"

# Run Horizon Europe scraper
echo "Running Horizon Europe scraper..." >> "$LOG_DIR/cron.log"
python -m scraper.pipelines.horizon_europe >> "$LOG_DIR/horizon_$TIMESTAMP.log" 2>&1
HORIZON_EXIT=$?

# Run Digital Europe scraper
echo "Running Digital Europe scraper..." >> "$LOG_DIR/cron.log"
python -m scraper.pipelines.digital_europe >> "$LOG_DIR/digital_$TIMESTAMP.log" 2>&1
DIGITAL_EXIT=$?

# Log results
echo "Horizon Europe exit code: $HORIZON_EXIT" >> "$LOG_DIR/cron.log"
echo "Digital Europe exit code: $DIGITAL_EXIT" >> "$LOG_DIR/cron.log"
echo "Completed at $(date)" >> "$LOG_DIR/cron.log"

# Optional: Send notification on failure
if [ $HORIZON_EXIT -ne 0 ] || [ $DIGITAL_EXIT -ne 0 ]; then
    echo "ERROR: One or more scrapers failed" >> "$LOG_DIR/cron.log"
    # Add notification here (email, Slack, etc.)
fi

# Optional: Run validation
python scripts/validate_run.py all >> "$LOG_DIR/validation_$TIMESTAMP.log" 2>&1

echo "========================================" >> "$LOG_DIR/cron.log"
echo "" >> "$LOG_DIR/cron.log"
