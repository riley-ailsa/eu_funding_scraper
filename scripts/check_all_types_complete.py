#!/usr/bin/env python3
"""
Check ALL grant types by fetching multiple pages.
"""

import requests
import json
from collections import Counter

BASE_API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"

def get_complete_type_analysis(programme_name, framework_id, max_pages=10):
    """Get grants across multiple pages to see all types"""
    print(f"\n{'='*70}")
    print(f"Complete Analysis: {programme_name}")
    print(f"Framework ID: {framework_id}")
    print(f"{'='*70}")

    all_types = []
    all_statuses = []
    all_identifiers = []

    # Fetch multiple pages
    for page in range(1, max_pages + 1):
        query = {
            "bool": {
                "must": [
                    {"term": {"programmePeriod": "2021 - 2027"}},
                    {"terms": {"frameworkProgramme": [framework_id]}}
                ]
            }
        }

        params = {
            "apiKey": "SEDIA",
            "text": "***",
            "pageSize": "100",
            "pageNumber": str(page)
        }

        try:
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
            total = data.get("totalResults", 0)

            if page == 1:
                print(f"\n✅ Total grants: {total}")

            if not results:
                break

            print(f"   Fetching page {page}... ({len(results)} results)")

            # Collect types
            for r in results:
                type_val = r.get('metadata', {}).get('type')
                if isinstance(type_val, list):
                    all_types.extend(type_val)
                elif type_val:
                    all_types.append(type_val)

                status_val = r.get('metadata', {}).get('status')
                if isinstance(status_val, list):
                    all_statuses.extend(status_val)
                elif status_val:
                    all_statuses.append(status_val)

                # Get identifier from metadata
                metadata = r.get('metadata', {})
                identifier_field = metadata.get('identifier')
                if identifier_field:
                    if isinstance(identifier_field, list) and len(identifier_field) > 0:
                        all_identifiers.append(identifier_field[0])
                    else:
                        all_identifiers.append(identifier_field)

        except Exception as e:
            print(f"   Error on page {page}: {e}")
            break

    # Analysis
    type_counts = Counter(all_types)
    status_counts = Counter(all_statuses)

    print(f"\n📊 Grant Types Distribution (across {len(all_identifiers)} grants):")
    for grant_type, count in sorted(type_counts.items()):
        pct = (count / len(all_identifiers) * 100) if all_identifiers else 0
        print(f"   Type '{grant_type}': {count} grants ({pct:.1f}%)")

    print(f"\n📊 Status Distribution:")
    for status, count in sorted(status_counts.items()):
        pct = (count / len(all_identifiers) * 100) if all_identifiers else 0
        print(f"   Status '{status}': {count} grants ({pct:.1f}%)")

    print(f"\n📋 Sample Identifiers (first 10):")
    for identifier in all_identifiers[:10]:
        print(f"   {identifier}")

    return {
        'total': total,
        'types': type_counts,
        'statuses': status_counts,
        'identifiers': all_identifiers
    }


def test_specific_filters(programme_name, framework_id):
    """Test specific combinations to match website results"""
    print(f"\n{'='*70}")
    print(f"Testing Filter Combinations: {programme_name}")
    print(f"{'='*70}")

    # Test 1: No status filter (all statuses)
    query1 = {
        "bool": {
            "must": [
                {"term": {"programmePeriod": "2021 - 2027"}},
                {"terms": {"frameworkProgramme": [framework_id]}}
            ]
        }
    }

    # Test 2: With common status filters (Open, Forthcoming, Closed)
    query2 = {
        "bool": {
            "must": [
                {"term": {"programmePeriod": "2021 - 2027"}},
                {"terms": {"frameworkProgramme": [framework_id]}},
                {"terms": {"status": ["31094501", "31094502", "31094503"]}}  # Common status IDs
            ]
        }
    }

    for test_name, query in [("All statuses", query1), ("Open/Forthcoming/Closed only", query2)]:
        params = {
            "apiKey": "SEDIA",
            "text": "***",
            "pageSize": "10",
            "pageNumber": "1"
        }

        try:
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

            total = data.get("totalResults", 0)
            print(f"   {test_name}: {total} grants")

        except Exception as e:
            print(f"   {test_name}: Error - {e}")


def main():
    print("="*70)
    print("COMPLETE GRANT TYPE ANALYSIS")
    print("="*70)

    # Analyze Digital Europe
    digital_data = get_complete_type_analysis("Digital Europe", "43152860", max_pages=6)

    # Analyze Horizon Europe
    horizon_data = get_complete_type_analysis("Horizon Europe", "43108390", max_pages=10)

    # Test filter combinations
    test_specific_filters("Digital Europe", "43152860")
    test_specific_filters("Horizon Europe", "43108390")

    print(f"\n{'='*70}")
    print("SUMMARY & RECOMMENDATIONS")
    print(f"{'='*70}")

    print(f"\nDigital Europe:")
    print(f"  API shows: {digital_data['total']} total grants")
    print(f"  Website shows: 310 grants")
    print(f"  Types found: {list(digital_data['types'].keys())}")

    print(f"\nHorizon Europe:")
    print(f"  API shows: {horizon_data['total']} total grants")
    print(f"  Website shows: 3,424 grants")
    print(f"  Types found: {list(horizon_data['types'].keys())}")

    print(f"\n✨ RECOMMENDED FIX:")
    print(f"  Remove the 'type' filter entirely from both scrapers.")
    print(f"  The type filter is limiting results unnecessarily.")
    print(f"\n  Change from:")
    print(f"    \"type\": [\"1\", \"2\"]")
    print(f"  To:")
    print(f"    (remove this line completely)")


if __name__ == "__main__":
    main()
