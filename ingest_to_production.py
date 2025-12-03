#!/usr/bin/env python3
"""
Ingest EU grants into production MongoDB + Pinecone.
Handles both Horizon Europe and Digital Europe programmes.
"""

import json
import os
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import openai
from pymongo import MongoClient
from pinecone import Pinecone
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "ailsa-grants")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "ailsa_grants")

# EUR to GBP exchange rate (update periodically or use API)
EUR_TO_GBP_RATE = 0.85

# Initialize clients
openai.api_key = OPENAI_API_KEY
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB_NAME]


def load_grants(source: str) -> List[Dict[str, Any]]:
    """Load normalized grants from scraper output."""
    file_path = Path(f"data/{source}/normalized.json")

    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        logger.info(f"Run scraper first: python -m scraper.pipelines.{source}")
        return []

    grants = json.loads(file_path.read_text(encoding='utf-8'))
    logger.info(f"Loaded {len(grants)} grants from {source}")
    return grants


def clean_html(text: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def convert_eur_to_gbp(amount_eur: Optional[int]) -> Optional[int]:
    """Convert EUR to GBP using approximate exchange rate."""
    return int(amount_eur * EUR_TO_GBP_RATE) if amount_eur else None


def extract_tags(grant: Dict[str, Any]) -> List[str]:
    """Extract tags from raw data."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})
    priorities = metadata.get('crossCuttingPriorities', [])
    return priorities if isinstance(priorities, list) else []


def extract_sectors_from_tags(tags: List[str]) -> List[str]:
    """Map cross-cutting priorities to sector categories."""
    sector_mapping = {
        'climate': ['Climate', 'Environment'],
        'digital': ['Digital', 'Technology'],
        'health': ['Health', 'Life Sciences'],
        'energy': ['Energy', 'Clean Tech'],
        'transport': ['Transport', 'Mobility'],
        'food': ['Food', 'Agriculture'],
        'security': ['Security', 'Defence'],
        'space': ['Space', 'Aerospace'],
        'culture': ['Culture', 'Creative Industries'],
        'social': ['Social Innovation'],
        'industrial': ['Manufacturing', 'Industry'],
    }

    sectors = set()
    for tag in tags:
        tag_lower = tag.lower()
        for keyword, sector_list in sector_mapping.items():
            if keyword in tag_lower:
                sectors.update(sector_list)

    return list(sectors) if sectors else ['General']


def extract_summary(grant: Dict[str, Any]) -> str:
    """Extract description summary (first 500 chars)."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    desc = None
    if 'descriptionByte' in metadata:
        desc_field = metadata['descriptionByte']
        if isinstance(desc_field, list) and len(desc_field) > 0:
            desc = desc_field[0]
        elif isinstance(desc_field, str):
            desc = desc_field

    if desc:
        desc = clean_html(desc)
        return desc[:500] if len(desc) > 500 else desc

    return ''


def extract_full_description(grant: Dict[str, Any]) -> str:
    """Extract full description text."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    desc = None
    if 'descriptionByte' in metadata:
        desc_field = metadata['descriptionByte']
        if isinstance(desc_field, list) and len(desc_field) > 0:
            desc = desc_field[0]
        elif isinstance(desc_field, str):
            desc = desc_field

    return clean_html(desc) if desc else ''


def extract_budget(grant: Dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    """Extract budget_min and budget_max from raw data."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    budget = metadata.get('budget', [])
    if isinstance(budget, list) and budget:
        try:
            budget_val = int(budget[0])
            return (budget_val, budget_val)
        except (ValueError, TypeError):
            pass

    return (None, None)


def extract_programme_name(grant: Dict[str, Any]) -> Optional[str]:
    """Extract programme code from identifier (e.g., 'HORIZON-CL5', 'HORIZON-EIT')."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    if 'identifier' in metadata:
        ident = metadata['identifier']
        if isinstance(ident, list) and ident:
            parts = ident[0].split('-')
            if len(parts) >= 2:
                return '-'.join(parts[:2])

    return None


def extract_action_type(grant: Dict[str, Any]) -> Optional[str]:
    """Extract action type from metadata."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    if 'type' in metadata:
        type_field = metadata['type']
        if isinstance(type_field, list) and type_field:
            return type_field[0]

    return None


def extract_duration(grant: Dict[str, Any]) -> Optional[str]:
    """Extract project duration."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    if 'duration' in metadata:
        duration = metadata['duration']
        if isinstance(duration, list) and duration:
            duration_text = clean_html(duration[0])
            return duration_text[:200] if len(duration_text) > 200 else duration_text

    return None


def extract_deadline_model(grant: Dict[str, Any]) -> Optional[str]:
    """Extract deadline model (single-stage vs multiple cut-off)."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    if 'deadlineModel' in metadata:
        model = metadata['deadlineModel']
        if isinstance(model, list) and model:
            return model[0]

    return None


def extract_identifier(grant: Dict[str, Any]) -> Optional[str]:
    """Extract official EU identifier."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    if 'identifier' in metadata:
        ident = metadata['identifier']
        if isinstance(ident, list) and ident:
            return ident[0]

    return None


def extract_call_title(grant: Dict[str, Any]) -> Optional[str]:
    """Extract call title."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    if 'callTitle' in metadata:
        title = metadata['callTitle']
        if isinstance(title, list) and title:
            return title[0]

    return None


def extract_further_info(grant: Dict[str, Any]) -> Optional[str]:
    """Extract further information (HTML content)."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    if 'furtherInformation' in metadata:
        info = metadata['furtherInformation']
        if isinstance(info, list) and info:
            info_text = clean_html(info[0])
            return info_text[:1000] if len(info_text) > 1000 else info_text

    return None


def extract_application_info(grant: Dict[str, Any]) -> Optional[str]:
    """Extract beneficiary administration/application instructions."""
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    if 'beneficiaryAdministration' in metadata:
        info = metadata['beneficiaryAdministration']
        if isinstance(info, list) and info:
            info_text = clean_html(info[0])
            return info_text[:1000] if len(info_text) > 1000 else info_text

    return None


def map_status(grant: Dict[str, Any]) -> str:
    """Convert status ID to readable string."""
    status_map = {
        '31094501': 'Forthcoming',
        '31094502': 'Open',
        '31094503': 'Closed'
    }

    status = grant.get('status', '')

    if isinstance(status, str):
        match = re.search(r"'(\d+)'", status)
        if match:
            status_id = match.group(1)
            return status_map.get(status_id, 'Unknown')

    if isinstance(status, list) and len(status) > 0:
        status_id = status[0]
        return status_map.get(status_id, 'Unknown')

    return 'Unknown'


def extract_embedding_text(grant_doc: Dict[str, Any]) -> str:
    """Extract rich text for embedding generation."""
    parts = []

    if grant_doc.get('title'):
        parts.append(f"Title: {grant_doc['title']}")

    if grant_doc.get('source'):
        parts.append(f"Programme: {grant_doc['source'].replace('_', ' ').title()}")

    if grant_doc.get('status'):
        parts.append(f"Status: {grant_doc['status']}")

    if grant_doc.get('closes_at'):
        parts.append(f"Deadline: {grant_doc['closes_at']}")

    if grant_doc.get('programme'):
        parts.append(f"Programme Code: {grant_doc['programme']}")

    if grant_doc.get('action_type'):
        parts.append(f"Action Type: {grant_doc['action_type']}")

    description = grant_doc.get('description', '')
    if description:
        if len(description) > 4000:
            description = description[:3500] + "\n...\n" + description[-500:]
        parts.append(f"\nDescription:\n{description}")

    tags = grant_doc.get('tags', [])
    if tags:
        parts.append(f"\nFocus Areas: {', '.join(tags[:10])}")

    return "\n".join(parts)


def normalize_eu_grant(grant: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Normalize a raw EU grant to the MongoDB document schema.

    Args:
        grant: Raw grant data from scraper
        source: "horizon_europe" or "digital_europe"

    Returns:
        Normalized MongoDB document
    """
    # Validate and fix dates
    open_date = grant.get('open_date')
    close_date = grant.get('close_date')

    if open_date and close_date:
        try:
            open_dt = datetime.fromisoformat(open_date.replace('Z', '+00:00'))
            close_dt = datetime.fromisoformat(close_date.replace('Z', '+00:00'))
            if close_dt < open_dt:
                logger.warning(f"Fixing swapped dates for {grant['id']}")
                open_date, close_date = close_date, open_date
        except (ValueError, TypeError):
            pass

    # Extract fields
    budget_min, budget_max = extract_budget(grant)
    tags = extract_tags(grant)
    status = map_status(grant)
    eu_identifier = extract_identifier(grant)

    # Build document following the spec schema
    grant_doc = {
        "grant_id": f"{source}_{grant['id']}",
        "source": source,
        "external_id": eu_identifier or grant['id'],

        # Core metadata
        "title": grant['title'],
        "call_title": extract_call_title(grant),
        "url": grant['url'],
        "description": extract_full_description(grant),
        "description_summary": extract_summary(grant),

        # Status & dates
        "status": status,
        "is_active": status == "Open",
        "opens_at": open_date,
        "closes_at": close_date,
        "deadline_model": extract_deadline_model(grant),

        # Funding (EUR values, with GBP conversion)
        "total_fund_gbp": convert_eur_to_gbp(budget_max),
        "total_fund_eur": budget_max,
        "budget_min": budget_min,
        "budget_max": budget_max,
        "project_funding_min": budget_min,
        "project_funding_max": budget_max,
        "competition_type": "grant",

        # Programme info
        "programme": extract_programme_name(grant),
        "action_type": extract_action_type(grant),
        "duration": extract_duration(grant),

        # Classification
        "tags": tags,
        "sectors": extract_sectors_from_tags(tags),

        # Additional EU-specific fields
        "further_information": extract_further_info(grant),
        "application_info": extract_application_info(grant),

        # Timestamps
        "scraped_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    return grant_doc


def ingest_grant(grant: Dict[str, Any], source: str) -> bool:
    """
    Ingest one grant into MongoDB and Pinecone.

    Args:
        grant: Raw grant from scraper
        source: "horizon_europe" or "digital_europe"

    Returns:
        True if successful, False otherwise
    """
    try:
        # Normalize to MongoDB document
        grant_doc = normalize_eu_grant(grant, source)

        # Upsert to MongoDB
        result = db.grants.update_one(
            {"grant_id": grant_doc["grant_id"]},
            {
                "$set": grant_doc,
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )

        # Generate embedding
        embedding_text = extract_embedding_text(grant_doc)
        response = openai.embeddings.create(
            input=embedding_text,
            model="text-embedding-3-small"
        )
        embedding = response.data[0].embedding

        # Upsert to Pinecone with metadata
        index.upsert(vectors=[{
            'id': grant_doc["grant_id"],
            'values': embedding,
            'metadata': {
                'source': source,
                'title': grant_doc["title"][:500] if grant_doc.get("title") else '',
                'programme': (grant_doc.get("programme") or "")[:100],
                'status': grant_doc["status"],
                'url': grant_doc["url"],
                'budget_min': str(grant_doc.get("budget_min") or ""),
                'budget_max': str(grant_doc.get("budget_max") or ""),
                'closes_at': grant_doc.get("closes_at") or "",
                'is_active': grant_doc["is_active"],
                'action_type': grant_doc.get("action_type") or "",
                'tags': ','.join(grant_doc.get("tags", [])[:5]),
            }
        }])

        return True

    except Exception as e:
        logger.error(f"Failed to ingest {grant.get('id')}: {e}")
        return False


def ingest_source(source: str) -> Dict[str, int]:
    """
    Ingest all grants from a source.

    Args:
        source: "horizon_europe" or "digital_europe"

    Returns:
        Dictionary with success and failure counts
    """
    logger.info(f"{'='*60}")
    logger.info(f"Ingesting: {source}")
    logger.info(f"{'='*60}")

    grants = load_grants(source)
    if not grants:
        return {'success': 0, 'failed': 0}

    success_count = 0
    fail_count = 0

    for grant in tqdm(grants, desc=f"Processing {source}"):
        # Add source to grant for processing
        grant['source'] = source

        if ingest_grant(grant, source):
            success_count += 1
        else:
            fail_count += 1

    logger.info(f"{source} complete: Success={success_count}, Failed={fail_count}")

    return {'success': success_count, 'failed': fail_count}


def get_stats() -> Dict[str, Any]:
    """Get current database statistics."""
    stats = {
        'mongodb': {
            'total': db.grants.count_documents({}),
            'horizon_europe': db.grants.count_documents({'source': 'horizon_europe'}),
            'digital_europe': db.grants.count_documents({'source': 'digital_europe'}),
            'by_status': {}
        },
        'pinecone': {}
    }

    # Status breakdown
    for status in ['Open', 'Closed', 'Forthcoming']:
        stats['mongodb']['by_status'][status] = db.grants.count_documents({'status': status})

    # Pinecone stats
    try:
        pinecone_stats = index.describe_index_stats()
        stats['pinecone']['total_vectors'] = pinecone_stats.get('total_vector_count', 0)
    except Exception as e:
        logger.warning(f"Could not get Pinecone stats: {e}")
        stats['pinecone']['total_vectors'] = 'unavailable'

    return stats


def main():
    """Main ingestion entry point."""
    logger.info("="*60)
    logger.info("INGESTING EU GRANTS TO PRODUCTION (MongoDB + Pinecone)")
    logger.info("="*60)

    start_time = datetime.now()

    # Ingest both sources
    horizon_results = ingest_source("horizon_europe")
    digital_results = ingest_source("digital_europe")

    # Get final stats
    stats = get_stats()

    duration = (datetime.now() - start_time).total_seconds()

    logger.info(f"\n{'='*60}")
    logger.info("INGESTION COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Duration: {duration:.1f}s")
    logger.info(f"Horizon Europe: {horizon_results['success']} success, {horizon_results['failed']} failed")
    logger.info(f"Digital Europe: {digital_results['success']} success, {digital_results['failed']} failed")
    logger.info(f"MongoDB total grants: {stats['mongodb']['total']}")
    logger.info(f"  - Horizon Europe: {stats['mongodb']['horizon_europe']}")
    logger.info(f"  - Digital Europe: {stats['mongodb']['digital_europe']}")
    logger.info(f"  - Open: {stats['mongodb']['by_status'].get('Open', 0)}")
    logger.info(f"  - Closed: {stats['mongodb']['by_status'].get('Closed', 0)}")
    logger.info(f"  - Forthcoming: {stats['mongodb']['by_status'].get('Forthcoming', 0)}")
    logger.info(f"Pinecone vectors: {stats['pinecone']['total_vectors']}")

    # Close MongoDB connection
    mongo_client.close()


if __name__ == "__main__":
    main()
