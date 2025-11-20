#!/bin/bash
# Production cron script with notifications

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Run incremental update
python run_incremental_update.py >> "$LOG_DIR/cron_$TIMESTAMP.log" 2>&1
EXIT_CODE=$?

# Check if successful
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Scraper completed successfully at $(date)" >> "$LOG_DIR/cron.log"

    # Optional: Sync to Ask Ailsa database
    # python sync_to_ailsa.py >> "$LOG_DIR/sync_$TIMESTAMP.log" 2>&1

else
    echo "❌ Scraper failed with exit code $EXIT_CODE at $(date)" >> "$LOG_DIR/cron.log"

    # Send alert (example using curl to Slack webhook)
    # Uncomment and add your Slack webhook URL:
    # SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    # curl -X POST -H 'Content-type: application/json' \
    #   --data "{\"text\":\"⚠️ EU Funding Scraper failed with exit code $EXIT_CODE\"}" \
    #   "$SLACK_WEBHOOK_URL"
fi

# Cleanup old logs (keep last 30 days)
find "$LOG_DIR" -name "*.log" -mtime +30 -delete

# Cleanup old update reports (keep last 90 days)
find "$SCRIPT_DIR/data" -name "update_report_*.json" -mtime +90 -delete
