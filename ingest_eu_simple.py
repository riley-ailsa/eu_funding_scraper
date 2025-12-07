#!/usr/bin/env python3
"""Simple EU grants ingestion to MongoDB"""

import json
from datetime import datetime
from pymongo import MongoClient

# Connect to local MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["ailsa_grants"]

def transform_grant(g):
    """Transform EU normalized grant to Grant schema"""
    return {
        "grant_id": g.get("id"),
        "source": g.get("source"),
        "external_id": g.get("call_id"),
        "title": g.get("title"),
        "url": g.get("url"),
        "status": "open" if "31094502" in str(g.get("status", "")) else "closed",
        "is_active": "31094502" in str(g.get("status", "")),
        "sections": g.get("sections", []),
        "programme": g.get("programme"),
        "tags": [g.get("source", "eu")],
        "raw": g.get("raw"),
        "processing": {},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

# Load and ingest Horizon Europe
print("Loading Horizon Europe...")
with open("data/horizon_europe/normalized.json") as f:
    horizon = json.load(f)
print(f"  Loaded {len(horizon)} grants")

# Load and ingest Digital Europe  
print("Loading Digital Europe...")
with open("data/digital_europe/normalized.json") as f:
    digital = json.load(f)
print(f"  Loaded {len(digital)} grants")

all_grants = horizon + digital
print(f"\nTotal: {len(all_grants)} grants")

# Transform
transformed = [transform_grant(g) for g in all_grants]

# Upsert to MongoDB
print("Upserting to MongoDB...")
from pymongo import UpdateOne
ops = [
    UpdateOne({"grant_id": g["grant_id"]}, {"$set": g}, upsert=True)
    for g in transformed
]

result = db.grants.bulk_write(ops)
print(f"  Matched: {result.matched_count}")
print(f"  Upserted: {result.upserted_count}")
print(f"  Modified: {result.modified_count}")

# Verify
print(f"\nTotal grants in DB: {db.grants.count_documents({})}")
