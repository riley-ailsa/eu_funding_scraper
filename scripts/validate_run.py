#!/usr/bin/env python3
"""
Comprehensive validation and diagnostics after full scraper run.

Checks:
- Data completeness
- Anomaly detection
- Error rates
- Content quality

Usage:
    python validate_run.py [horizon|digital|all]
"""

import sys
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
import re

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_json(filepath: Path):
    """Load JSON file safely"""
    if not filepath.exists():
        return None
    try:
        return json.loads(filepath.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print(f"  ⚠️  Error loading {filepath}: {e}")
        return None


def validate_source(source_dir: Path):
    """Run comprehensive validation on a source directory"""

    print(f"\n{'='*70}")
    print(f"VALIDATING: {source_dir.name}")
    print(f"{'='*70}")

    if not source_dir.exists():
        print(f"  ❌ Directory not found: {source_dir}")
        return

    # Load data files
    raw_index = load_json(source_dir / "raw_index.json")
    normalized = load_json(source_dir / "normalized.json")
    checkpoint = load_json(source_dir / "checkpoint.json")
    validation_report = load_json(source_dir / "validation_report.json")

    # Check if run completed
    print("\n📋 RUN STATUS")
    print("-" * 70)

    if checkpoint:
        phase = checkpoint.get('phase', 'unknown')
        completed_count = len(checkpoint.get('completed_ids', []))
        failed_count = len(checkpoint.get('failed_ids', []))

        print(f"  Last phase: {phase}")
        print(f"  Completed: {completed_count}")
        print(f"  Failed: {failed_count}")

        if failed_count > 0:
            print(f"  ⚠️  {failed_count} grants failed to process")
            print(f"     Failed IDs: {checkpoint.get('failed_ids', [])[:10]}")
            if failed_count > 10:
                print(f"     ... and {failed_count - 10} more")
    else:
        print("  ⚠️  No checkpoint file found")

    # Audit log analysis
    print("\n📊 AUDIT LOG ANALYSIS")
    print("-" * 70)

    audit_file = source_dir / "audit_log.jsonl"
    if audit_file.exists():
        events = []
        with open(audit_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        event_counts = Counter(e['event_type'] for e in events)
        print(f"  Total events: {len(events)}")
        print(f"  Event breakdown:")
        for event_type, count in event_counts.most_common():
            print(f"    {event_type}: {count}")

        # Check for errors
        errors = [e for e in events if 'error' in e['event_type'].lower()]
        if errors:
            print(f"\n  ⚠️  Found {len(errors)} error events:")
            for err in errors[:5]:
                print(f"    - {err.get('details', {})}")
    else:
        print("  ⚠️  No audit log found")

    # Data quality analysis
    print("\n🔍 DATA QUALITY ANALYSIS")
    print("-" * 70)

    if raw_index:
        print(f"  Raw index records: {len(raw_index)}")
    else:
        print("  ⚠️  No raw index found")

    if normalized:
        print(f"  Normalized grants: {len(normalized)}")

        # Field completeness
        field_counts = defaultdict(int)
        for grant in normalized:
            for field in ['title', 'url', 'status', 'programme', 'open_date', 'close_date']:
                if grant.get(field):
                    field_counts[field] += 1

        print(f"\n  Field completeness:")
        total = len(normalized)
        for field, count in sorted(field_counts.items()):
            pct = (count / total) * 100 if total > 0 else 0
            print(f"    {field}: {count}/{total} ({pct:.1f}%)")

        # Status distribution
        statuses = [g.get('status') for g in normalized if g.get('status')]
        if statuses:
            status_counts = Counter(statuses)
            print(f"\n  Status distribution:")
            for status, count in status_counts.most_common():
                pct = (count / len(statuses)) * 100
                print(f"    {status}: {count} ({pct:.1f}%)")

        # Programme distribution
        programmes = [g.get('programme') for g in normalized if g.get('programme')]
        if programmes:
            prog_counts = Counter(programmes)
            print(f"\n  Programme distribution (top 5):")
            for prog, count in prog_counts.most_common(5):
                pct = (count / len(programmes)) * 100
                print(f"    {prog[:50]}: {count} ({pct:.1f}%)")

        # Title quality checks
        print(f"\n  Title quality:")
        empty_titles = [g for g in normalized if not g.get('title') or len(g['title'].strip()) == 0]
        short_titles = [g for g in normalized if g.get('title') and len(g['title']) < 10]
        encoding_issues = [g for g in normalized if g.get('title') and any(c in g['title'] for c in ['�', '\x00'])]

        print(f"    Empty titles: {len(empty_titles)}")
        print(f"    Very short titles (<10 chars): {len(short_titles)}")
        print(f"    Encoding issues: {len(encoding_issues)}")

        if empty_titles:
            print(f"      Examples: {[g.get('id') for g in empty_titles[:3]]}")

        # Date validation
        print(f"\n  Date validation:")
        invalid_dates = []
        for grant in normalized:
            for date_field in ['open_date', 'close_date']:
                date_val = grant.get(date_field)
                if date_val:
                    # Check ISO format
                    if not re.match(r'\d{4}-\d{2}-\d{2}', date_val):
                        invalid_dates.append({
                            'grant_id': grant.get('id'),
                            'field': date_field,
                            'value': date_val
                        })

        print(f"    Invalid date formats: {len(invalid_dates)}")
        if invalid_dates:
            print(f"      Examples: {invalid_dates[:3]}")
    else:
        print("  ⚠️  No normalized data found")

    # Validation report summary
    if validation_report:
        print(f"\n📝 VALIDATION REPORT")
        print("-" * 70)

        total_grants = validation_report.get('total_grants', 0)
        issues_found = validation_report.get('issues_found', {})

        print(f"  Total grants validated: {total_grants}")
        print(f"  Issues found:")
        for issue_type, count in issues_found.items():
            print(f"    {issue_type}: {count}")

    # HTML cache check
    html_dir = source_dir / "html"
    if html_dir.exists():
        html_files = list(html_dir.glob("*.html"))
        print(f"\n💾 HTML CACHE")
        print("-" * 70)
        print(f"  Cached HTML files: {len(html_files)}")

        if html_files:
            # Sample file sizes
            sizes = [f.stat().st_size for f in html_files[:100]]
            avg_size = sum(sizes) / len(sizes) if sizes else 0
            print(f"  Average size (first 100): {avg_size/1024:.1f} KB")
            print(f"  Min: {min(sizes)/1024:.1f} KB, Max: {max(sizes)/1024:.1f} KB")

            # Check for suspiciously small files
            small_files = [f for f in html_files if f.stat().st_size < 1000]
            if small_files:
                print(f"  ⚠️  {len(small_files)} files < 1KB (possibly errors)")

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    if normalized and raw_index:
        coverage = (len(normalized) / len(raw_index)) * 100 if len(raw_index) > 0 else 0
        print(f"  Coverage: {len(normalized)}/{len(raw_index)} ({coverage:.1f}%)")

    if checkpoint:
        failed = len(checkpoint.get('failed_ids', []))
        if failed == 0:
            print(f"  ✅ All grants processed successfully")
        else:
            print(f"  ⚠️  {failed} grants failed")

    print()


def main():
    if len(sys.argv) > 1:
        source = sys.argv[1].lower()
    else:
        source = "all"

    data_dir = Path("data")

    if source in ["horizon", "all"]:
        validate_source(data_dir / "horizon_europe")

    if source in ["digital", "all"]:
        validate_source(data_dir / "digital_europe")

    print("\n" + "="*70)
    print("Validation complete!")
    print("="*70)


if __name__ == "__main__":
    main()
