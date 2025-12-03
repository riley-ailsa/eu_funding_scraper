#!/usr/bin/env python3
"""
Quick smoke test - processes only 5 grants per source.
Use this to verify the pipeline works before running full scrape.

Usage:
    python test_5_grants.py [horizon|digital|all]
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.pipelines import horizon_europe, digital_europe


def test_horizon():
    print("\n" + "="*60)
    print("Testing Horizon Europe (5 grants)")
    print("="*60 + "\n")
    horizon_europe.run(limit=5)


def test_digital():
    print("\n" + "="*60)
    print("Testing Digital Europe (5 grants)")
    print("="*60 + "\n")
    digital_europe.run(limit=5)


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
    print("Smoke test complete!")
    print("="*60)
    print("\nCheck data/ directories for output:")
    print("  - raw_index.json")
    print("  - html/*.html")
    print("  - normalized.json")
    print("  - audit_log.jsonl")
    print("  - checkpoint.json")
    print("  - validation_report.json")


if __name__ == "__main__":
    main()
