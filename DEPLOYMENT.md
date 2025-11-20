# Docker Deployment Guide

This guide covers deploying the EU Funding Scraper using Docker with automated scheduling.

## Features

- **Automated Scheduling**: Runs on configurable cron schedule (default: every 6 hours)
- **Open Grants Only**: Option to scrape only open grants
- **Change Detection**: Tracks what changed (new, updated, deleted grants)
- **Detailed Reports**: JSON reports with specific field changes
- **PostgreSQL Integration**: Stores data in PostgreSQL
- **Pinecone Integration**: Syncs to vector database
- **Checkpoint Recovery**: Resumes from last successful state

## Quick Start

### 1. Create Environment File

Create a `.env` file with your credentials:

```bash
# Required: Pinecone
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=ailsa-grants

# Required: OpenAI
OPENAI_API_KEY=your_openai_api_key

# Optional: PostgreSQL password (defaults to 'dev_password')
POSTGRES_PASSWORD=your_secure_password

# Optional: Scheduler configuration
SCRAPER_SCHEDULE=0 */6 * * *  # Every 6 hours
RUN_ON_STARTUP=true
ONLY_OPEN_GRANTS=true  # Set to 'false' to scrape all statuses
```

### 2. Start Services

```bash
# Start all services (PostgreSQL + Scraper with scheduler)
docker-compose up -d

# View logs
docker-compose logs -f scraper

# Stop services
docker-compose down
```

### 3. Manual Runs

To run the scraper manually (one-off):

```bash
# Run incremental update
docker-compose run --rm scraper-manual

# Run with custom mode
docker-compose run --rm -e ONLY_OPEN_GRANTS=false scraper-manual

# Run specific programme
docker-compose run --rm scraper-manual python -c "from scraper.pipelines.horizon_europe_open import run; run()"
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SCRAPER_SCHEDULE` | Cron expression for schedule | `0 */6 * * *` (every 6 hours) |
| `RUN_ON_STARTUP` | Run scraper immediately on startup | `true` |
| `ONLY_OPEN_GRANTS` | Only scrape open grants | `true` |
| `SCRAPER_MODE` | Mode: `incremental` or `full` | `incremental` |
| `DATABASE_URL` | PostgreSQL connection string | Auto-configured |
| `PINECONE_API_KEY` | Pinecone API key | Required |
| `PINECONE_INDEX_NAME` | Pinecone index name | `ailsa-grants` |
| `OPENAI_API_KEY` | OpenAI API key | Required |

### Cron Schedule Examples

```bash
# Every 6 hours
SCRAPER_SCHEDULE=0 */6 * * *

# Daily at 2 AM
SCRAPER_SCHEDULE=0 2 * * *

# Every 12 hours
SCRAPER_SCHEDULE=0 */12 * * *

# Every Monday at 9 AM
SCRAPER_SCHEDULE=0 9 * * 1

# Every 4 hours during business hours (9 AM - 5 PM)
SCRAPER_SCHEDULE=0 9-17/4 * * *
```

## Data Persistence

### Volumes

- `postgres_data`: PostgreSQL database files
- `./data`: Scraped grant data and reports
- `./logs`: Application logs

### Data Directory Structure

```
data/
├── horizon_europe/
│   ├── normalized.json           # Current normalized grants
│   ├── checkpoint.json            # Recovery checkpoint
│   ├── raw_index.json             # Raw API responses
│   ├── update_report_*.json       # Change reports
│   └── validation_report.json     # Data validation report
└── digital_europe/
    └── (same structure)
```

## Change Detection Reports

Update reports include detailed change information:

```json
{
  "timestamp": "2025-11-20T12:00:00Z",
  "programme": "Horizon Europe",
  "changes": {
    "new": 5,
    "updated": 3,
    "deleted": 2
  },
  "new_grants": [
    {
      "change_type": "new",
      "title": "New Grant Title",
      "status": "Open",
      "close_date": "2025-12-31",
      "url": "https://..."
    }
  ],
  "updated_grants": [
    {
      "change_type": "updated",
      "title": "Updated Grant",
      "changes": {
        "close_date": {
          "old": "2025-11-30",
          "new": "2025-12-15"
        },
        "status": {
          "old": "Forthcoming",
          "new": "Open"
        }
      }
    }
  ],
  "deleted_grants": [
    {
      "change_type": "deleted",
      "title": "Closed Grant",
      "was_status": "Open"
    }
  ]
}
```

## Monitoring

### Check Scraper Status

```bash
# View real-time logs
docker-compose logs -f scraper

# Check last run
docker-compose exec scraper cat logs/scheduler.log

# View update reports
ls -lh data/*/update_report_*.json
```

### Health Checks

```bash
# Check if services are running
docker-compose ps

# Check PostgreSQL
docker-compose exec postgres psql -U postgres ailsa -c "SELECT COUNT(*) FROM grants;"

# Test database connection
docker-compose exec scraper python test_connections.py
```

## Troubleshooting

### Scraper Not Running

```bash
# Check logs for errors
docker-compose logs scraper

# Restart scraper
docker-compose restart scraper

# Rebuild if code changed
docker-compose up -d --build scraper
```

### Database Issues

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres ailsa

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
```

### Reset Checkpoints

```bash
# Remove checkpoints to force full rescrape
rm data/*/checkpoint.json
docker-compose restart scraper
```

## Production Deployment

### Security Recommendations

1. **Use strong passwords**: Set `POSTGRES_PASSWORD` to a strong random value
2. **Secure .env file**: Never commit `.env` to version control
3. **Network isolation**: Use Docker networks to isolate services
4. **Regular backups**: Backup `postgres_data` volume and `data/` directory

### Backup Strategy

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U postgres ailsa > backup_$(date +%Y%m%d).sql

# Backup data directory
tar -czf data_backup_$(date +%Y%m%d).tar.gz data/

# Restore PostgreSQL
docker-compose exec -T postgres psql -U postgres ailsa < backup_20251120.sql
```

### Scaling Considerations

- **CPU**: Scraper is I/O bound (API calls), 1-2 CPUs sufficient
- **Memory**: 512MB-1GB RAM per scraper instance
- **Storage**: ~1GB for database, ~500MB for data files
- **Network**: ~10-50 MB per scrape run

## Advanced Usage

### Running Specific Programmes

```bash
# Horizon Europe only (open grants)
docker-compose run --rm scraper python scraper/pipelines/horizon_europe_open.py

# Digital Europe only (all statuses)
docker-compose run --rm scraper python scraper/pipelines/digital_europe.py
```

### Custom Scraper Script

Create `custom_scrape.py`:

```python
from scraper.pipelines.horizon_europe_open import run as horizon_run
from scraper.pipelines.digital_europe_open import run as digital_run

# Run with limits for testing
horizon_run(limit=10)
digital_run(limit=10)
```

Run it:

```bash
docker-compose run --rm scraper python custom_scrape.py
```

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Review reports: `data/*/update_report_*.json`
- Validate data: `data/*/validation_report.json`
