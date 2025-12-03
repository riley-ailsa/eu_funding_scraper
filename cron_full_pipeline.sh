#!/bin/bash
# Complete automated pipeline: Scrape → Ingest to Production
# This script is designed to run on a schedule (daily/weekly)

set -e  # Exit on any error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Setup logging
LOG_DIR="$SCRIPT_DIR/outputs/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOGFILE="$LOG_DIR/pipeline_$TIMESTAMP.log"

# Load environment variables
source .env 2>/dev/null || echo "Warning: .env not found"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOGFILE"
}

log "=========================================="
log "EU FUNDING PIPELINE STARTING"
log "=========================================="

# Step 1: Scrape Horizon Europe
log "📡 Step 1/4: Scraping Horizon Europe..."
python3 -m scraper.pipelines.horizon_europe >> "$LOGFILE" 2>&1
HORIZON_EXIT=$?

if [ $HORIZON_EXIT -eq 0 ]; then
    log "✅ Horizon Europe scraping completed"
else
    log "❌ Horizon Europe scraping failed (exit code: $HORIZON_EXIT)"
fi

# Step 2: Scrape Digital Europe
log "📡 Step 2/4: Scraping Digital Europe..."
python3 -m scraper.pipelines.digital_europe >> "$LOGFILE" 2>&1
DIGITAL_EXIT=$?

if [ $DIGITAL_EXIT -eq 0 ]; then
    log "✅ Digital Europe scraping completed"
else
    log "❌ Digital Europe scraping failed (exit code: $DIGITAL_EXIT)"
fi

# Step 3: Ingest to Production (MongoDB + Pinecone)
log "💾 Step 3/4: Ingesting to production database..."
python3 run_pipeline.py >> "$LOGFILE" 2>&1
INGEST_EXIT=$?

if [ $INGEST_EXIT -eq 0 ]; then
    log "✅ Ingestion completed successfully"
else
    log "❌ Ingestion failed (exit code: $INGEST_EXIT)"
fi

# Step 4: Summary
log "=========================================="
log "PIPELINE COMPLETE"
log "=========================================="
log "Results:"
log "  Horizon Europe: $([ $HORIZON_EXIT -eq 0 ] && echo '✅ Success' || echo '❌ Failed')"
log "  Digital Europe: $([ $DIGITAL_EXIT -eq 0 ] && echo '✅ Success' || echo '❌ Failed')"
log "  Ingestion:      $([ $INGEST_EXIT -eq 0 ] && echo '✅ Success' || echo '❌ Failed')"

# Overall exit code (fail if any step failed)
if [ $HORIZON_EXIT -eq 0 ] && [ $DIGITAL_EXIT -eq 0 ] && [ $INGEST_EXIT -eq 0 ]; then
    log "🎉 All steps completed successfully"
    echo "success" > "$LOG_DIR/last_run_status"
    exit 0
else
    log "⚠️  Pipeline completed with errors"
    echo "failed" > "$LOG_DIR/last_run_status"

    # Optional: Send alert
    # Uncomment to enable Slack notifications:
    # SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    # curl -X POST -H 'Content-type: application/json' \
    #   --data "{\"text\":\"⚠️ EU Funding Pipeline failed. Check logs: $LOGFILE\"}" \
    #   "$SLACK_WEBHOOK_URL"

    exit 1
fi

# Cleanup old logs (keep last 30 days)
find "$LOG_DIR" -name "pipeline_*.log" -mtime +30 -delete
find "$LOG_DIR" -name "horizon_*.log" -mtime +30 -delete
find "$LOG_DIR" -name "digital_*.log" -mtime +30 -delete
