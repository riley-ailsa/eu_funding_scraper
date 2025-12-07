#!/usr/bin/env python3
"""
EU Funding Scraper - Fixed Pipeline
"""

import json
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
from tqdm import tqdm

from scraper.pipelines import horizon_europe, digital_europe
from ailsa_shared import Grant, MongoDBClient, PineconeClientV3

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_normalized_grants(source: str) -> List[Grant]:
    """Load normalized grants from JSON and convert to Grant objects"""
    data_path = Path(f"data/{source}/normalized.json")
    
    if not data_path.exists():
        logger.warning(f"No normalized data found at {data_path}")
        return []
    
    with open(data_path) as f:
        grant_dicts = json.load(f)
    
    grants = []
    for grant_dict in grant_dicts:
        try:
            # Map 'id' to 'grant_id' if needed
            if 'id' in grant_dict and 'grant_id' not in grant_dict:
                grant_dict['grant_id'] = grant_dict.pop('id')
            
            for k in ['call_id','open_date','close_date','programme']: grant_dict.pop(k, None)
            grant = Grant(**grant_dict)
            grants.append(grant)
        except Exception as e:
            logger.error(f"Failed to parse grant {grant_dict.get('grant_id', grant_dict.get('id'))}: {e}")
    
    logger.info(f"Loaded {len(grants)} grants from {data_path}")
    return grants


def main():
    parser = argparse.ArgumentParser(description='EU Funding Scraper Pipeline')
    parser.add_argument(
        '--source',
        choices=['horizon', 'digital', 'both'],
        default='both',
        help='Which source to scrape'
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("EU Funding Scraper Pipeline")
    logger.info("=" * 60)
    
    all_grants = []
    
    # Step 1: Run scrapers
    if args.source in ['horizon', 'both']:
        logger.info("Running Horizon Europe scraper...")
        try:
            horizon_europe.run()
            horizon_grants = load_normalized_grants('horizon_europe')
            all_grants.extend(horizon_grants)
        except Exception as e:
            logger.error(f"Horizon Europe scraper failed: {e}")
    
    if args.source in ['digital', 'both']:
        logger.info("Running Digital Europe scraper...")
        try:
            digital_europe.run()
            digital_grants = load_normalized_grants('digital_europe')
            all_grants.extend(digital_grants)
        except Exception as e:
            logger.error(f"Digital Europe scraper failed: {e}")
    
    if not all_grants:
        logger.warning("No grants to process")
        return 1
    
    logger.info(f"Total grants to ingest: {len(all_grants)}")
    
    # Step 2: Ingest to MongoDB
    logger.info("Ingesting to MongoDB...")
    try:
        mongo = MongoDBClient(
            uri=os.getenv("MONGO_URI"),
            database=os.getenv("MONGO_DB_NAME")
        )
        saved, errors = mongo.upsert_grants(all_grants)
        logger.info(f"MongoDB: {saved} saved, {errors} errors")
    except Exception as e:
        logger.error(f"MongoDB ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Step 3: Create embeddings and upsert to Pinecone
    logger.info("Creating embeddings and upserting to Pinecone...")
    try:
        pinecone = PineconeClientV3(
            api_key=os.getenv("PINECONE_API_KEY"),
            index_name=os.getenv("PINECONE_INDEX_NAME"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        embedded = 0
        for grant in tqdm(all_grants, desc="Embedding"):
            try:
                pinecone.upsert_grant(grant)
                embedded += 1
            except Exception as e:
                logger.error(f"Failed to embed grant {grant.grant_id}: {e}")
        
        logger.info(f"Pinecone: {embedded} vectors upserted")
    except Exception as e:
        logger.error(f"Pinecone upsert failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    logger.info("=" * 60)
    logger.info(f"✅ Complete: {len(all_grants)} grants processed")
    logger.info("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
