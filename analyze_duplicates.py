#!/usr/bin/env python3
"""
Analyze duplicate grant IDs to understand why they appear multiple times.
"""

import requests
import json
from collections import defaultdict

BASE_API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"

def fetch_digital_europe_grants():
    """Fetch all Digital Europe grants and analyze duplicates"""
    query = {
        "bool": {
            "must": [
                {"term": {"programmePeriod": "2021 - 2027"}},
                {"terms": {"frameworkProgramme": ["43152860"]}},
                {"terms": {"status": ["31094501", "31094502", "31094503"]}},
            ]
        }
    }

    params = {
        "apiKey": "SEDIA",
        "text": "***",
        "pageSize": "100",
        "pageNumber": "1",
    }

    all_results = []
    page = 1

    while True:
        params["pageNumber"] = str(page)

        resp = requests.post(
            BASE_API_URL,
            params=params,
            files={
                "query": ("blob", json.dumps(query), "application/json"),
                "languages": ("blob", json.dumps(["en"]), "application/json"),
                "sort": ("blob", json.dumps({"field": "sortStatus", "order": "ASC"}), "application/json"),
            },
            timeout=40,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            break

        all_results.extend(results)

        total_size = data.get("totalSize", 0)
        print(f"Page {page}: {len(results)} results (total: {len(all_results)}/{total_size})")

        if len(all_results) >= total_size:
            break

        page += 1

    return all_results


def analyze_duplicates(results):
    """Analyze what makes duplicate IDs different"""

    # Group by identifier
    by_identifier = defaultdict(list)

    for item in results:
        metadata = item.get("metadata", {})
        identifier_field = metadata.get("identifier")

        if identifier_field:
            if isinstance(identifier_field, list) and len(identifier_field) > 0:
                grant_id = identifier_field[0]
            else:
                grant_id = identifier_field

            by_identifier[grant_id].append(item)

    # Find duplicates
    duplicates = {k: v for k, v in by_identifier.items() if len(v) > 1}

    print(f"\n{'='*70}")
    print(f"ANALYSIS OF DUPLICATE IDs")
    print(f"{'='*70}")
    print(f"Total records: {len(results)}")
    print(f"Unique IDs: {len(by_identifier)}")
    print(f"Duplicate IDs: {len(duplicates)}")

    # Analyze most duplicated
    most_duplicated = sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)[:5]

    print(f"\n🔍 Top 5 Most Duplicated IDs:\n")

    for grant_id, items in most_duplicated:
        print(f"\n{'='*70}")
        print(f"ID: {grant_id}")
        print(f"Appears {len(items)} times")
        print(f"{'='*70}")

        # Compare what's different
        for idx, item in enumerate(items, 1):
            metadata = item.get("metadata", {})

            print(f"\nOccurrence #{idx}:")
            print(f"  reference: {item.get('reference')}")
            print(f"  ccm2Id: {metadata.get('ccm2Id', ['N/A'])[0] if isinstance(metadata.get('ccm2Id'), list) else metadata.get('ccm2Id', 'N/A')}")
            print(f"  callccm2Id: {metadata.get('callccm2Id', ['N/A'])[0] if isinstance(metadata.get('callccm2Id'), list) else metadata.get('callccm2Id', 'N/A')}")
            print(f"  type: {metadata.get('type', ['N/A'])[0] if isinstance(metadata.get('type'), list) else metadata.get('type', 'N/A')}")
            print(f"  content: {item.get('content', 'N/A')[:80]}")

            # Check for topic-related fields
            topic_id = metadata.get('topicIdentifier')
            action_type = metadata.get('actionType')

            if topic_id:
                print(f"  topicIdentifier: {topic_id[0] if isinstance(topic_id, list) else topic_id}")
            if action_type:
                print(f"  actionType: {action_type[0] if isinstance(action_type, list) else action_type}")

    # Check if type varies
    print(f"\n\n{'='*70}")
    print(f"TYPE FIELD ANALYSIS")
    print(f"{'='*70}")

    type_counts = defaultdict(int)
    for item in results:
        metadata = item.get("metadata", {})
        type_val = metadata.get("type", ["unknown"])
        if isinstance(type_val, list):
            type_val = type_val[0] if type_val else "unknown"
        type_counts[type_val] += 1

    print("\nType distribution:")
    for type_val, count in sorted(type_counts.items()):
        print(f"  Type {type_val}: {count} records")


def main():
    print("Fetching Digital Europe grants...")
    results = fetch_digital_europe_grants()
    analyze_duplicates(results)


if __name__ == "__main__":
    main()
