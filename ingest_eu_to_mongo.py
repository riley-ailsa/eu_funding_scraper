#!/usr/bin/env python3
"""
Ingest EU grants from scraper output to MongoDB + Pinecone
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from scraper.pipelines import horizon_europe, digital_europe
from ailsa_shared import MongoDBClient, PineconeClientV3

load_dotenv()

# Step 1: Run scrapers
print("Running Horizon Europe scraper...")
horizon_europe.run()

print("Running Digital Europe scraper...")
digital_europe.run()

# Step 2: Load normalized data
horizon_file = Path("data/horizon_europe/normalized.json")
digital_file = Path("data/digital_europe/normalized.json")

# Step 3: Ingest to MongoDB
print("Ingesting to MongoDB...")
# TODO: Add MongoDB ingestion here

print("Done!")
