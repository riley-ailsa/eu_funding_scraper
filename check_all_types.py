#!/usr/bin/env python3
"""
Check what grant types exist and how many grants each type has.
"""

import requests
import json
from collections import Counter

BASE_API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"

def get_all_grants_for_programme(programme_name, framework_id):
    """Get ALL grants without type filter"""
    print(f"\n{'='*70}")
    print(f"Checking: {programme_name}")
    print(f"Framework ID: {framework_id}")
    print(f"{'='*70}")

    # Query WITHOUT type filter
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

        results = data.get("results", [])
        total = data.get("totalResults", 0)

        print(f"\n✅ Total grants (no type filter): {total}")

        if results:
            # Analyze types
            types = []
            for r in results:
                type_val = r.get('metadata', {}).get('type')
                if isinstance(type_val, list):
                    types.extend(type_val)
                elif type_val:
                    types.append(type_val)

            type_counts = Counter(types)
            print(f"\n📊 Grant types found:")
            for grant_type, count in sorted(type_counts.items()):
                print(f"   Type {grant_type}: {count} grants")

            # Analyze statuses
            statuses = []
            for r in results:
                status_val = r.get('metadata', {}).get('status')
                if isinstance(status_val, list):
                    statuses.extend(status_val)
                elif status_val:
                    statuses.append(status_val)

            status_counts = Counter(statuses)
            print(f"\n📊 Grant statuses found:")
            for status, count in sorted(status_counts.items()):
                print(f"   Status {status}: {count} grants")

        return total

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 0


def test_with_all_types():
    """Test what happens when we include ALL types"""
    print(f"\n{'='*70}")
    print("Testing with ALL type values")
    print(f"{'='*70}")

    # Try types 1-10
    all_types = [str(i) for i in range(1, 11)]

    for programme_name, framework_id in [
        ("Digital Europe", "43152860"),
        ("Horizon Europe", "43108390")
    ]:
        query = {
            "bool": {
                "must": [
                    {"term": {"programmePeriod": "2021 - 2027"}},
                    {"terms": {"frameworkProgramme": [framework_id]}},
                    {"terms": {"type": all_types}}
                ]
            }
        }

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
            print(f"   {programme_name}: {total} grants with types 1-10")

        except Exception as e:
            print(f"   {programme_name}: Error - {e}")


def main():
    print("="*70)
    print("CHECKING ALL GRANT TYPES")
    print("="*70)

    # Check without type filter
    digital_total = get_all_grants_for_programme("Digital Europe", "43152860")
    horizon_total = get_all_grants_for_programme("Horizon Europe", "43108390")

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Digital Europe: {digital_total} total grants (website shows 310)")
    print(f"Horizon Europe: {horizon_total} total grants (website shows 3,424)")

    # Test with all types
    test_with_all_types()

    print(f"\n{'='*70}")
    print("RECOMMENDATION")
    print(f"{'='*70}")
    print("Remove the 'type' filter or expand it to include all types found above.")


if __name__ == "__main__":
    main()
