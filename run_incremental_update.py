#!/usr/bin/env python3
"""
Incremental scraper that only fetches new/changed grants.
Perfect for scheduled cron jobs.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timezone
from scraper.pipelines import horizon_europe, digital_europe

# Check if we should use open-only mode
ONLY_OPEN_GRANTS = os.environ.get('ONLY_OPEN_GRANTS', 'false').lower() == 'true'

if ONLY_OPEN_GRANTS:
    from scraper.pipelines import horizon_europe_open, digital_europe_open
else:
    from scraper.pipelines import horizon_europe, digital_europe


def get_existing_grants(source_dir):
    """Load existing normalized grants"""
    normalized_file = Path(source_dir) / "normalized.json"

    if not normalized_file.exists():
        return {}

    grants = json.loads(normalized_file.read_text(encoding='utf-8'))

    # Create lookup by ID
    return {g['id']: g for g in grants}


def detect_changes(old_grants, new_grants):
    """Detect which grants are new or changed with detailed change tracking"""
    changes = {
        'new': [],
        'updated': [],
        'deleted': [],
        'details': {}  # Detailed change info
    }

    old_ids = set(old_grants.keys())
    new_ids = set(new_grants.keys())

    # New grants
    new_grant_ids = list(new_ids - old_ids)
    changes['new'] = new_grant_ids

    for grant_id in new_grant_ids:
        grant = new_grants[grant_id]
        changes['details'][grant_id] = {
            'change_type': 'new',
            'title': grant.get('title'),
            'status': grant.get('status'),
            'close_date': grant.get('close_date'),
            'open_date': grant.get('open_date'),
            'url': grant.get('url')
        }

    # Deleted/archived grants
    deleted_grant_ids = list(old_ids - new_ids)
    changes['deleted'] = deleted_grant_ids

    for grant_id in deleted_grant_ids:
        old_grant = old_grants[grant_id]
        changes['details'][grant_id] = {
            'change_type': 'deleted',
            'title': old_grant.get('title'),
            'was_status': old_grant.get('status')
        }

    # Updated grants (status or dates changed)
    for grant_id in old_ids & new_ids:
        old_grant = old_grants[grant_id]
        new_grant = new_grants[grant_id]

        changes_found = {}

        if old_grant.get('status') != new_grant.get('status'):
            changes_found['status'] = {
                'old': old_grant.get('status'),
                'new': new_grant.get('status')
            }

        if old_grant.get('close_date') != new_grant.get('close_date'):
            changes_found['close_date'] = {
                'old': old_grant.get('close_date'),
                'new': new_grant.get('close_date')
            }

        if old_grant.get('open_date') != new_grant.get('open_date'):
            changes_found['open_date'] = {
                'old': old_grant.get('open_date'),
                'new': new_grant.get('open_date')
            }

        if old_grant.get('title') != new_grant.get('title'):
            changes_found['title'] = {
                'old': old_grant.get('title'),
                'new': new_grant.get('title')
            }

        if changes_found:
            changes['updated'].append(grant_id)
            changes['details'][grant_id] = {
                'change_type': 'updated',
                'title': new_grant.get('title'),
                'url': new_grant.get('url'),
                'changes': changes_found
            }

    return changes


def run_incremental_scrape(programme_name, scraper_module, source_dir):
    """Run incremental scrape for a programme"""
    print(f"\n{'='*70}")
    print(f"Incremental Update: {programme_name}")
    print(f"{'='*70}")

    # Load existing grants
    old_grants = get_existing_grants(source_dir)
    print(f"📊 Existing grants: {len(old_grants)}")

    # Run full scrape (checkpoint system makes this efficient if run frequently)
    print(f"\n🚀 Running scraper for {programme_name}...")
    scraper_module.run()

    # Load new grants
    new_grants = get_existing_grants(source_dir)

    # Detect changes
    changes = detect_changes(old_grants, new_grants)

    # Report changes
    print(f"\n📊 Update Summary:")
    print(f"   Previous: {len(old_grants)} grants")
    print(f"   Current: {len(new_grants)} grants")
    print(f"   New: {len(changes['new'])} grants")
    print(f"   Updated: {len(changes['updated'])} grants")
    print(f"   Deleted/Archived: {len(changes['deleted'])} grants")

    # Save detailed update report with specific changes
    report = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'programme': programme_name,
        'previous_count': len(old_grants),
        'current_count': len(new_grants),
        'changes': {
            'new': len(changes['new']),
            'updated': len(changes['updated']),
            'deleted': len(changes['deleted'])
        },
        'new_grants': [
            changes['details'][gid] for gid in changes['new']
        ],
        'updated_grants': [
            changes['details'][gid] for gid in changes['updated']
        ],
        'deleted_grants': [
            changes['details'][gid] for gid in changes['deleted']
        ]
    }

    # Save report
    report_file = Path(source_dir) / f"update_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_file.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"\n💾 Report saved to: {report_file.name}")

    # Print detailed changes for logging
    if changes['new']:
        print(f"\n📝 New Grants:")
        for gid in changes['new'][:5]:  # Show first 5
            detail = changes['details'][gid]
            print(f"   • {detail['title'][:80]}... (Status: {detail['status']})")

    if changes['updated']:
        print(f"\n🔄 Updated Grants:")
        for gid in changes['updated'][:5]:  # Show first 5
            detail = changes['details'][gid]
            print(f"   • {detail['title'][:80]}...")
            for field, change in detail['changes'].items():
                print(f"     - {field}: {change['old']} → {change['new']}")

    if changes['deleted']:
        print(f"\n🗑️  Deleted/Closed Grants:")
        for gid in changes['deleted'][:5]:  # Show first 5
            detail = changes['details'][gid]
            print(f"   • {detail['title'][:80]}...")

    return changes


def main():
    print("="*70)
    print("INCREMENTAL SCRAPER UPDATE")
    print(f"Mode: {'OPEN GRANTS ONLY' if ONLY_OPEN_GRANTS else 'ALL STATUSES'}")
    print(f"Started at: {datetime.now()}")
    print("="*70)

    # Select appropriate scraper modules
    if ONLY_OPEN_GRANTS:
        horizon_module = horizon_europe_open
        digital_module = digital_europe_open
    else:
        horizon_module = horizon_europe
        digital_module = digital_europe

    # Run incremental updates
    horizon_changes = run_incremental_scrape(
        "Horizon Europe",
        horizon_module,
        "data/horizon_europe"
    )

    digital_changes = run_incremental_scrape(
        "Digital Europe",
        digital_module,
        "data/digital_europe"
    )

    # Summary
    total_new = len(horizon_changes['new']) + len(digital_changes['new'])
    total_updated = len(horizon_changes['updated']) + len(digital_changes['updated'])

    print("\n" + "="*70)
    print("✅ Update Complete!")
    print(f"   Total new grants: {total_new}")
    print(f"   Total updated grants: {total_updated}")
    print("="*70)


if __name__ == "__main__":
    main()
