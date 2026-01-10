#!/usr/bin/env python3
"""
ASM Backend - Asset Service Manager
PaddiSense Farm Management System

This script handles all write operations for the asset service system:
  - add_asset / edit_asset / delete_asset: Asset management
  - add_part / edit_part / delete_part: Part management
  - adjust_stock: Manual stock adjustments
  - record_service: Record service events (auto-deducts parts)

Data is stored in: /config/local_data/asm/data.json
This file is NOT tracked in git - each farm maintains their own data.

Usage:
  python3 asm_backend.py add_asset --name "Tractor 1" --category "Tractor" --attributes '{"tyre_size": "18.4-38"}'
  python3 asm_backend.py add_part --name "Oil Filter" --category "Filter" --stock 5 --assets '["TRACTOR_1"]'
  python3 asm_backend.py record_service --asset "TRACTOR_1" --type "250 Hr Service" --parts '[{"part_id": "OIL_FILTER", "quantity": 1}]'
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Data file location (outside of git-tracked folders)
DATA_FILE = Path("/config/local_data/asm/data.json")

# Valid categories
ASSET_CATEGORIES = ["Tractor", "Pump", "Harvester", "Vehicle"]
PART_CATEGORIES = ["Filter", "Belt", "Oil", "Grease", "Battery", "Tyre", "Hose"]
SERVICE_TYPES = [
    "250 Hr Service",
    "500 Hr Service",
    "1000 Hr Service",
    "Annual Service",
    "Repair",
    "Inspection",
    "Other",
]
PART_UNITS = ["ea", "L", "kg", "m"]


def generate_id(name: str) -> str:
    """Generate a clean ID from the name."""
    clean = re.sub(r"[^A-Z0-9]+", "_", name.upper())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean[:30] if clean else "UNKNOWN"


def load_data() -> dict[str, Any]:
    """Load data from JSON file, or return empty structure."""
    if not DATA_FILE.exists():
        return {"assets": {}, "parts": {}, "service_events": [], "transactions": []}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"assets": {}, "parts": {}, "service_events": [], "transactions": []}


def save_data(data: dict[str, Any]) -> None:
    """Save data to JSON file."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def log_transaction(
    data: dict,
    action: str,
    entity_type: str,
    entity_id: str,
    entity_name: str,
    details: str = "",
) -> None:
    """Append a transaction record for audit trail."""
    data.setdefault("transactions", []).append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "details": details,
        }
    )


# =============================================================================
# ASSET COMMANDS
# =============================================================================


def cmd_add_asset(args: argparse.Namespace) -> int:
    """Add a new asset."""
    data = load_data()
    assets = data.setdefault("assets", {})

    asset_id = generate_id(args.name)
    if asset_id in assets:
        print(f"ERROR: Asset '{asset_id}' already exists", file=sys.stderr)
        return 1

    category = args.category.strip() if args.category else "Tractor"
    if category not in ASSET_CATEGORIES:
        print(f"ERROR: Invalid category '{category}'", file=sys.stderr)
        return 1

    # Parse attributes JSON
    attributes = {}
    if args.attributes and args.attributes.strip():
        try:
            parsed = json.loads(args.attributes)
            if isinstance(parsed, dict):
                attributes = {
                    str(k).strip(): str(v).strip()
                    for k, v in parsed.items()
                    if str(k).strip()
                }
        except json.JSONDecodeError:
            pass

    asset = {
        "id": asset_id,
        "name": args.name.strip(),
        "category": category,
        "attributes": attributes,
        "created": datetime.now().isoformat(timespec="seconds"),
    }

    assets[asset_id] = asset
    log_transaction(data, "add_asset", "asset", asset_id, asset["name"])
    save_data(data)

    print(f"OK:{asset_id}")
    return 0


def cmd_edit_asset(args: argparse.Namespace) -> int:
    """Edit an existing asset."""
    data = load_data()
    assets = data.get("assets", {})

    asset_id = args.id.strip().upper()
    if asset_id not in assets:
        print(f"ERROR: Asset '{asset_id}' not found", file=sys.stderr)
        return 1

    asset = assets[asset_id]

    if args.name:
        asset["name"] = args.name.strip()

    if args.category:
        category = args.category.strip()
        if category not in ASSET_CATEGORIES:
            print(f"ERROR: Invalid category '{category}'", file=sys.stderr)
            return 1
        asset["category"] = category

    if args.attributes is not None and args.attributes.strip():
        try:
            parsed = json.loads(args.attributes)
            if isinstance(parsed, dict):
                asset["attributes"] = {
                    str(k).strip(): str(v).strip()
                    for k, v in parsed.items()
                    if str(k).strip()
                }
        except json.JSONDecodeError:
            pass

    asset["modified"] = datetime.now().isoformat(timespec="seconds")

    log_transaction(data, "edit_asset", "asset", asset_id, asset["name"])
    save_data(data)

    print(f"OK:{asset_id}")
    return 0


def cmd_delete_asset(args: argparse.Namespace) -> int:
    """Delete an asset."""
    data = load_data()
    assets = data.get("assets", {})

    asset_id = args.id.strip().upper()
    if asset_id not in assets:
        print(f"ERROR: Asset '{asset_id}' not found", file=sys.stderr)
        return 1

    asset_name = assets[asset_id].get("name", asset_id)
    del assets[asset_id]

    log_transaction(data, "delete_asset", "asset", asset_id, asset_name)
    save_data(data)

    print("OK:deleted")
    return 0


# =============================================================================
# PART COMMANDS
# =============================================================================


def cmd_add_part(args: argparse.Namespace) -> int:
    """Add a new part."""
    data = load_data()
    parts = data.setdefault("parts", {})

    part_id = generate_id(args.name)
    if part_id in parts:
        print(f"ERROR: Part '{part_id}' already exists", file=sys.stderr)
        return 1

    category = args.category.strip() if args.category else "Filter"
    if category not in PART_CATEGORIES:
        print(f"ERROR: Invalid category '{category}'", file=sys.stderr)
        return 1

    unit = args.unit.strip() if args.unit else "ea"
    if unit not in PART_UNITS:
        unit = "ea"

    # Parse applicable assets
    applicable_assets = []
    if args.assets and args.assets.strip():
        try:
            parsed = json.loads(args.assets)
            if isinstance(parsed, list):
                applicable_assets = [str(a).strip().upper() for a in parsed if a]
        except json.JSONDecodeError:
            pass

    # Parse attributes JSON
    attributes = {}
    if args.attributes and args.attributes.strip():
        try:
            parsed = json.loads(args.attributes)
            if isinstance(parsed, dict):
                attributes = {
                    str(k).strip(): str(v).strip()
                    for k, v in parsed.items()
                    if str(k).strip()
                }
        except json.JSONDecodeError:
            pass

    part = {
        "id": part_id,
        "name": args.name.strip(),
        "part_number": args.part_number.strip() if args.part_number else "",
        "category": category,
        "applicable_assets": applicable_assets,
        "universal": bool(args.universal) if hasattr(args, "universal") else False,
        "attributes": attributes,
        "stock": float(args.stock) if args.stock else 0,
        "min_stock": float(args.min_stock) if args.min_stock else 0,
        "unit": unit,
        "created": datetime.now().isoformat(timespec="seconds"),
    }

    parts[part_id] = part
    log_transaction(
        data,
        "add_part",
        "part",
        part_id,
        part["name"],
        f"Initial stock: {part['stock']} {unit}",
    )
    save_data(data)

    print(f"OK:{part_id}")
    return 0


def cmd_edit_part(args: argparse.Namespace) -> int:
    """Edit an existing part."""
    data = load_data()
    parts = data.get("parts", {})

    part_id = args.id.strip().upper()
    if part_id not in parts:
        print(f"ERROR: Part '{part_id}' not found", file=sys.stderr)
        return 1

    part = parts[part_id]

    if args.name:
        part["name"] = args.name.strip()

    if args.part_number is not None:
        part["part_number"] = args.part_number.strip()

    if args.category:
        category = args.category.strip()
        if category not in PART_CATEGORIES:
            print(f"ERROR: Invalid category '{category}'", file=sys.stderr)
            return 1
        part["category"] = category

    if args.unit:
        unit = args.unit.strip()
        if unit in PART_UNITS:
            part["unit"] = unit

    if args.min_stock is not None:
        part["min_stock"] = float(args.min_stock)

    if args.assets is not None and args.assets.strip():
        try:
            parsed = json.loads(args.assets)
            if isinstance(parsed, list):
                part["applicable_assets"] = [
                    str(a).strip().upper() for a in parsed if a
                ]
        except json.JSONDecodeError:
            pass

    if hasattr(args, "universal") and args.universal is not None:
        part["universal"] = args.universal.lower() in ("true", "1", "yes")

    if args.attributes is not None and args.attributes.strip():
        try:
            parsed = json.loads(args.attributes)
            if isinstance(parsed, dict):
                part["attributes"] = {
                    str(k).strip(): str(v).strip()
                    for k, v in parsed.items()
                    if str(k).strip()
                }
        except json.JSONDecodeError:
            pass

    part["modified"] = datetime.now().isoformat(timespec="seconds")

    log_transaction(data, "edit_part", "part", part_id, part["name"])
    save_data(data)

    print(f"OK:{part_id}")
    return 0


def cmd_delete_part(args: argparse.Namespace) -> int:
    """Delete a part."""
    data = load_data()
    parts = data.get("parts", {})

    part_id = args.id.strip().upper()
    if part_id not in parts:
        print(f"ERROR: Part '{part_id}' not found", file=sys.stderr)
        return 1

    part_name = parts[part_id].get("name", part_id)
    del parts[part_id]

    log_transaction(data, "delete_part", "part", part_id, part_name)
    save_data(data)

    print("OK:deleted")
    return 0


def cmd_adjust_stock(args: argparse.Namespace) -> int:
    """Adjust stock level for a part."""
    data = load_data()
    parts = data.get("parts", {})

    part_id = args.id.strip().upper()
    if part_id not in parts:
        print(f"ERROR: Part '{part_id}' not found", file=sys.stderr)
        return 1

    part = parts[part_id]
    delta = float(args.delta)

    if delta == 0:
        print("OK:0")
        return 0

    current = float(part.get("stock", 0))
    new_stock = max(0, current + delta)
    part["stock"] = new_stock

    log_transaction(
        data,
        "stock_adjust",
        "part",
        part_id,
        part["name"],
        f"Changed by {delta:+.1f} (was {current:.1f}, now {new_stock:.1f})",
    )
    save_data(data)

    print(f"OK:{new_stock}")
    return 0


# =============================================================================
# SERVICE EVENT COMMANDS
# =============================================================================


def cmd_record_service(args: argparse.Namespace) -> int:
    """Record a service event and auto-deduct parts."""
    data = load_data()
    assets = data.get("assets", {})
    parts = data.get("parts", {})

    asset_id = args.asset.strip().upper()
    if asset_id not in assets:
        print(f"ERROR: Asset '{asset_id}' not found", file=sys.stderr)
        return 1

    service_type = args.type.strip() if args.type else "Other"
    if service_type not in SERVICE_TYPES:
        service_type = "Other"

    # Parse parts consumed
    parts_consumed = []
    if args.parts and args.parts.strip():
        try:
            parsed = json.loads(args.parts)
            if isinstance(parsed, list):
                for item in parsed:
                    pid = str(item.get("part_id", "")).strip().upper()
                    qty = float(item.get("quantity", 0))
                    if pid and pid in parts and qty > 0:
                        parts_consumed.append({"part_id": pid, "quantity": qty})
        except json.JSONDecodeError:
            pass

    # Generate service event ID
    timestamp = datetime.now()
    event_id = f"SE_{timestamp.strftime('%Y%m%d')}_{len(data.get('service_events', [])) + 1:03d}"

    event = {
        "id": event_id,
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "asset_id": asset_id,
        "asset_name": assets[asset_id].get("name", asset_id),
        "service_type": service_type,
        "parts_consumed": parts_consumed,
        "notes": args.notes.strip() if args.notes else "",
        "engine_hours": args.hours.strip() if args.hours else "",
    }

    # Auto-deduct parts from stock
    deducted = []
    for pc in parts_consumed:
        part = parts.get(pc["part_id"])
        if part:
            current = float(part.get("stock", 0))
            new_stock = max(0, current - pc["quantity"])
            part["stock"] = new_stock
            deducted.append(f"{part['name']} x{pc['quantity']}")

    data.setdefault("service_events", []).append(event)

    log_transaction(
        data,
        "record_service",
        "service",
        event_id,
        f"{service_type} on {event['asset_name']}",
        f"Parts: {', '.join(deducted) if deducted else 'None'}",
    )
    save_data(data)

    print(f"OK:{event_id}")
    return 0


# =============================================================================
# ARGUMENT PARSER
# =============================================================================


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="asm_backend.py", description="ASM Asset Service Backend - PaddiSense"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add_asset
    add_asset = subparsers.add_parser("add_asset", help="Add a new asset")
    add_asset.add_argument("--name", required=True, help="Asset name")
    add_asset.add_argument("--category", default="Tractor", help="Asset category")
    add_asset.add_argument("--attributes", default="", help="Attributes as JSON object")
    add_asset.set_defaults(func=cmd_add_asset)

    # edit_asset
    edit_asset = subparsers.add_parser("edit_asset", help="Edit an asset")
    edit_asset.add_argument("--id", required=True, help="Asset ID")
    edit_asset.add_argument("--name", help="New name")
    edit_asset.add_argument("--category", help="New category")
    edit_asset.add_argument("--attributes", help="New attributes as JSON object")
    edit_asset.set_defaults(func=cmd_edit_asset)

    # delete_asset
    del_asset = subparsers.add_parser("delete_asset", help="Delete an asset")
    del_asset.add_argument("--id", required=True, help="Asset ID")
    del_asset.set_defaults(func=cmd_delete_asset)

    # add_part
    add_part = subparsers.add_parser("add_part", help="Add a new part")
    add_part.add_argument("--name", required=True, help="Part name")
    add_part.add_argument("--part_number", default="", help="Part number")
    add_part.add_argument("--category", default="Filter", help="Part category")
    add_part.add_argument("--unit", default="ea", help="Unit (ea, L, kg, m)")
    add_part.add_argument("--stock", type=float, default=0, help="Initial stock")
    add_part.add_argument("--min_stock", type=float, default=0, help="Minimum stock")
    add_part.add_argument("--assets", default="", help="Applicable assets as JSON array")
    add_part.add_argument("--universal", default="false", help="Applies to all assets")
    add_part.add_argument("--attributes", default="", help="Attributes as JSON object")
    add_part.set_defaults(func=cmd_add_part)

    # edit_part
    edit_part = subparsers.add_parser("edit_part", help="Edit a part")
    edit_part.add_argument("--id", required=True, help="Part ID")
    edit_part.add_argument("--name", help="New name")
    edit_part.add_argument("--part_number", help="New part number")
    edit_part.add_argument("--category", help="New category")
    edit_part.add_argument("--unit", help="New unit")
    edit_part.add_argument("--min_stock", type=float, help="New minimum stock")
    edit_part.add_argument("--assets", help="New applicable assets as JSON array")
    edit_part.add_argument("--universal", help="Applies to all assets (true/false)")
    edit_part.add_argument("--attributes", help="New attributes as JSON object")
    edit_part.set_defaults(func=cmd_edit_part)

    # delete_part
    del_part = subparsers.add_parser("delete_part", help="Delete a part")
    del_part.add_argument("--id", required=True, help="Part ID")
    del_part.set_defaults(func=cmd_delete_part)

    # adjust_stock
    adj_stock = subparsers.add_parser("adjust_stock", help="Adjust part stock")
    adj_stock.add_argument("--id", required=True, help="Part ID")
    adj_stock.add_argument("--delta", type=float, required=True, help="Change amount")
    adj_stock.set_defaults(func=cmd_adjust_stock)

    # record_service
    rec_svc = subparsers.add_parser("record_service", help="Record a service event")
    rec_svc.add_argument("--asset", required=True, help="Asset ID")
    rec_svc.add_argument("--type", default="Other", help="Service type")
    rec_svc.add_argument("--parts", default="", help="Parts consumed as JSON array")
    rec_svc.add_argument("--notes", default="", help="Service notes")
    rec_svc.add_argument("--hours", default="", help="Engine hours at service")
    rec_svc.set_defaults(func=cmd_record_service)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
