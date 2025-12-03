# EU Funding Scraper & Data Pipeline

**Production-ready system for scraping, processing, and serving EU grant opportunities from Horizon Europe and Digital Europe Programmes.**

[![Status](https://img.shields.io/badge/status-production-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.9+-blue)]()
[![Database](https://img.shields.io/badge/database-MongoDB-47A248)]()
[![Vector DB](https://img.shields.io/badge/vector-Pinecone-orange)]()

---

## Overview

This system provides end-to-end automation for EU grant discovery:

1. **Scrapes** grant data from EU Funding & Tenders Portal
2. **Extracts** 15+ metadata fields from raw API responses
3. **Validates** dates, maps status codes, cleans HTML
4. **Stores** structured data in MongoDB
5. **Embeds** full grant descriptions for semantic search in Pinecone
6. **Schedules** automated updates via cron

**Data Coverage:** 3,734 grants (3,425 Horizon Europe + 309 Digital Europe)

---

## Quick Start

### Prerequisites

- Python 3.9+
- MongoDB 6.0+ (local or Atlas)
- Pinecone account
- OpenAI API key

### Installation

```bash
# 1. Clone repository
git clone <your-repo>
cd "EU Funding Scraper"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys and MongoDB URI
```

### First Run

```bash
# 1. Run complete pipeline
python3 -m scraper.pipelines.horizon_europe    # Scrape Horizon Europe
python3 -m scraper.pipelines.digital_europe    # Scrape Digital Europe
python3 ingest_to_production.py                # Ingest to MongoDB + Pinecone

# 2. Verify results
python3 validate_run.py
```

---

## Data Schema

### MongoDB Document Schema

```python
{
    "grant_id": "horizon_europe_XXXX",  # Unique identifier
    "source": "horizon_europe",          # horizon_europe or digital_europe
    "external_id": "HORIZON-CL5-...",   # Official EU identifier

    # Core metadata
    "title": "Grant title",
    "call_title": "Full call name",
    "url": "https://...",
    "description": "Full description text",
    "description_summary": "First 500 chars",

    # Status & dates
    "status": "Open",                    # Open/Closed/Forthcoming
    "is_active": true,
    "opens_at": "2025-01-01T00:00:00Z",
    "closes_at": "2025-06-30T17:00:00Z",
    "deadline_model": "single-stage",

    # Funding (EUR with GBP conversion)
    "total_fund_gbp": 850000,
    "total_fund_eur": 1000000,
    "budget_min": 1000000,
    "budget_max": 1000000,
    "project_funding_min": 1000000,
    "project_funding_max": 1000000,
    "competition_type": "grant",

    # Programme info
    "programme": "HORIZON-CL5",
    "action_type": "HORIZON-RIA",
    "duration": "36 months",

    # Classification
    "tags": ["Climate", "Digital"],
    "sectors": ["Climate", "Environment"],

    # Additional EU-specific fields
    "further_information": "...",
    "application_info": "...",

    # Timestamps
    "scraped_at": ISODate("..."),
    "updated_at": ISODate("..."),
    "created_at": ISODate("...")
}
```

### Field Coverage

| Field | Type | Coverage | Description |
|-------|------|----------|-------------|
| `grant_id` | string | 100% | Unique identifier |
| `source` | string | 100% | horizon_europe or digital_europe |
| `title` | text | 100% | Grant title |
| `external_id` | string | 100% | Official EU ID (e.g., HORIZON-CL5-...) |
| `programme` | string | 100% | Programme code (HORIZON-CL5, HORIZON-EIT, etc.) |
| `status` | string | 100% | Open / Closed / Forthcoming |
| `is_active` | boolean | 100% | True if status is Open |
| `opens_at` | datetime | High | Application opening date |
| `closes_at` | datetime | High | Deadline |
| `deadline_model` | string | 99% | single-stage or multiple cut-off |
| `budget_min` | integer | 17% | Minimum budget (EUR) |
| `budget_max` | integer | 17% | Maximum budget (EUR) |
| `total_fund_gbp` | integer | 17% | Budget converted to GBP |
| `duration` | string | 13% | Project duration |
| `tags` | array | 64% | Cross-cutting priorities/themes |
| `sectors` | array | 100% | Derived sector categories |
| `action_type` | string | 100% | Grant type classification |
| `description_summary` | text | High | First 500 chars |
| `call_title` | text | 100% | Full call name |
| `further_information` | text | Variable | Additional context (up to 1000 chars) |
| `application_info` | text | Variable | How to apply (up to 1000 chars) |
| `url` | text | 100% | Link to grant page |

### Database Architecture

```
┌─────────────────────┐       ┌──────────────────────┐
│      MongoDB        │       │      Pinecone        │
│  (Document Store)   │       │  (Vector Embeddings) │
├─────────────────────┤       ├──────────────────────┤
│ • Full documents    │       │ • Full descriptions  │
│ • Flexible schema   │       │ • Semantic search    │
│ • Rich queries      │       │ • Similarity ranking │
│ • Aggregations      │       │ • Filterable metadata│
└─────────────────────┘       └──────────────────────┘
```

---

## Automated Scheduling

### Setup Cron Job

To run the complete pipeline daily at 2 AM:

```bash
# Make script executable
chmod +x cron_full_pipeline.sh

# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * /path/to/EU\ Funding\ Scraper/cron_full_pipeline.sh

# Or for weekly updates (Sundays at 2 AM)
0 2 * * 0 /path/to/EU\ Funding\ Scraper/cron_full_pipeline.sh
```

The pipeline script:
- Scrapes both funding sources
- Ingests to MongoDB + Pinecone
- Logs all operations
- Sends alerts on failure (if configured)
- Cleans up old logs

---

## Project Structure

```
EU Funding Scraper/
├── README.md                      # This file
├── DEPLOYMENT.md                  # Docker deployment guide
├── .env                           # Configuration (API keys, MongoDB URI)
├── requirements.txt               # Python dependencies
│
├── scraper/                       # Scraping engine
│   ├── base.py                    # Base pipeline with checkpointing
│   ├── eu_common.py               # EU portal shared logic
│   └── pipelines/
│       ├── horizon_europe.py      # Horizon Europe scraper
│       └── digital_europe.py      # Digital Europe scraper
│
├── ingest_to_production.py        # Main ingestion script (MongoDB + Pinecone)
├── validate_run.py                # Data validation
│
├── cron_full_pipeline.sh          # Automated pipeline (scrape + ingest)
├── run_scrapers.sh                # Manual scraper runner
│
├── data/                          # Scraped data output
│   ├── horizon_europe/
│   │   ├── normalized.json        # Processed grant data
│   │   ├── raw_index.json         # Raw API responses
│   │   ├── checkpoint.json        # Resume state
│   │   └── audit_log.jsonl        # Operation log
│   └── digital_europe/
│       └── ... (same structure)
│
├── logs/                          # Cron job logs
│   └── pipeline_YYYYMMDD_HHMMSS.log
│
└── docs/                          # Additional documentation
    ├── EXTRACTION_SUMMARY.md      # Field extraction details
    ├── CRON_SETUP.md              # Scheduling guide
    └── DUPLICATE_IDS_EXPLAINED.md # Data quality notes
```

---

## Key Features

### 1. Robust Scraping
- **Checkpoint Recovery**: Resumes from interruption point
- **Exponential Backoff**: Automatic retry on failures
- **Rate Limiting**: Respects API limits
- **Audit Logging**: Complete operation trail

### 2. Data Validation
- **Date Validation**: Auto-fixes reversed open/close dates
- **Status Mapping**: Converts API codes to readable strings
  - `31094501` → Forthcoming
  - `31094502` → Open
  - `31094503` → Closed
- **HTML Cleaning**: Removes tags from descriptions
- **Type Safety**: Handles missing/malformed fields

### 3. Semantic Search
- **Full-Text Embeddings**: Entire grant descriptions (up to 4,000 chars)
- **OpenAI Embeddings**: text-embedding-3-small model
- **Rich Metadata**: 10+ filterable fields in Pinecone
- **Hybrid Search**: Combine vector similarity with metadata filters

### 4. Production Ready
- **Automated Updates**: Cron-based scheduling
- **Monitoring**: Status tracking and alerts
- **Log Rotation**: Auto-cleanup of old logs (30 days)
- **Error Handling**: Graceful degradation, no data loss

---

## Testing

```bash
# Quick smoke test (5 grants)
python3 test_5_grants.py

# Sample test (20 grants)
python3 test_20_grants.py

# Validate data quality
python3 validate_run.py horizon_europe
python3 validate_run.py digital_europe
python3 validate_run.py all
```

---

## Current Data

**Last Updated:** [Run pipeline to populate]

| Source | Grants | Open | Closed | Forthcoming |
|--------|--------|------|--------|-------------|
| Horizon Europe | 3,425 | 154 | 3,265 | 6 |
| Digital Europe | 309 | TBD | TBD | TBD |
| **Total** | **3,734** | - | - | - |

---

## Configuration

### Environment Variables (.env)

```bash
# MongoDB
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DB_NAME=ailsa_grants

# Pinecone
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=ailsa-grants

# OpenAI
OPENAI_API_KEY=sk-proj-...
```

### Status Filters

By default, scrapers fetch:
- Open grants (currently accepting applications)
- Closed grants (recently closed for reference)
- Forthcoming grants (upcoming opportunities)

To fetch **all** grants including archived, modify status filters in pipeline files.

---

## Documentation

- [Deployment Guide](DEPLOYMENT.md) - Docker deployment instructions
- [Extraction Summary](docs/EXTRACTION_SUMMARY.md) - Detailed field extraction
- [Cron Setup Guide](docs/CRON_SETUP.md) - Scheduling instructions
- [Data Quality Notes](docs/DUPLICATE_IDS_EXPLAINED.md) - Known issues

---

## Troubleshooting

### Scraper Issues
```bash
# Check checkpoint state
cat data/horizon_europe/checkpoint.json

# Review audit log
tail -f data/horizon_europe/audit_log.jsonl

# Clear checkpoint and restart
rm data/horizon_europe/checkpoint.json
python3 -m scraper.pipelines.horizon_europe
```

### MongoDB Issues
```bash
# Test connection
mongosh "$MONGO_URI" --eval 'db.grants.countDocuments({})'

# Check counts by source
mongosh "$MONGO_URI" --eval '
use ailsa_grants;
db.grants.aggregate([
  {$group: {_id: "$source", count: {$sum: 1}}}
])
'
```

### Ingestion Issues
```bash
# Check logs
tail -f logs/pipeline_*.log

# Test with single grant
python3 -c "
from ingest_to_production import *
import json
with open('data/horizon_europe/normalized.json') as f:
    grants = json.load(f)
print(ingest_grant(grants[0], 'horizon_europe'))
"
```

---

## Verification Commands

```bash
# Run scrapers
python3 -m scraper.pipelines.horizon_europe
python3 -m scraper.pipelines.digital_europe

# Ingest to MongoDB
python3 ingest_to_production.py

# Verify counts
mongosh "$MONGO_URI" --eval '
use ailsa_grants;
print("Horizon Europe:", db.grants.countDocuments({source: "horizon_europe"}));
print("Digital Europe:", db.grants.countDocuments({source: "digital_europe"}));
print("Open grants:", db.grants.countDocuments({status: "Open"}));
print("Total:", db.grants.countDocuments({}));
'
```

---

## Deployment

### Production Checklist
- [ ] Environment variables configured
- [ ] MongoDB connection verified
- [ ] Test run successful
- [ ] Cron job scheduled
- [ ] Monitoring/alerts configured
- [ ] Backup strategy in place

### Monitoring
```bash
# Check last run status
cat logs/last_run_status

# View recent logs
ls -lth logs/ | head -10

# Check database counts
mongosh "$MONGO_URI" --eval '
use ailsa_grants;
db.grants.aggregate([
  {$group: {_id: {source: "$source", status: "$status"}, count: {$sum: 1}}},
  {$sort: {"_id.source": 1, "_id.status": 1}}
])
'
```
