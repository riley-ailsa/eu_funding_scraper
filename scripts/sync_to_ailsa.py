#!/usr/bin/env python3
"""
Sync scraped grants to Ask Ailsa's vector database.

This is a template - adapt to your actual vector DB setup
(ChromaDB, Pinecone, Weaviate, etc.)
"""

import json
from pathlib import Path
from datetime import datetime


def prepare_grant_text(grant):
    """
    Prepare grant text for embedding.
    This will be embedded and stored in the vector database.
    """
    # Extract description if available
    raw = grant.get('raw', {})
    metadata = raw.get('metadata', {})

    # Try to get description from various fields
    description = ''
    if isinstance(metadata.get('descriptionByte'), list) and metadata.get('descriptionByte'):
        description = metadata['descriptionByte'][0][:2000]  # Limit length
    elif isinstance(metadata.get('description'), list) and metadata.get('description'):
        description = metadata['description'][0][:2000]

    # Format text for embedding
    text_content = f"""
Title: {grant['title']}

Programme: {grant['source'].replace('_', ' ').title()}
Status: {grant['status']}
Call ID: {grant['call_id']}

Open Date: {grant['open_date'] or 'Not specified'}
Close Date: {grant['close_date'] or 'Not specified'}

{description}

URL: {grant['url']}
""".strip()

    return text_content


def prepare_grant_metadata(grant):
    """
    Prepare metadata for filtering/searching.
    This will be stored alongside the embedding.
    """
    return {
        'id': grant['id'],
        'source': grant['source'],
        'title': grant['title'],
        'status': grant['status'],
        'programme': grant.get('programme'),
        'url': grant['url'],
        'open_date': grant['open_date'],
        'close_date': grant['close_date'],
        'call_id': grant['call_id'],
        'indexed_at': datetime.now().isoformat()
    }


def sync_grants_to_vector_db():
    """
    Sync normalized grants to vector database.

    Example using ChromaDB - adapt to your setup:

    import chromadb
    client = chromadb.Client()
    collection = client.get_or_create_collection("eu_funding")
    """

    print("="*70)
    print("SYNCING GRANTS TO VECTOR DATABASE")
    print("="*70)

    total_synced = 0

    for source in ['horizon_europe', 'digital_europe']:
        normalized_file = Path(f"data/{source}/normalized.json")

        if not normalized_file.exists():
            print(f"⚠️  Skipping {source}: normalized.json not found")
            continue

        grants = json.loads(normalized_file.read_text(encoding='utf-8'))
        print(f"\n📂 Processing {source}: {len(grants)} grants")

        for grant in grants:
            # Prepare text and metadata
            text_content = prepare_grant_text(grant)
            metadata = prepare_grant_metadata(grant)

            # TODO: Replace this with your actual vector DB upsert
            # Example for ChromaDB:
            # collection.upsert(
            #     ids=[grant['id']],
            #     documents=[text_content],
            #     metadatas=[metadata]
            # )

            # Example for Pinecone:
            # index.upsert(
            #     vectors=[(grant['id'], embedding, metadata)]
            # )

            # For now, just print summary
            if total_synced < 3:  # Show first 3 as examples
                print(f"\n  Example {total_synced + 1}:")
                print(f"    ID: {grant['id']}")
                print(f"    Title: {grant['title'][:60]}...")
                print(f"    Text length: {len(text_content)} chars")

            total_synced += 1

    print(f"\n{'='*70}")
    print(f"✅ Total grants processed: {total_synced}")
    print(f"{'='*70}")
    print("\n⚠️  NOTE: This is a template script.")
    print("   Update the sync_grants_to_vector_db() function with your")
    print("   actual vector database connection and upsert logic.")


def sync_only_new_grants():
    """
    Sync only grants that have changed since last sync.
    More efficient for frequent updates.
    """
    # Load the most recent update reports
    for source in ['horizon_europe', 'digital_europe']:
        source_dir = Path(f"data/{source}")

        # Find most recent update report
        update_reports = sorted(source_dir.glob("update_report_*.json"))
        if not update_reports:
            print(f"No update reports found for {source}")
            continue

        latest_report = update_reports[-1]
        report = json.loads(latest_report.read_text(encoding='utf-8'))

        print(f"\n📊 {source}:")
        print(f"   New grants: {report['changes']['new']}")
        print(f"   Updated grants: {report['changes']['updated']}")

        # Load normalized.json and sync only changed grants
        normalized_file = source_dir / "normalized.json"
        if normalized_file.exists():
            grants = json.loads(normalized_file.read_text(encoding='utf-8'))
            grants_by_id = {g['id']: g for g in grants}

            # Sync only new and updated grants
            changed_ids = set(report.get('new_grant_ids', []) + report.get('updated_grant_ids', []))

            for grant_id in changed_ids:
                if grant_id in grants_by_id:
                    grant = grants_by_id[grant_id]
                    # Upsert to vector DB
                    print(f"   Syncing: {grant_id}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--incremental":
        sync_only_new_grants()
    else:
        sync_grants_to_vector_db()
