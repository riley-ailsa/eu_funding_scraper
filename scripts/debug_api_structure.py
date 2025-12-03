#!/usr/bin/env python3
"""
Debug the actual API response structure to fix validation.
"""

import requests
import json

BASE_API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"

def fetch_sample_grant(programme_name, framework_id):
    """Fetch one sample grant and show its complete structure"""
    print(f"\n{'='*70}")
    print(f"Sample API Response: {programme_name}")
    print(f"{'='*70}")

    query = {
        "bool": {
            "must": [
                {"term": {"programmePeriod": "2021 - 2027"}},
                {"terms": {"frameworkProgramme": [framework_id]}},
                {"terms": {"status": ["31094501", "31094502", "31094503"]}}
            ]
        }
    }

    params = {
        "apiKey": "SEDIA",
        "text": "***",
        "pageSize": "1",
        "pageNumber": "1"
    }

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
    if results:
        sample = results[0]

        print(f"\n🔍 Top-level fields:")
        for key in sample.keys():
            value = sample[key]
            if isinstance(value, (str, int, bool)) or value is None:
                print(f"   {key}: {value}")
            elif isinstance(value, list):
                print(f"   {key}: [list with {len(value)} items]")
            elif isinstance(value, dict):
                print(f"   {key}: [dict with {len(value)} keys]")

        print(f"\n📋 Metadata fields:")
        metadata = sample.get("metadata", {})
        for key in list(metadata.keys())[:20]:  # First 20 fields
            value = metadata[key]
            if isinstance(value, list) and len(value) > 0:
                print(f"   {key}: {value[0]} (+ {len(value)-1} more)")
            else:
                print(f"   {key}: {value}")

        print(f"\n✨ Key fields for validation:")
        print(f"   identifier (top): {sample.get('identifier')}")
        print(f"   identifier (metadata): {metadata.get('identifier')}")
        print(f"   callIdentifier: {metadata.get('callIdentifier')}")
        print(f"   title (metadata): {metadata.get('title')}")
        print(f"   content (top): {sample.get('content', '')[:80]}")

        print(f"\n📄 Complete sample (formatted):")
        print(json.dumps(sample, indent=2)[:2000] + "\n...")


def main():
    fetch_sample_grant("Digital Europe", "43152860")
    fetch_sample_grant("Horizon Europe", "43108390")


if __name__ == "__main__":
    main()
