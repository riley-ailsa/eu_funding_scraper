#!/usr/bin/env python3
"""
Representative sample test - processes 20 grants per source.
Use this to validate data quality before full production run.

Usage:
    python test_20_grants.py [horizon|digital|all]
"""

import sys
import json
from pathlib import Path
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.pipelines import horizon_europe, digital_europe


def analyze_output(source_dir: Path):
    """Analyze the normalized output for data quality"""
    normalized_file = source_dir / "normalized.json"

    if not normalized_file.exists():
        print(f"  ⚠️  No normalized.json found in {source_dir}")
        return

    data = json.loads(normalized_file.read_text(encoding='utf-8'))

    print(f"\n  📊 Analysis of {source_dir.name}:")
    print(f"     Total grants: {len(data)}")

    # Check for missing fields
    missing_titles = sum(1 for g in data if not g.get('title'))
    missing_urls = sum(1 for g in data if not g.get('url'))
    missing_status = sum(1 for g in data if not g.get('status'))
    missing_open_date = sum(1 for g in data if not g.get('open_date'))
    missing_close_date = sum(1 for g in data if not g.get('close_date'))

    print(f"     Missing titles: {missing_titles}")
    print(f"     Missing URLs: {missing_urls}")
    print(f"     Missing status: {missing_status}")
    print(f"     Missing open_date: {missing_open_date}")
    print(f"     Missing close_date: {missing_close_date}")

    # Status distribution
    statuses = [g.get('status') for g in data if g.get('status')]
    status_counts = Counter(statuses)
    print(f"     Status distribution:")
    for status, count in status_counts.most_common():
        print(f"       {status}: {count}")

    # Title length distribution
    title_lengths = [len(g.get('title', '')) for g in data]
    if title_lengths:
        avg_len = sum(title_lengths) / len(title_lengths)
        print(f"     Average title length: {avg_len:.1f} chars")
        print(f"     Min: {min(title_lengths)}, Max: {max(title_lengths)}")

    # Check validation report
    validation_file = source_dir / "validation_report.json"
    if validation_file.exists():
        validation = json.loads(validation_file.read_text(encoding='utf-8'))
        print(f"     Validation issues:")
        for issue_type, count in validation.get('issues_found', {}).items():
            print(f"       {issue_type}: {count}")


def test_horizon():
    print("\n" + "="*60)
    print("Testing Horizon Europe (20 grants)")
    print("="*60 + "\n")
    horizon_europe.run(limit=20)
    analyze_output(Path("data/horizon_europe"))


def test_digital():
    print("\n" + "="*60)
    print("Testing Digital Europe (20 grants)")
    print("="*60 + "\n")
    digital_europe.run(limit=20)
    analyze_output(Path("data/digital_europe"))


def main():
    if len(sys.argv) > 1:
        source = sys.argv[1].lower()
    else:
        source = "all"

    if source in ["horizon", "all"]:
        test_horizon()

    if source in ["digital", "all"]:
        test_digital()

    print("\n" + "="*60)
    print("Sample test complete!")
    print("="*60)
    print("\nReview the analysis above for data quality issues.")
    print("If everything looks good, proceed with full run.")


if __name__ == "__main__":
    main()
