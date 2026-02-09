#!/usr/bin/env python3
"""
HFM Sensor - Hey Farmer Module
Read-only sensor providing event data and configuration.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Paths
DATA_DIR = Path("/config/local_data/hfm")
CONFIG_FILE = DATA_DIR / "config.json"
EVENTS_FILE = DATA_DIR / "events.json"
APPLICATORS_FILE = DATA_DIR / "applicators.json"
BACKUPS_DIR = DATA_DIR / "backups"
VERSION_FILE = Path("/config/PaddiSense/hfm/VERSION")
REGISTRY_FILE = Path("/config/local_data/registry/config.json")
IPM_INVENTORY_FILE = Path("/config/local_data/ipm/inventory.json")


def get_version() -> str:
    """Get module version."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except (IOError, FileNotFoundError):
        return "unknown"


def load_json(path: Path, default: Any = None) -> Any:
    """Load JSON file, returning default if not found or invalid."""
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return default


def get_paddock_names() -> dict:
    """Get paddock ID to name mapping from Registry."""
    registry = load_json(REGISTRY_FILE, {})
    paddocks = registry.get("paddocks", {})
    return {pid: p.get("name", pid) for pid, p in paddocks.items()}


def get_product_names() -> list:
    """Get product names from IPM inventory, filtered by Fertiliser and Chemical categories."""
    ipm_inventory = load_json(IPM_INVENTORY_FILE, {})
    products = ipm_inventory.get("products", {})
    # Filter to only Fertiliser and Chemical categories (relevant for farm events)
    relevant_categories = {"Fertiliser", "Chemical"}
    return sorted([
        p.get("name", pid)
        for pid, p in products.items()
        if p.get("category") in relevant_categories
    ])


def get_backup_info() -> dict:
    """Get info about latest backup."""
    if not BACKUPS_DIR.exists():
        return {"last_backup": None, "backup_count": 0}

    backups = sorted(BACKUPS_DIR.glob("hfm_export_*.json"), reverse=True)
    if not backups:
        return {"last_backup": None, "backup_count": 0}

    # Get latest backup timestamp from filename
    latest = backups[0].name
    # Parse: hfm_export_20260207_143522.json
    try:
        ts_part = latest.replace("hfm_export_", "").replace(".json", "")
        dt = datetime.strptime(ts_part, "%Y%m%d_%H%M%S")
        last_backup = dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        last_backup = latest

    return {"last_backup": last_backup, "backup_count": len(backups)}


def get_applicators() -> dict:
    """Get applicator data for dropdowns and UI."""
    data = load_json(APPLICATORS_FILE, {"applicators": [], "attribute_templates": {}})
    applicators = data.get("applicators", [])
    templates = data.get("attribute_templates", {})

    # Active applicators only for dropdowns
    active_applicators = [a for a in applicators if a.get("active", True)]

    # Group by type for filtering
    by_type = {}
    for app in active_applicators:
        app_type = app.get("type", "unknown")
        if app_type not in by_type:
            by_type[app_type] = []
        by_type[app_type].append({
            "id": app["id"],
            "name": app["name"],
            "type": app_type
        })

    return {
        "applicators": applicators,
        "active_applicators": active_applicators,
        "applicators_by_type": by_type,
        "applicator_names": [a["name"] for a in active_applicators],
        "applicator_ids": [a["id"] for a in active_applicators],
        "attribute_templates": templates
    }


def main():
    config = load_json(CONFIG_FILE, {})
    events_data = load_json(EVENTS_FILE, {"events": []})
    events = events_data.get("events", [])

    # Get today's date
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Count events
    total_events = len(events)
    events_today = sum(1 for e in events if e.get("event_date") == today)
    events_yesterday = sum(1 for e in events if e.get("event_date") == yesterday)
    pending_events = sum(1 for e in events if e.get("confirmation_status") == "pending")

    # Events by type
    events_by_type = {}
    for e in events:
        etype = e.get("event_type", "unknown")
        events_by_type[etype] = events_by_type.get(etype, 0) + 1

    # Events by paddock
    events_by_paddock = {}
    for e in events:
        for pid in e.get("paddocks", []):
            events_by_paddock[pid] = events_by_paddock.get(pid, 0) + 1

    # Recent events (last 20, sorted by recorded_at descending)
    sorted_events = sorted(events, key=lambda x: x.get("recorded_at", ""), reverse=True)
    recent_events = sorted_events[:20]

    # Pending events
    pending_list = [e for e in sorted_events if e.get("confirmation_status") == "pending"]

    # Get paddock names for display
    paddock_names = get_paddock_names()
    paddock_list = sorted(paddock_names.values()) if paddock_names else []

    # Get product names from IPM
    product_names = get_product_names()

    # Config items for dropdowns
    crop_stages = config.get("crop_stages", [])
    application_methods = config.get("application_methods", [])
    irrigation_types = config.get("irrigation_types", [])
    devices = config.get("devices", {})

    # Backup info
    backup_info = get_backup_info()

    # Applicator info
    applicator_info = get_applicators()

    # Determine system status
    if not CONFIG_FILE.exists():
        system_status = "not_initialized"
    elif not events:
        system_status = "ready_no_events"
    else:
        system_status = "ready"

    # Build output
    output = {
        # Main state value
        "total_events": total_events,

        # Event counts
        "events_today": events_today,
        "events_yesterday": events_yesterday,
        "pending_events": pending_events,

        # Event lists
        "recent_events": recent_events,
        "pending_list": pending_list,
        "all_events": sorted_events,

        # Aggregations
        "events_by_type": events_by_type,
        "events_by_paddock": events_by_paddock,

        # Config items
        "crop_stages": crop_stages,
        "application_methods": application_methods,
        "irrigation_types": irrigation_types,
        "devices": devices,

        # Integration data
        "paddock_names": paddock_list,
        "paddock_map": paddock_names,
        "product_names": product_names,

        # Lists for dropdowns
        "crop_stage_names": [s.get("name") for s in crop_stages],
        "crop_stage_ids": [s.get("id") for s in crop_stages],
        "method_names": [m.get("name") for m in application_methods],
        "method_ids": [m.get("id") for m in application_methods],
        "irrigation_names": [i.get("name") for i in irrigation_types],
        "irrigation_ids": [i.get("id") for i in irrigation_types],

        # System info
        "system_status": system_status,
        "config_exists": CONFIG_FILE.exists(),
        "voice_enabled": config.get("voice_enabled", False),
        "weather_enabled": config.get("weather_enabled", False),
        "weather_entities": config.get("weather_entities", {}),
        "version": get_version(),

        # Backup info
        "last_backup": backup_info["last_backup"],
        "backup_count": backup_info["backup_count"],

        # Applicator info
        "applicators": applicator_info["applicators"],
        "active_applicators": applicator_info["active_applicators"],
        "applicators_by_type": applicator_info["applicators_by_type"],
        "applicator_names": applicator_info["applicator_names"],
        "applicator_ids": applicator_info["applicator_ids"],
        "applicator_templates": applicator_info["attribute_templates"],
    }

    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
