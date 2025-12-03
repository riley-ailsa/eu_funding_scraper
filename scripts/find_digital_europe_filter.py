#!/usr/bin/env python3
"""
Find the correct filter for Digital Europe Programme
by searching for a known Digital Europe call.
"""

import requests
import json
from collections import Counter

BASE_API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"

def search_for_specific_call(call_id):
    """Search for a specific known call ID"""
    print(f"\n{'='*70}")
    print(f"Searching for specific call: {call_id}")
    print(f"{'='*70}")

    params = {
        "apiKey": "SEDIA",
        "text": call_id,
        "pageSize": "10",
        "pageNumber": "1"
    }

    # Minimal query to get results
    query = {
        "bool": {
            "must": [
                {"term": {"programmePeriod": "2021 - 2027"}}
            ]
        }
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

        print(f"\n✅ Found {total} total results")
        print(f"   Retrieved {len(results)} in this page")

        if results:
            # Find the exact match
            exact_match = None
            for r in results:
                metadata = r.get('metadata', {})
                identifier_field = metadata.get('identifier')
                if identifier_field:
                    identifier = identifier_field[0] if isinstance(identifier_field, list) else identifier_field
                    if identifier == call_id:
                        exact_match = r
                        break

            if not exact_match:
                exact_match = results[0]

            metadata = exact_match.get('metadata', {})
            identifier_field = metadata.get('identifier')
            identifier = identifier_field[0] if isinstance(identifier_field, list) else identifier_field

            print(f"\n📋 Result details:")
            print(f"   Identifier: {identifier}")
            print(f"   Title: {exact_match.get('content', '')[:80]}...")

            print(f"\n   🔍 CRITICAL FIELDS FOR FILTERING:")
            print(f"   =====================================")

            # These are the key fields
            framework = metadata.get('frameworkProgramme')
            programme = metadata.get('programme')
            program_code = metadata.get('programCode')
            programme_division = metadata.get('programmeDivision')

            print(f"   frameworkProgramme: {framework}")
            print(f"   programme: {programme}")
            print(f"   programCode: {program_code}")
            print(f"   programmeDivision: {programme_division}")

            # Show what to use
            print(f"\n   ✨ USE THIS IN YOUR FILTER:")
            print(f"   =====================================")
            if framework:
                if isinstance(framework, list):
                    framework_str = framework[0] if framework else None
                else:
                    framework_str = framework
                print(f"   \"frameworkProgramme\": [\"{framework_str}\"]")

            if programme_division:
                print(f"   OR")
                if isinstance(programme_division, list):
                    # Use the most specific division (usually the first or last)
                    div_str = programme_division[-1] if programme_division else None
                else:
                    div_str = programme_division
                print(f"   \"programmeDivision\": [\"{div_str}\"]")

            return exact_match

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_framework_id(framework_id):
    """Test if a framework ID returns Digital Europe grants"""
    print(f"\n{'='*70}")
    print(f"Testing frameworkProgramme: {framework_id}")
    print(f"{'='*70}")

    query = {
        "bool": {
            "must": [
                {"term": {"programmePeriod": "2021 - 2027"}},
                {"terms": {"type": ["1", "2"]}},
                {"terms": {"frameworkProgramme": [framework_id]}}
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

        results = data.get("results", [])
        total = data.get("totalResults", 0)

        print(f"   Found {total} total results")

        if results:
            # Check identifiers
            identifiers = []
            for r in results[:10]:
                metadata = r.get('metadata', {})
                identifier_field = metadata.get('identifier')
                if identifier_field:
                    identifier = identifier_field[0] if isinstance(identifier_field, list) else identifier_field
                    identifiers.append(identifier)

            digital_count = sum(1 for i in identifiers if i and i.startswith('DIGITAL-'))

            print(f"   Sample identifiers: {identifiers[:5]}")
            print(f"   Digital Europe calls: {digital_count}/{len(identifiers)}")

            if digital_count > 0:
                print(f"   ✅ This looks like Digital Europe!")
                return True

        return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    print("="*70)
    print("FINDING DIGITAL EUROPE PROGRAMME API FILTER")
    print("="*70)

    # Known Digital Europe call IDs
    known_digital_calls = [
        "DIGITAL-2025-EDIH-AC-08-CONSOLIDATION-STEP",
        "DIGITAL-2025-SKILLS-08-VIRTUAL-WORLDS-ACADEMY-STEP",
        "DIGITAL-IRIS2-2025-QCI-03",
        "DIGITAL-2026-EDIH-EU-EEA-09-CONSOLIDATION-STEP",
    ]

    print("\nStep 1: Search for known Digital Europe calls...")

    digital_result = None
    for call_id in known_digital_calls:
        result = search_for_specific_call(call_id)
        if result:
            digital_result = result
            break

    if digital_result:
        # Extract the framework ID
        metadata = digital_result.get('metadata', {})
        framework = metadata.get('frameworkProgramme')

        if framework:
            fw_id = framework[0] if isinstance(framework, list) else framework

            print(f"\n\nStep 2: Testing if frameworkProgramme '{fw_id}' returns Digital Europe grants...")
            if test_framework_id(fw_id):
                print(f"\n{'='*70}")
                print(f"🎉 SUCCESS! USE THIS IN digital_europe.py:")
                print(f"{'='*70}")
                print(f"""
query_filters={{
    "type": ["1", "2"],
    "programmePeriod": "2021 - 2027",
    "frameworkProgramme": ["{fw_id}"],
}}
                """)
    else:
        print("\n⚠️  Could not find any known Digital Europe calls.")
        print("    The API might have changed or calls might be archived.")

        print("\n\nStep 3: Testing candidate framework IDs from earlier search...")
        # From your earlier search, 43332642 appeared 9 times
        candidates = ["43332642", "43637601", "43152860"]

        for candidate in candidates:
            if test_framework_id(candidate):
                print(f"\n{'='*70}")
                print(f"🎉 FOUND IT! USE THIS IN digital_europe.py:")
                print(f"{'='*70}")
                print(f"""
query_filters={{
    "type": ["1", "2"],
    "programmePeriod": "2021 - 2027",
    "frameworkProgramme": ["{candidate}"],
}}
                """)
                break


if __name__ == "__main__":
    main()
