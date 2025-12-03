#!/usr/bin/env python3
"""
Scrape EU grants and export to Excel for review.
Uses the unified excel_export module for consistent formatting.

Usage:
    python scrape_to_excel.py [--limit N] [--source horizon|digital|all]
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
# Add scripts directory for excel_export module
sys.path.insert(0, str(Path(__file__).parent))

from scraper.pipelines import horizon_europe, digital_europe
from excel_export import (
    normalize_grant_for_excel,
    export_grants_to_excel,
    generate_summary,
    print_summary,
)


def load_normalized_grants(source: str) -> list:
    """Load normalized grants from JSON file."""
    file_path = Path(f"data/{source}/normalized.json")
    if not file_path.exists():
        return []
    return json.loads(file_path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description='Scrape EU grants and export to Excel')
    parser.add_argument('--limit', type=int, default=20, help='Number of grants per source (default: 20)')
    parser.add_argument('--source', choices=['horizon', 'digital', 'all'], default='all',
                        help='Source to scrape (default: all)')
    args = parser.parse_args()

    all_grants = []

    # Run scrapers
    if args.source in ['horizon', 'all']:
        print("\n" + "="*60)
        print(f"Scraping Horizon Europe ({args.limit} grants)")
        print("="*60 + "\n")
        horizon_europe.run(limit=args.limit)

        grants = load_normalized_grants('horizon_europe')
        for g in grants:
            all_grants.append(normalize_grant_for_excel(g, 'horizon_europe'))
        print(f"Loaded {len(grants)} Horizon Europe grants")

    if args.source in ['digital', 'all']:
        print("\n" + "="*60)
        print(f"Scraping Digital Europe ({args.limit} grants)")
        print("="*60 + "\n")
        digital_europe.run(limit=args.limit)

        grants = load_normalized_grants('digital_europe')
        for g in grants:
            all_grants.append(normalize_grant_for_excel(g, 'digital_europe'))
        print(f"Loaded {len(grants)} Digital Europe grants")

    if not all_grants:
        print("No grants found to export!")
        return

    # Generate and print summary
    summary = generate_summary(all_grants)
    print_summary(summary)

    # Export to Excel
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"eu_grants_review_{timestamp}.xlsx"
    export_grants_to_excel(all_grants, filename, sheet_name="EU Grants")
    print(f"\nExcel file saved: {filename}")


if __name__ == "__main__":
    main()
