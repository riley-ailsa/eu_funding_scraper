# Getting Started - Quick Guide

This is your **immediate action plan** to get the system running.

---

## ✅ Prerequisites Checklist

Before starting, make sure you have:
- [x] Python 3.9+ installed
- [x] PostgreSQL database running (local or cloud)
- [x] Pinecone account created
- [x] OpenAI API key
- [x] `.env` file configured with your credentials

---

## 🚀 Step-by-Step Setup

### Step 1: Apply Database Migration

This adds the new enhanced fields to your PostgreSQL database:

```bash
python3 run_migration.py
```

**Expected output:**
```
Connecting to database...
Running migration...
✅ Migration completed successfully!

✅ Verified new columns: application_info, call_title, deadline_model, duration, eu_identifier, further_information

✅ Ready to run: python3 ingest_to_production.py
```

---

### Step 2: Run the Ingestion Pipeline

This processes all 3,734 grants and loads them into PostgreSQL + Pinecone:

```bash
python3 ingest_to_production.py
```

**What happens:**
- Loads grants from `data/horizon_europe/normalized.json`
- Loads grants from `data/digital_europe/normalized.json`
- Extracts 15+ metadata fields per grant
- Maps status codes (e.g., `['31094502']` → `Open`)
- Validates and fixes dates
- Generates embeddings (full descriptions → vectors)
- Stores in PostgreSQL
- Upserts to Pinecone
- Shows progress bar

**Expected output:**
```
============================================================
INGESTING EU GRANTS TO PRODUCTION
============================================================

============================================================
Ingesting: horizon_europe
============================================================
📁 Loaded 3425 grants from horizon_europe
Processing horizon_europe: 100%|████████████| 3425/3425

✅ horizon_europe complete:
   Success: 3425
   Failed: 0

============================================================
Ingesting: digital_europe
============================================================
📁 Loaded 309 grants from digital_europe
Processing digital_europe: 100%|████████████| 309/309

✅ digital_europe complete:
   Success: 309
   Failed: 0

============================================================
INGESTION COMPLETE
============================================================
Duration: 892.3s
PostgreSQL grants: 3734
Pinecone vectors: 3734
```

**Time estimate:** 15-30 minutes (depends on OpenAI API rate limits)

---

### Step 3: Verify the Results

```bash
# Check PostgreSQL counts
psql $DATABASE_URL -c "SELECT source, status, COUNT(*) FROM grants GROUP BY source, status;"
```

**Expected output:**
```
     source      |   status    | count
-----------------+-------------+-------
 horizon_europe  | Open        |   154
 horizon_europe  | Closed      |  3265
 horizon_europe  | Forthcoming |     6
 digital_europe  | ...         |   ...
```

---

## 🔄 Setup Automated Updates (Optional)

To automatically scrape and ingest new grants daily:

### Step 1: Make the pipeline script executable
```bash
chmod +x cron_full_pipeline.sh
```

### Step 2: Add to crontab
```bash
crontab -e
```

Add this line (runs daily at 2 AM):
```bash
0 2 * * * /Users/rileycoleman/EU\ Funding\ Scraper/cron_full_pipeline.sh
```

Or for weekly updates (Sundays at 2 AM):
```bash
0 2 * * 0 /Users/rileycoleman/EU\ Funding\ Scraper/cron_full_pipeline.sh
```

---

## ✅ You're Done!

Your system is now:
- ✅ Fully configured with enhanced data extraction
- ✅ PostgreSQL populated with 3,734 grants
- ✅ Pinecone populated with semantic embeddings
- ✅ (Optional) Automated daily/weekly updates

---

## 📊 What You Have Now

### PostgreSQL Database
- 3,734 grants with full metadata
- Searchable by SQL (status, programme, budget, dates, etc.)
- Includes application instructions, further info, etc.

### Pinecone Vector Database
- 3,734 embedded grant descriptions
- Semantic search enabled
- Filterable metadata (status, programme, budget, etc.)

### Data Fields (per grant)
- Official EU identifiers
- Programme codes (HORIZON-CL5, HORIZON-EIT, etc.)
- Human-readable status (Open/Closed/Forthcoming)
- Budget information (where available)
- Deadlines and durations
- Full descriptions + summaries
- Application instructions

---

## 🔍 Next Steps

1. **Build your application** that queries this data
2. **Implement semantic search** using Pinecone
3. **Add user interface** for grant discovery
4. **Enable filtering** by programme, status, budget, etc.

See the main [README.md](README.md) for complete documentation.

---

## 🐛 Troubleshooting

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### "psycopg2.OperationalError: could not connect"
Check your `DATABASE_URL` in `.env` file.

### "Migration failed: column already exists"
The migration has already been run. You can skip Step 1 and go directly to Step 2.

### "Rate limit exceeded" from OpenAI
The script will automatically retry with exponential backoff. Just wait for it to complete.

---

## 📞 Need Help?

Check the [README.md](README.md) for:
- Detailed troubleshooting
- Architecture overview
- API documentation
- Development guide
