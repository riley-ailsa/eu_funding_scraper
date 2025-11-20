# Cron Job Setup Guide

This guide shows how to set up automated, scheduled scraping of EU funding opportunities.

## Quick Start

### 1. Make Scripts Executable

```bash
chmod +x run_scrapers.sh
chmod +x cron_scraper.sh
chmod +x run_incremental_update.py
chmod +x sync_to_ailsa.py
```

### 2. Test the Scripts

```bash
# Test basic wrapper script
./run_scrapers.sh

# Test incremental update
python run_incremental_update.py

# Test cron script
./cron_scraper.sh
```

### 3. Set Up Cron Job

Edit your crontab:
```bash
crontab -e
```

Add one of these lines depending on your needs:

```bash
# Option 1: Daily at 2 AM (recommended)
0 2 * * * cd /Users/rileycoleman/EU\ Funding\ Scraper && ./cron_scraper.sh

# Option 2: Twice daily (8 AM and 8 PM)
0 8,20 * * * cd /Users/rileycoleman/EU\ Funding\ Scraper && ./cron_scraper.sh

# Option 3: Weekly on Mondays at 3 AM
0 3 * * 1 cd /Users/rileycoleman/EU\ Funding\ Scraper && ./cron_scraper.sh

# Option 4: Every 6 hours
0 */6 * * * cd /Users/rileycoleman/EU\ Funding\ Scraper && ./cron_scraper.sh
```

## Scripts Overview

### `run_scrapers.sh`
Basic wrapper script that:
- Runs both Horizon Europe and Digital Europe scrapers
- Logs output to timestamped files
- Runs validation after completion
- Records exit codes for monitoring

### `run_incremental_update.py`
Smart incremental scraper that:
- Compares current grants with previously scraped data
- Detects new, updated, and deleted grants
- Generates detailed update reports
- Uses checkpoint recovery for efficiency

### `cron_scraper.sh`
Production-ready cron script that:
- Runs incremental updates
- Logs success/failure
- Sends alerts on failure (optional)
- Cleans up old logs automatically

### `sync_to_ailsa.py`
Vector database sync template that:
- Prepares grant text for embedding
- Formats metadata for filtering
- Syncs to your vector database (ChromaDB, Pinecone, etc.)
- Supports incremental syncing

## Cron Schedule Examples

### Cron Syntax Reminder
```
* * * * * command
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, Sunday = 0 or 7)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

### Common Schedules

```bash
# Every day at 2:00 AM
0 2 * * * /path/to/cron_scraper.sh

# Every Monday at 3:00 AM
0 3 * * 1 /path/to/cron_scraper.sh

# Every 6 hours
0 */6 * * * /path/to/cron_scraper.sh

# Twice a day (8 AM and 8 PM)
0 8,20 * * * /path/to/cron_scraper.sh

# Every weekday at 9 AM
0 9 * * 1-5 /path/to/cron_scraper.sh
```

## Logging

Logs are saved to the `logs/` directory:

```
logs/
├── cron.log                    # Main cron activity log
├── cron_20251119_140000.log    # Timestamped run logs
├── horizon_20251119_140000.log # Horizon Europe specific logs
├── digital_20251119_140000.log # Digital Europe specific logs
└── validation_20251119_140000.log # Validation logs
```

View recent cron activity:
```bash
tail -f logs/cron.log
```

View most recent run:
```bash
ls -t logs/cron_*.log | head -1 | xargs cat
```

## Update Reports

After each run, update reports are saved:

```
data/horizon_europe/update_report_20251119_140000.json
data/digital_europe/update_report_20251119_140000.json
```

Example report:
```json
{
  "timestamp": "2025-11-19T14:00:00.000000+00:00",
  "programme": "Horizon Europe",
  "previous_count": 3424,
  "current_count": 3428,
  "changes": {
    "new": 4,
    "updated": 12,
    "deleted": 0
  },
  "new_grant_ids": ["horizon_europe:12345COMPETITIVE_CALLen", "..."],
  "updated_grant_ids": ["horizon_europe:11234COMPETITIVE_CALLen", "..."]
}
```

## Notifications

### Slack Notifications

1. Create a Slack webhook URL: https://api.slack.com/messaging/webhooks

2. Edit `cron_scraper.sh` and update the Slack webhook section:

```bash
# Uncomment and add your webhook URL
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
curl -X POST -H 'Content-type: application/json' \
  --data "{\"text\":\"⚠️ EU Funding Scraper failed with exit code $EXIT_CODE\"}" \
  "$SLACK_WEBHOOK_URL"
```

### Email Notifications

Add to `cron_scraper.sh`:

```bash
if [ $EXIT_CODE -ne 0 ]; then
    echo "Scraper failed" | mail -s "EU Scraper Alert" your.email@example.com
fi
```

## Monitoring

### Check if Cron Job is Running

```bash
# View current crontab
crontab -l

# Check cron is running (macOS)
sudo launchctl list | grep cron

# Check recent cron activity
grep CRON /var/log/system.log | tail -20
```

### Manual Test Run

```bash
# Test the exact command cron will run
cd /Users/rileycoleman/EU\ Funding\ Scraper && ./cron_scraper.sh
```

## Integration with Ask Ailsa

After scraping, sync to your vector database:

1. **Update `sync_to_ailsa.py`** with your actual vector DB code:
   - ChromaDB example included
   - Adapt to Pinecone, Weaviate, or your choice

2. **Enable in `cron_scraper.sh`**:
   ```bash
   # Uncomment this line:
   python sync_to_ailsa.py >> "$LOG_DIR/sync_$TIMESTAMP.log" 2>&1
   ```

3. **For incremental syncing**:
   ```bash
   python sync_to_ailsa.py --incremental
   ```

## Checkpoint Recovery

The scrapers use checkpoint recovery, so:

✅ **Interrupted cron jobs can resume** from where they left off
✅ **Failed grant fetches are tracked** and can be retried
✅ **Progress is never lost** even if the script crashes

This makes frequent cron runs very efficient - if nothing changed, the scraper completes in seconds.

## Cleanup

Logs and reports are automatically cleaned up:
- **Logs**: Kept for 30 days
- **Update reports**: Kept for 90 days

Adjust retention in `cron_scraper.sh`:
```bash
# Change 30 to desired number of days
find "$LOG_DIR" -name "*.log" -mtime +30 -delete
```

## Troubleshooting

### Cron Job Not Running

1. **Check crontab syntax**:
   ```bash
   crontab -l
   ```

2. **Check script permissions**:
   ```bash
   ls -la *.sh
   # Should show -rwxr-xr-x (executable)
   ```

3. **Test manually**:
   ```bash
   ./cron_scraper.sh
   ```

4. **Check cron logs**:
   ```bash
   # macOS
   log show --predicate 'process == "cron"' --last 1h

   # Linux
   grep CRON /var/log/syslog | tail -20
   ```

### Script Fails in Cron but Works Manually

**Common issue**: Python not in PATH for cron

Fix: Use absolute path to Python:
```bash
# Find your Python path
which python

# Update cron_scraper.sh to use absolute path
/usr/local/bin/python run_incremental_update.py
```

### No New Grants Detected

This is normal! If you run frequently (e.g., daily), most runs will find 0-5 new grants.

Check the update report to see change statistics:
```bash
cat data/horizon_europe/update_report_*.json | tail -1
```

## Recommended Setup

For production use with Ask Ailsa:

```bash
# Add to crontab:
0 2 * * * cd /Users/rileycoleman/EU\ Funding\ Scraper && ./cron_scraper.sh

# This will:
# 1. Run incremental scrape at 2 AM daily
# 2. Detect new/updated grants
# 3. Sync to Ask Ailsa vector DB
# 4. Clean up old logs
# 5. Send alerts on failure
```

**Benefits:**
- ✅ Always up-to-date grant data
- ✅ Minimal bandwidth usage (checkpoint recovery)
- ✅ Complete audit trail
- ✅ Automatic failure alerts
- ✅ Zero maintenance required

## Questions?

- **How often should I run this?** Daily at 2 AM is recommended
- **Does it use a lot of bandwidth?** No, checkpoint recovery makes it efficient
- **What if it fails?** It will resume from the checkpoint on next run
- **Can I run multiple instances?** No, use file locking if needed
- **Does it affect the website?** No, we use proper delays and User-Agent headers
