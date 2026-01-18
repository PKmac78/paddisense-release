#!/usr/bin/env python3
"""
ASM Backend - Asset Service Manager
PaddiSense Farm Management System

This script handles all write operations for the asset service system:
  - add_asset / edit_asset / delete_asset: Asset management
  - add_part / edit_part / delete_part: Part management
  - adjust_stock: Manual stock adjustments
  - record_service / delete_service: Record/delete service events
  - init / status: System initialization and status
  - export / import_backup / reset / backup_list: Data management

Data is stored in: /config/local_data/asm/data.json
Config is stored in: /config/local_data/asm/config.json
Backups are stored in: /config/local_data/asm/backups/

Usage:
  python3 asm_backend.py init
  python3 asm_backend.py status
  python3 asm_backend.py add_asset --name "Tractor 1" --category "Tractor" --attributes '{"tyre_size": "18.4-38"}'
  python3 asm_backend.py add_part --name "Oil Filter" --category "Filter" --stock 5 --assets '["TRACTOR_1"]'
  python3 asm_backend.py record_service --asset "TRACTOR_1" --type "250 Hr Service" --parts '[{"part_id": "OIL_FILTER", "quantity": 1}]'
  python3 asm_backend.py export
  python3 asm_backend.py import_backup --filename "backup_2026-01-17_120000.json"
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# File locations (outside of git-tracked folders)
DATA_DIR = Path("/config/local_data/asm")
DATA_FILE = DATA_DIR / "data.json"
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"

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

# Valid categories (will be loaded from config if available)
ASSET_CATEGORIES = DEFAULT_ASSET_CATEGORIES.copy()
PART_CATEGORIES = DEFAULT_PART_CATEGORIES.copy()
SERVICE_TYPES = DEFAULT_SERVICE_TYPES.copy()
PART_UNITS = DEFAULT_PART_UNITS.copy()


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


def load_config() -> dict[str, Any]:
    """Load config from JSON file, or return default structure."""
    if not CONFIG_FILE.exists():
        return {
            "asset_categories": DEFAULT_ASSET_CATEGORIES.copy(),
            "part_categories": DEFAULT_PART_CATEGORIES.copy(),
            "service_types": DEFAULT_SERVICE_TYPES.copy(),
            "part_units": DEFAULT_PART_UNITS.copy(),
            "created": datetime.now().isoformat(timespec="seconds"),
        }
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {
            "asset_categories": DEFAULT_ASSET_CATEGORIES.copy(),
            "part_categories": DEFAULT_PART_CATEGORIES.copy(),
            "service_types": DEFAULT_SERVICE_TYPES.copy(),
            "part_units": DEFAULT_PART_UNITS.copy(),
            "created": datetime.now().isoformat(timespec="seconds"),
        }


def save_config(config: dict[str, Any]) -> None:
    """Save config to JSON file."""
    config["modified"] = datetime.now().isoformat(timespec="seconds")
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
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


def cmd_delete_service(args: argparse.Namespace) -> int:
    """Delete a service event."""
    data = load_data()
    service_events = data.get("service_events", [])

    event_id = args.id.strip()
    if not event_id:
        print("ERROR: Event ID is required", file=sys.stderr)
        return 1

    # Find the event
    found_idx = None
    event_info = ""
    for idx, event in enumerate(service_events):
        if event.get("id") == event_id:
            found_idx = idx
            event_info = f"{event.get('service_type', 'Service')} on {event.get('asset_name', event.get('asset_id', 'Unknown'))}"
            break

    if found_idx is None:
        print(f"ERROR: Service event '{event_id}' not found", file=sys.stderr)
        return 1

    # Remove the event
    del service_events[found_idx]

    log_transaction(data, "delete_service", "service", event_id, event_info)
    save_data(data)

    print("OK:deleted")
    return 0


# =============================================================================
# SYSTEM MANAGEMENT COMMANDS
# =============================================================================


def cmd_status(args: argparse.Namespace) -> int:
    """Get system status (for Settings page)."""
    status = {
        "initialized": False,
        "config_ok": False,
        "database_ok": False,
        "asset_count": 0,
        "part_count": 0,
        "service_count": 0,
        "transaction_count": 0,
        "low_stock_count": 0,
        "status": "not_initialized",
    }

    # Check config
    if CONFIG_FILE.exists():
        try:
            config = load_config()
            status["config_ok"] = True
            status["asset_categories"] = config.get("asset_categories", DEFAULT_ASSET_CATEGORIES)
            status["part_categories"] = config.get("part_categories", DEFAULT_PART_CATEGORIES)
            status["service_types"] = config.get("service_types", DEFAULT_SERVICE_TYPES)
        except Exception:
            status["status"] = "error"
            status["error"] = "Config file corrupted"
            print(json.dumps(status))
            return 0

    # Check database
    if DATA_FILE.exists():
        try:
            data = load_data()
            assets = data.get("assets", {})
            parts = data.get("parts", {})
            events = data.get("service_events", [])

            status["database_ok"] = True
            status["asset_count"] = len(assets)
            status["part_count"] = len(parts)
            status["service_count"] = len(events)
            status["transaction_count"] = len(data.get("transactions", []))

            # Count low stock parts
            low_stock = 0
            for part in parts.values():
                stock = float(part.get("stock", 0))
                min_stock = float(part.get("min_stock", 0))
                if min_stock > 0 and stock < min_stock:
                    low_stock += 1
            status["low_stock_count"] = low_stock

            status["initialized"] = True
            status["status"] = "ready"
        except Exception as e:
            status["status"] = "error"
            status["error"] = f"Database file corrupted: {e}"
    elif CONFIG_FILE.exists():
        # Config exists but no database - still considered initialized
        status["initialized"] = True
        status["status"] = "ready"

    print(json.dumps(status))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize the ASM system - create config and database files."""
    created = []

    # Create directory
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Create config if missing
    if not CONFIG_FILE.exists():
        config = {
            "asset_categories": DEFAULT_ASSET_CATEGORIES.copy(),
            "part_categories": DEFAULT_PART_CATEGORIES.copy(),
            "service_types": DEFAULT_SERVICE_TYPES.copy(),
            "part_units": DEFAULT_PART_UNITS.copy(),
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        save_config(config)
        created.append("config")

    # Create empty database if missing
    if not DATA_FILE.exists():
        data = {"assets": {}, "parts": {}, "service_events": [], "transactions": []}
        save_data(data)
        created.append("database")

    if created:
        print(f"OK:created:{','.join(created)}")
    else:
        print("OK:already_initialized")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export data and config to a timestamped backup file."""
    # Create backup directory if needed
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = BACKUP_DIR / f"asm_backup_{timestamp}.json"

    # Load current data
    data = load_data()
    config = load_config()

    # Create backup structure
    backup_data = {
        "version": "1.0",
        "created": datetime.now().isoformat(timespec="seconds"),
        "type": "asm_backup",
        "data": data,
        "config": config,
    }

    # Write backup file
    backup_file.write_text(
        json.dumps(backup_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"OK:{backup_file.name}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    """Import data and config from a backup file."""
    filename = args.filename.strip()
    if not filename:
        print("ERROR: Filename cannot be empty", file=sys.stderr)
        return 1

    # Construct full path
    backup_file = BACKUP_DIR / filename
    if not backup_file.exists():
        print(f"ERROR: Backup file '{filename}' not found", file=sys.stderr)
        return 1

    # Load and validate backup
    try:
        backup_data = json.loads(backup_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in backup file: {e}", file=sys.stderr)
        return 1

    # Validate backup structure
    if backup_data.get("type") != "asm_backup":
        print("ERROR: File is not a valid ASM backup", file=sys.stderr)
        return 1

    data = backup_data.get("data")
    config = backup_data.get("config")

    if not isinstance(data, dict):
        print("ERROR: Backup contains invalid data", file=sys.stderr)
        return 1

    # Create a backup of current data before importing
    current_data = load_data()
    current_config = load_config()

    pre_import_backup = {
        "version": "1.0",
        "created": datetime.now().isoformat(timespec="seconds"),
        "type": "asm_backup",
        "note": "Pre-import automatic backup",
        "data": current_data,
        "config": current_config,
    }

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    pre_import_file = BACKUP_DIR / f"pre_import_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
    pre_import_file.write_text(
        json.dumps(pre_import_backup, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Import the data
    save_data(data)
    if config and isinstance(config, dict):
        save_config(config)

    asset_count = len(data.get("assets", {}))
    part_count = len(data.get("parts", {}))
    print(f"OK:imported:{asset_count}:{part_count}:{pre_import_file.name}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    """Reset all ASM data (requires confirmation token)."""
    token = args.token.strip() if args.token else ""

    # Token must be "CONFIRM_RESET" to proceed
    if token != "CONFIRM_RESET":
        print("ERROR: Invalid confirmation token. Use --token CONFIRM_RESET", file=sys.stderr)
        return 1

    # Create backup before reset
    current_data = load_data()
    current_config = load_config()

    if current_data.get("assets") or current_data.get("parts") or current_data.get("service_events"):
        pre_reset_backup = {
            "version": "1.0",
            "created": datetime.now().isoformat(timespec="seconds"),
            "type": "asm_backup",
            "note": "Pre-reset automatic backup",
            "data": current_data,
            "config": current_config,
        }

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        pre_reset_file = BACKUP_DIR / f"pre_reset_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
        pre_reset_file.write_text(
            json.dumps(pre_reset_backup, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # Reset to empty state
    empty_data = {"assets": {}, "parts": {}, "service_events": [], "transactions": []}
    save_data(empty_data)

    # Reset config to defaults
    reset_config = {
        "asset_categories": DEFAULT_ASSET_CATEGORIES.copy(),
        "part_categories": DEFAULT_PART_CATEGORIES.copy(),
        "service_types": DEFAULT_SERVICE_TYPES.copy(),
        "part_units": DEFAULT_PART_UNITS.copy(),
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    save_config(reset_config)

    print("OK:reset")
    return 0


def cmd_backup_list(args: argparse.Namespace) -> int:
    """List available backup files with metadata."""
    backups = []

    if BACKUP_DIR.exists():
        for backup_file in sorted(BACKUP_DIR.glob("*.json"), reverse=True):
            try:
                backup_data = json.loads(backup_file.read_text(encoding="utf-8"))
                asset_count = len(backup_data.get("data", {}).get("assets", {}))
                part_count = len(backup_data.get("data", {}).get("parts", {}))
                backups.append({
                    "filename": backup_file.name,
                    "created": backup_data.get("created", ""),
                    "note": backup_data.get("note", ""),
                    "asset_count": asset_count,
                    "part_count": part_count,
                    "size_kb": round(backup_file.stat().st_size / 1024, 1),
                })
            except (json.JSONDecodeError, IOError):
                # Include file even if we can't read it
                backups.append({
                    "filename": backup_file.name,
                    "created": "",
                    "note": "Unable to read",
                    "asset_count": 0,
                    "part_count": 0,
                    "size_kb": round(backup_file.stat().st_size / 1024, 1),
                })

    result = {
        "total": len(backups),
        "backups": backups,
    }

    print(json.dumps(result))
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

    # delete_service
    del_svc = subparsers.add_parser("delete_service", help="Delete a service event")
    del_svc.add_argument("--id", required=True, help="Service event ID")
    del_svc.set_defaults(func=cmd_delete_service)

    # ----- System Management Commands -----
    # status command
    status_p = subparsers.add_parser("status", help="Get system status")
    status_p.set_defaults(func=cmd_status)

    # init command
    init_p = subparsers.add_parser("init", help="Initialize ASM system")
    init_p.set_defaults(func=cmd_init)

    # export command
    export_p = subparsers.add_parser("export", help="Export data to backup file")
    export_p.set_defaults(func=cmd_export)

    # import command
    import_p = subparsers.add_parser("import_backup", help="Import data from backup file")
    import_p.add_argument("--filename", required=True, help="Backup filename to import")
    import_p.set_defaults(func=cmd_import)

    # reset command
    reset_p = subparsers.add_parser("reset", help="Reset all data (requires confirmation)")
    reset_p.add_argument("--token", required=True, help="Confirmation token (CONFIRM_RESET)")
    reset_p.set_defaults(func=cmd_reset)

    # backup_list command
    backup_list_p = subparsers.add_parser("backup_list", help="List available backups")
    backup_list_p.set_defaults(func=cmd_backup_list)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
