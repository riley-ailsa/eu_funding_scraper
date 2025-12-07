#!/usr/bin/env python3
"""Eureka grants ingestion to MongoDB"""

import json
from datetime import datetime, timezone
from pymongo import MongoClient, UpdateOne

client = MongoClient("mongodb://localhost:27017")
db = client["ailsa_grants"]

def transform_sections(raw_sections):
    """Convert Eureka sections dict to list format"""
    if not raw_sections:
        return []
    sections = []
    for name, text in raw_sections.items():
        if isinstance(text, dict):
            # Flatten nested dicts (like funding.general)
            text = "\n".join(f"{k}: {v}" for k, v in text.items())
        if text:
            sections.append({"name": name, "text": str(text), "url": ""})
    return sections

def transform_grant(g):
    """Transform Eureka normalized grant to Grant schema"""
    raw = g.get("raw", {})
    sections = transform_sections(raw.get("sections", {}))
    
    return {
        "grant_id": g.get("id"),
        "source": g.get("source"),
        "external_id": g.get("call_id"),
        "title": g.get("title"),
        "url": g.get("url"),
        "status": g.get("status", "").lower(),
        "is_active": g.get("status", "").lower() == "open",
        "sections": sections,
        "programme": g.get("programme"),
        "tags": ["eureka_network"],
        "raw": raw,
        "processing": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

print("Loading Eureka Network...")
with open("/Users/rileycoleman/Ailsa/eureka_network_scraper/data/eureka_network/normalized.json") as f:
    eureka = json.load(f)
print(f"  Loaded {len(eureka)} grants")

transformed = [transform_grant(g) for g in eureka]

print("Upserting to MongoDB...")
ops = [UpdateOne({"grant_id": g["grant_id"]}, {"$set": g}, upsert=True) for g in transformed]
result = db.grants.bulk_write(ops)

print(f"  Matched: {result.matched_count}")
print(f"  Upserted: {result.upserted_count}")
print(f"  Modified: {result.modified_count}")
print(f"\nTotal grants in DB: {db.grants.count_documents({})}")
