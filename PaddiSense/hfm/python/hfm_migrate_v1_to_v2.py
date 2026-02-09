#!/usr/bin/env python3
"""
HFM Event Migration Script: v1 -> v2

Migrates existing HFM events from v1 schema to v2 schema.

Changes:
- Add schema_version: "2.0.0"
- Convert paddocks array to single paddock object
- Add farm object from registry lookup
- Add batch_id/batch_index/batch_total (null for single paddock, generated for multi)
- Add application_timing with date
- Add weather: null
- Add applicator: null
- Convert recorded_by_device to operator object

Multi-paddock v1 events are expanded into multiple v2 events with batch_id linking.

Usage:
    python3 hfm_migrate_v1_to_v2.py [--dry-run]

Options:
    --dry-run    Show what would be changed without modifying files
"""

import json
import os
import sys
import shutil
from datetime import datetime
import random
import string

# Paths
EVENTS_FILE = "/config/local_data/hfm/events.json"
REGISTRY_FILE = "/config/local_data/registry/config.json"
BACKUP_DIR = "/config/local_data/hfm/backups"


def generate_id(prefix="batch_", length=8):
    """Generate a random ID."""
    chars = string.ascii_lowercase + string.digits
    return prefix + ''.join(random.choices(chars, k=length))


def load_json(path):
    """Load JSON file."""
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)


def save_json(path, data):
    """Save JSON file with pretty formatting."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def backup_file(path):
    """Create timestamped backup of file."""
    if not os.path.exists(path):
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    basename = os.path.basename(path).replace('.json', '')
    backup_path = os.path.join(BACKUP_DIR, f"{basename}_pre_v2_migration_{timestamp}.json")
    shutil.copy2(path, backup_path)
    return backup_path


def get_paddock_info(paddock_id, registry):
    """Get paddock name and area from registry."""
    paddocks = registry.get('paddocks', {})
    paddock = paddocks.get(paddock_id, {})
    return {
        "id": paddock_id,
        "name": paddock.get('name', paddock_id.upper()),
        "area_ha": paddock.get('area_ha', None)
    }


def get_farm_info(farm_id, registry):
    """Get farm info from registry."""
    farms = registry.get('farms', {})
    farm = farms.get(farm_id, {})
    return {
        "id": farm_id,
        "name": farm.get('name', farm_id)
    }


def get_farm_for_paddock(paddock_id, registry):
    """Look up farm_id for a paddock."""
    paddocks = registry.get('paddocks', {})
    paddock = paddocks.get(paddock_id, {})
    return paddock.get('farm_id', 'farm_1')


def migrate_event(event, registry):
    """
    Migrate a single v1 event to v2 format.

    Returns a list of events (may be multiple if multi-paddock).
    """
    # Skip if already v2
    if event.get('schema_version'):
        return [event]

    paddocks = event.get('paddocks', [])
    if not paddocks:
        paddocks = ['unknown']

    # Determine if we need batch expansion
    is_batch = len(paddocks) > 1
    batch_id = generate_id("batch_") if is_batch else None
    batch_total = len(paddocks) if is_batch else None

    migrated_events = []

    for idx, paddock_id in enumerate(paddocks, start=1):
        # Get registry info
        paddock_info = get_paddock_info(paddock_id, registry)
        farm_id = get_farm_for_paddock(paddock_id, registry)
        farm_info = get_farm_info(farm_id, registry)

        # Build new event
        new_event = {
            "id": event['id'] if len(paddocks) == 1 else generate_id("evt_"),
            "schema_version": "2.0.0",
            "batch_id": batch_id,
            "batch_index": idx if is_batch else None,
            "batch_total": batch_total,
            "event_type": event.get('event_type'),
            "farm": farm_info,
            "paddock": paddock_info,
            "application_timing": {
                "date": event.get('event_date')
            },
            "products": event.get('products', []),
            "applicator": None,
            "application_method": event.get('application_method'),
            "crop_stage": event.get('crop_stage'),
            "irrigation_type": event.get('irrigation_type'),
            "weather": None,
            "operator": {
                "device_id": event.get('recorded_by_device', 'unknown'),
                "user_name": ""
            },
            "notes": event.get('notes', ''),
            "confirmation_status": event.get('confirmation_status', 'confirmed'),
            "recorded_at": event.get('recorded_at'),
            "modified_at": event.get('modified_at')
        }

        # Preserve voice fields if present
        if event.get('voice_transcript'):
            new_event['voice_transcript'] = event['voice_transcript']
        if event.get('voice_source'):
            new_event['voice_source'] = event['voice_source']

        migrated_events.append(new_event)

    return migrated_events


def run_migration(dry_run=False):
    """Run the migration."""
    print("=" * 60)
    print("HFM Event Migration: v1 -> v2")
    print("=" * 60)

    # Load files
    events_data = load_json(EVENTS_FILE)
    if not events_data:
        print("ERROR: Could not load events file")
        return False

    registry = load_json(REGISTRY_FILE)
    if not registry:
        print("WARNING: Could not load registry, using defaults for paddock/farm names")
        registry = {"paddocks": {}, "farms": {}}

    events = events_data.get('events', [])
    print(f"\nFound {len(events)} events")

    # Count v1 vs v2
    v1_count = sum(1 for e in events if not e.get('schema_version'))
    v2_count = len(events) - v1_count
    print(f"  - v1 events (need migration): {v1_count}")
    print(f"  - v2 events (already migrated): {v2_count}")

    if v1_count == 0:
        print("\nNo events need migration. All events are already v2.")
        return True

    # Migrate events
    print(f"\nMigrating {v1_count} events...")

    migrated_events = []
    expansion_count = 0

    for event in events:
        if event.get('schema_version'):
            # Already v2, keep as-is
            migrated_events.append(event)
        else:
            # Migrate v1 to v2
            new_events = migrate_event(event, registry)
            migrated_events.extend(new_events)

            if len(new_events) > 1:
                expansion_count += 1
                print(f"  - Event {event['id']}: expanded {len(event.get('paddocks', []))} paddocks -> {len(new_events)} events")

    print(f"\nMigration summary:")
    print(f"  - Events before: {len(events)}")
    print(f"  - Events after: {len(migrated_events)}")
    print(f"  - Multi-paddock expansions: {expansion_count}")

    if dry_run:
        print("\n[DRY RUN] No changes made.")
        print("\nSample migrated event:")
        for e in migrated_events:
            if e.get('schema_version') == '2.0.0' and e.get('batch_id') is None:
                print(json.dumps(e, indent=2)[:1000])
                break
        return True

    # Backup original
    backup_path = backup_file(EVENTS_FILE)
    print(f"\nBackup created: {backup_path}")

    # Save migrated events
    events_data['events'] = migrated_events
    events_data['modified'] = datetime.now().isoformat()
    events_data['schema_version'] = '2.0.0'

    save_json(EVENTS_FILE, events_data)
    print(f"Migration complete! Saved to {EVENTS_FILE}")

    return True


def main():
    dry_run = '--dry-run' in sys.argv

    if dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    success = run_migration(dry_run=dry_run)

    if success:
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("Migration failed!")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
