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
"""

import json
import sys
from pathlib import Path
from typing import Any

DATA_FILE = Path("/config/local_data/asm/data.json")


def load_data() -> dict[str, Any]:
    """Load data from JSON file."""
    if not DATA_FILE.exists():
        return {"assets": {}, "parts": {}, "service_events": [], "transactions": []}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"assets": {}, "parts": {}, "service_events": [], "transactions": []}


def main() -> int:
    data = load_data()

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

    # Build categories list
    asset_categories = ["Tractor", "Pump", "Harvester", "Vehicle"]
    part_categories = ["Filter", "Belt", "Oil", "Grease", "Battery", "Tyre", "Hose"]
    service_types = [
        "250 Hr Service",
        "500 Hr Service",
        "1000 Hr Service",
        "Annual Service",
        "Repair",
        "Inspection",
        "Other",
    ]

    output = {
        "total_assets": len(assets),
        "total_parts": len(parts),
        "low_stock_count": low_stock_count,
        "assets": assets,
        "parts": parts,
        "asset_names": asset_names,
        "part_names": part_names,
        "asset_id_to_name": asset_id_to_name,
        "part_id_to_name": part_id_to_name,
        "recent_events": recent_events,
        "asset_categories": asset_categories,
        "part_categories": part_categories,
        "service_types": service_types,
    }

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
