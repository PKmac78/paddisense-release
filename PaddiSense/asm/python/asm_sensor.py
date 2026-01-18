#!/usr/bin/env python3
"""
ASM Sensor - Asset Service Manager
PaddiSense Farm Management System

This script provides read-only JSON output for the Home Assistant sensor.
It reads the data file and outputs computed values for the UI.

Output includes:
  - assets: All assets with their attributes
  - parts: All parts with stock levels
  - asset_names: List of asset names for dropdowns
  - part_names: List of part names for dropdowns
  - recent_events: Last 20 service events
  - low_stock_count: Number of parts below min_stock
  - initialized: System initialization status
  - config_ok / database_ok: File status
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("/config/local_data/asm")
DATA_FILE = DATA_DIR / "data.json"
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"

# Version file location (in module directory)
VERSION_FILE = Path("/config/PaddiSense/asm/VERSION")


def get_version() -> str:
    """Read module version from VERSION file."""
    try:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text(encoding="utf-8").strip()
    except IOError:
        pass
    return "unknown"

# Default categories
DEFAULT_ASSET_CATEGORIES = ["Tractor", "Pump", "Harvester", "Vehicle"]
DEFAULT_PART_CATEGORIES = ["Filter", "Belt", "Oil", "Grease", "Battery", "Tyre", "Hose"]
DEFAULT_SERVICE_TYPES = [
    "250 Hr Service",
    "500 Hr Service",
    "1000 Hr Service",
    "Annual Service",
    "Repair",
    "Inspection",
    "Other",
]
DEFAULT_PART_UNITS = ["ea", "L", "kg", "m"]


def load_data() -> dict[str, Any]:
    """Load data from JSON file."""
    if not DATA_FILE.exists():
        return {"assets": {}, "parts": {}, "service_events": [], "transactions": []}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"assets": {}, "parts": {}, "service_events": [], "transactions": []}


def load_config() -> dict[str, Any]:
    """Load config from JSON file."""
    if not CONFIG_FILE.exists():
        return {
            "asset_categories": DEFAULT_ASSET_CATEGORIES.copy(),
            "part_categories": DEFAULT_PART_CATEGORIES.copy(),
            "service_types": DEFAULT_SERVICE_TYPES.copy(),
            "part_units": DEFAULT_PART_UNITS.copy(),
        }
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {
            "asset_categories": DEFAULT_ASSET_CATEGORIES.copy(),
            "part_categories": DEFAULT_PART_CATEGORIES.copy(),
            "service_types": DEFAULT_SERVICE_TYPES.copy(),
            "part_units": DEFAULT_PART_UNITS.copy(),
        }


def main() -> int:
    data = load_data()
    config = load_config()

    # System status
    initialized = CONFIG_FILE.exists() or DATA_FILE.exists()
    config_ok = CONFIG_FILE.exists()
    database_ok = DATA_FILE.exists()

    assets = data.get("assets", {})
    parts = data.get("parts", {})
    service_events = data.get("service_events", [])

    # Build asset names list (sorted)
    asset_names = sorted([a.get("name", aid) for aid, a in assets.items()])

    # Build part names list (sorted)
    part_names = sorted([p.get("name", pid) for pid, p in parts.items()])

    # Build asset ID to name mapping
    asset_id_to_name = {aid: a.get("name", aid) for aid, a in assets.items()}

    # Build part ID to name mapping
    part_id_to_name = {pid: p.get("name", pid) for pid, p in parts.items()}

    # Count low stock parts
    low_stock_count = 0
    for pid, p in parts.items():
        stock = float(p.get("stock", 0))
        min_stock = float(p.get("min_stock", 0))
        if min_stock > 0 and stock < min_stock:
            low_stock_count += 1

    # Get recent service events (last 20, newest first)
    recent_events = sorted(
        service_events, key=lambda e: e.get("timestamp", ""), reverse=True
    )[:20]

    # Build service event labels for dropdown (date time - asset - type)
    event_labels = []
    event_id_to_label = {}
    for e in recent_events:
        ts_full = e.get("timestamp", "")
        # Include date and time (HH:MM) to avoid duplicates
        ts = ts_full[:16].replace("T", " ") if len(ts_full) >= 16 else ts_full[:10]
        asset = e.get("asset_name", e.get("asset_id", "Unknown"))
        stype = e.get("service_type", "Service")
        label = f"{ts} - {asset} - {stype}"
        event_labels.append(label)
        event_id_to_label[e.get("id", "")] = label

    # Build categories list (from config or defaults)
    asset_categories = config.get("asset_categories", DEFAULT_ASSET_CATEGORIES)
    part_categories = config.get("part_categories", DEFAULT_PART_CATEGORIES)
    service_types = config.get("service_types", DEFAULT_SERVICE_TYPES)
    part_units = config.get("part_units", DEFAULT_PART_UNITS)

    # Count backups
    backup_count = 0
    if BACKUP_DIR.exists():
        backup_count = len(list(BACKUP_DIR.glob("*.json")))

    # Get version
    version = get_version()

    output = {
        # System status
        "initialized": initialized,
        "config_ok": config_ok,
        "database_ok": database_ok,
        "status": "ready" if initialized else "not_initialized",
        "version": version,
        # Counts
        "total_assets": len(assets),
        "total_parts": len(parts),
        "total_services": len(service_events),
        "low_stock_count": low_stock_count,
        "transaction_count": len(data.get("transactions", [])),
        "backup_count": backup_count,
        # Data
        "assets": assets,
        "parts": parts,
        "asset_names": asset_names,
        "part_names": part_names,
        "asset_id_to_name": asset_id_to_name,
        "part_id_to_name": part_id_to_name,
        "recent_events": recent_events,
        "event_labels": event_labels,
        "event_id_to_label": event_id_to_label,
        # Categories (from config)
        "asset_categories": asset_categories,
        "part_categories": part_categories,
        "service_types": service_types,
        "part_units": part_units,
    }

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
