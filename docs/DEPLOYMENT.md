# Docker Deployment Guide

This guide covers deploying the EU Funding Scraper using Docker with automated scheduling.

## Features

- **Automated Scheduling**: Runs on configurable cron schedule (default: every 6 hours)
- **Open Grants Only**: Option to scrape only open grants
- **Change Detection**: Tracks what changed (new, updated, deleted grants)
- **Detailed Reports**: JSON reports with specific field changes
- **MongoDB Integration**: Stores data in MongoDB (local or Atlas)
- **Pinecone Integration**: Syncs to vector database
- **Checkpoint Recovery**: Resumes from last successful state

## Quick Start

### 1. Create Environment File

Create a `.env` file with your credentials:

```bash
# Required: MongoDB
MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/
MONGO_DB_NAME=ailsa_grants

# Required: Pinecone
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=ailsa-grants

# Required: OpenAI
OPENAI_API_KEY=your_openai_api_key

# Optional: Scheduler configuration
SCRAPER_SCHEDULE=0 */6 * * *  # Every 6 hours
RUN_ON_STARTUP=true
ONLY_OPEN_GRANTS=true  # Set to 'false' to scrape all statuses
```

### 2. Start Services

```bash
# Start scraper service
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
| `MONGO_URI` | MongoDB connection string | Required |
| `MONGO_DB_NAME` | MongoDB database name | `ailsa_grants` |
| `SCRAPER_SCHEDULE` | Cron expression for schedule | `0 */6 * * *` (every 6 hours) |
| `RUN_ON_STARTUP` | Run scraper immediately on startup | `true` |
| `ONLY_OPEN_GRANTS` | Only scrape open grants | `true` |
| `SCRAPER_MODE` | Mode: `incremental` or `full` | `incremental` |
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

## MongoDB Setup

### Option 1: MongoDB Atlas (Recommended for Production)

1. Create a free cluster at [MongoDB Atlas](https://www.mongodb.com/atlas)
2. Create a database user with read/write permissions
3. Whitelist your IP address (or allow all IPs for Docker)
4. Get your connection string and add it to `.env`:

```bash
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
```

### Option 2: Local MongoDB with Docker

Add MongoDB to your docker-compose.yml:

```yaml
services:
  mongodb:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: your_password

  scraper:
    # ... your scraper config
    depends_on:
      - mongodb
    environment:
      MONGO_URI: mongodb://admin:your_password@mongodb:27017/

volumes:
  mongodb_data:
```

### Creating Indexes

For optimal query performance, create indexes on common query fields:

```javascript
// Connect to MongoDB
mongosh "$MONGO_URI"

// Switch to database
use ailsa_grants

// Create indexes
db.grants.createIndex({ "grant_id": 1 }, { unique: true })
db.grants.createIndex({ "source": 1 })
db.grants.createIndex({ "status": 1 })
db.grants.createIndex({ "is_active": 1 })
db.grants.createIndex({ "closes_at": 1 })
db.grants.createIndex({ "programme": 1 })
db.grants.createIndex({ "tags": 1 })
db.grants.createIndex({ "sectors": 1 })
db.grants.createIndex({ "source": 1, "status": 1 })
db.grants.createIndex({ "title": "text", "description": "text" })
```

## Data Persistence

### Volumes

- `mongodb_data`: MongoDB database files (if running locally)
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

# Check MongoDB connection
mongosh "$MONGO_URI" --eval 'db.grants.countDocuments({})'

# Test database connection from container
docker-compose exec scraper python test_connections.py
```

### Database Statistics

```bash
# Get grant counts by source and status
mongosh "$MONGO_URI" --eval '
use ailsa_grants;
db.grants.aggregate([
  {$group: {_id: {source: "$source", status: "$status"}, count: {$sum: 1}}},
  {$sort: {"_id.source": 1, "_id.status": 1}}
])
'

# Get open grants
mongosh "$MONGO_URI" --eval '
use ailsa_grants;
db.grants.find({is_active: true}, {title: 1, closes_at: 1}).sort({closes_at: 1}).limit(10)
'
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

### MongoDB Connection Issues

```bash
# Test connection string
mongosh "$MONGO_URI" --eval 'db.runCommand({ping: 1})'

# Check if URI is correctly formatted
# Should be: mongodb+srv://user:pass@cluster.mongodb.net/

# For Atlas: ensure IP is whitelisted
# For local: ensure MongoDB is running
```

### Reset Checkpoints

```bash
# Remove checkpoints to force full rescrape
rm data/*/checkpoint.json
docker-compose restart scraper
```

## Production Deployment

### Security Recommendations

1. **Use MongoDB Atlas**: Managed service with built-in security
2. **Secure connection strings**: Use environment variables, never commit credentials
3. **Network isolation**: Use Docker networks to isolate services
4. **Enable authentication**: Always use authenticated connections
5. **Regular backups**: Enable automated backups in Atlas or run manual backups

### Backup Strategy

```bash
# Export grants collection
mongodump --uri="$MONGO_URI" --db=ailsa_grants --collection=grants --out=./backup_$(date +%Y%m%d)

# Backup data directory
tar -czf data_backup_$(date +%Y%m%d).tar.gz data/

# Restore from backup
mongorestore --uri="$MONGO_URI" --db=ailsa_grants ./backup_20251120/ailsa_grants/
```

### Scaling Considerations

- **CPU**: Scraper is I/O bound (API calls), 1-2 CPUs sufficient
- **Memory**: 512MB-1GB RAM per scraper instance
- **Storage**: ~100MB for MongoDB (grows with data), ~500MB for data files
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

### Query Examples

```javascript
// Find all open grants closing in the next 30 days
db.grants.find({
  is_active: true,
  closes_at: {
    $gte: new Date(),
    $lte: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
  }
}).sort({closes_at: 1})

// Find grants by programme
db.grants.find({
  programme: "HORIZON-CL5"
})

// Find grants with specific tags
db.grants.find({
  tags: {$in: ["Climate", "Digital"]}
})

// Full-text search
db.grants.find({
  $text: {$search: "artificial intelligence"}
})

// Aggregation: count by programme
db.grants.aggregate([
  {$match: {is_active: true}},
  {$group: {_id: "$programme", count: {$sum: 1}}},
  {$sort: {count: -1}}
])
```

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Review reports: `data/*/update_report_*.json`
- Validate data: `data/*/validation_report.json`
