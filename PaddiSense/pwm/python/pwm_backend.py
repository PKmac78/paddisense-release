#!/usr/bin/env python3
"""
PWM Backend - Precision Water Management
PaddiSense Farm Management System

This script handles all write operations for the water management system:
  - add_paddock / edit_paddock / delete_paddock: Paddock management
  - enable_paddock / disable_paddock: Enable/disable paddocks
  - edit_bay / assign_device: Bay configuration
  - init / status: System initialization and status
  - export / import_backup / reset / backup_list: Data management

Data is stored in: /config/local_data/pwm/config.json
Backups are stored in: /config/local_data/pwm/backups/

Usage:
  python3 pwm_backend.py init
  python3 pwm_backend.py status
  python3 pwm_backend.py add_paddock --farm farm_1 --name "SW6" --bay_prefix "B-" --bay_count 5
  python3 pwm_backend.py edit_paddock --id sw6 --name "Sheepwash 6"
  python3 pwm_backend.py enable_paddock --id sw6
  python3 pwm_backend.py edit_bay --id sw6_b_01 --level_sensor rb_040
  python3 pwm_backend.py assign_device --bay sw6_b_01 --slot supply_1 --device rb_040 --type door
  python3 pwm_backend.py export
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# File locations (outside of git-tracked folders)
DATA_DIR = Path("/config/local_data/pwm")
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"

# Default bay settings
DEFAULT_BAY_SETTINGS = {
    "water_level_min": 5,
    "water_level_max": 15,
    "water_level_offset": 0,
    "flush_time_on_water": 3600,
}

# Valid device types
DEVICE_TYPES = ["door", "valve", "spur", "channel_supply"]

# Valid device slots
DEVICE_SLOTS = ["supply_1", "supply_2", "drain_1", "drain_2"]


def generate_id(name: str) -> str:
    """Generate a clean ID from the name."""
    clean = re.sub(r"[^a-z0-9]+", "_", name.lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean[:30] if clean else "unknown"


def load_config() -> dict[str, Any]:
    """Load config from JSON file, or return empty structure."""
    if not CONFIG_FILE.exists():
        return {
            "initialized": False,
            "paddocks": {},
            "bays": {},
            "version": "1.0.0",
        }
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {
            "initialized": False,
            "paddocks": {},
            "bays": {},
            "version": "1.0.0",
        }


def save_config(config: dict[str, Any]) -> None:
    """Save config to JSON file."""
    config["modified"] = datetime.now().isoformat(timespec="seconds")
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def create_backup(tag: str = "") -> Path:
    """Create a timestamped backup of the config file."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    backup_name = f"backup_{ts}{suffix}.json"
    backup_path = BACKUP_DIR / backup_name
    if CONFIG_FILE.exists():
        backup_path.write_text(CONFIG_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


def log_transaction(
    config: dict,
    action: str,
    entity_type: str,
    entity_id: str,
    entity_name: str,
    details: str = "",
) -> None:
    """Append a transaction record for audit trail."""
    config.setdefault("transactions", []).append(
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
# PADDOCK COMMANDS
# =============================================================================


def cmd_add_paddock(args: argparse.Namespace) -> int:
    """Add a new paddock with specified number of bays."""
    config = load_config()
    paddocks = config.setdefault("paddocks", {})
    bays = config.setdefault("bays", {})

    paddock_id = generate_id(args.name)

    # Check if paddock already exists
    if paddock_id in paddocks:
        print(json.dumps({"error": f"Paddock '{paddock_id}' already exists"}))
        return 1

    # Create paddock
    now = datetime.now().isoformat(timespec="seconds")
    paddocks[paddock_id] = {
        "farm_id": args.farm or "farm_1",
        "name": args.name,
        "enabled": False,  # Start disabled
        "automation_state_individual": args.individual or False,
        "bay_prefix": args.bay_prefix or "B-",
        "bay_count": args.bay_count,
        "created": now,
        "modified": now,
    }

    # Create bays
    bay_prefix = args.bay_prefix or "B-"
    for i in range(1, args.bay_count + 1):
        bay_name = f"{bay_prefix}{i:02d}"
        bay_id = f"{paddock_id}_{generate_id(bay_name)}"
        is_last = i == args.bay_count

        bays[bay_id] = {
            "paddock_id": paddock_id,
            "name": bay_name,
            "order": i,
            "supply_1": {"device": None, "type": None},
            "supply_2": {"device": None, "type": None},
            "drain_1": {"device": None, "type": None} if is_last else {"device": None, "type": None},
            "drain_2": {"device": None, "type": None},
            "level_sensor": None,
            "settings": DEFAULT_BAY_SETTINGS.copy(),
        }
        if is_last:
            bays[bay_id]["is_last_bay"] = True

    log_transaction(
        config, "add", "paddock", paddock_id, args.name,
        f"Created with {args.bay_count} bays"
    )
    save_config(config)

    print(json.dumps({
        "success": True,
        "paddock_id": paddock_id,
        "bay_count": args.bay_count,
        "message": f"Created paddock '{args.name}' with {args.bay_count} bays"
    }))
    return 0


def cmd_edit_paddock(args: argparse.Namespace) -> int:
    """Edit an existing paddock."""
    config = load_config()
    paddocks = config.get("paddocks", {})

    if args.id not in paddocks:
        print(json.dumps({"error": f"Paddock '{args.id}' not found"}))
        return 1

    paddock = paddocks[args.id]
    changes = []

    if args.name is not None:
        paddock["name"] = args.name
        changes.append(f"name={args.name}")

    if args.farm is not None:
        paddock["farm_id"] = args.farm
        changes.append(f"farm={args.farm}")

    if args.individual is not None:
        paddock["automation_state_individual"] = args.individual
        changes.append(f"individual={args.individual}")

    paddock["modified"] = datetime.now().isoformat(timespec="seconds")

    log_transaction(
        config, "edit", "paddock", args.id, paddock["name"],
        ", ".join(changes)
    )
    save_config(config)

    print(json.dumps({
        "success": True,
        "paddock_id": args.id,
        "message": f"Updated paddock '{paddock['name']}'"
    }))
    return 0


def cmd_delete_paddock(args: argparse.Namespace) -> int:
    """Delete a paddock and all its bays."""
    config = load_config()
    paddocks = config.get("paddocks", {})
    bays = config.get("bays", {})

    if args.id not in paddocks:
        print(json.dumps({"error": f"Paddock '{args.id}' not found"}))
        return 1

    # Create backup before delete
    create_backup("pre_delete")

    paddock_name = paddocks[args.id].get("name", args.id)

    # Delete associated bays
    bays_to_delete = [bid for bid, b in bays.items() if b.get("paddock_id") == args.id]
    for bid in bays_to_delete:
        del bays[bid]

    # Delete paddock
    del paddocks[args.id]

    log_transaction(
        config, "delete", "paddock", args.id, paddock_name,
        f"Deleted with {len(bays_to_delete)} bays"
    )
    save_config(config)

    print(json.dumps({
        "success": True,
        "paddock_id": args.id,
        "bays_deleted": len(bays_to_delete),
        "message": f"Deleted paddock '{paddock_name}' and {len(bays_to_delete)} bays"
    }))
    return 0


def cmd_enable_paddock(args: argparse.Namespace) -> int:
    """Enable a paddock."""
    config = load_config()
    paddocks = config.get("paddocks", {})

    if args.id not in paddocks:
        print(json.dumps({"error": f"Paddock '{args.id}' not found"}))
        return 1

    paddocks[args.id]["enabled"] = True
    paddocks[args.id]["modified"] = datetime.now().isoformat(timespec="seconds")

    log_transaction(config, "enable", "paddock", args.id, paddocks[args.id]["name"], "")
    save_config(config)

    print(json.dumps({
        "success": True,
        "paddock_id": args.id,
        "message": f"Enabled paddock '{paddocks[args.id]['name']}'"
    }))
    return 0


def cmd_disable_paddock(args: argparse.Namespace) -> int:
    """Disable a paddock."""
    config = load_config()
    paddocks = config.get("paddocks", {})

    if args.id not in paddocks:
        print(json.dumps({"error": f"Paddock '{args.id}' not found"}))
        return 1

    paddocks[args.id]["enabled"] = False
    paddocks[args.id]["modified"] = datetime.now().isoformat(timespec="seconds")

    log_transaction(config, "disable", "paddock", args.id, paddocks[args.id]["name"], "")
    save_config(config)

    print(json.dumps({
        "success": True,
        "paddock_id": args.id,
        "message": f"Disabled paddock '{paddocks[args.id]['name']}'"
    }))
    return 0


# =============================================================================
# BAY COMMANDS
# =============================================================================


def cmd_edit_bay(args: argparse.Namespace) -> int:
    """Edit bay configuration."""
    config = load_config()
    bays = config.get("bays", {})

    if args.id not in bays:
        print(json.dumps({"error": f"Bay '{args.id}' not found"}))
        return 1

    bay = bays[args.id]
    changes = []

    if args.level_sensor is not None:
        bay["level_sensor"] = args.level_sensor if args.level_sensor != "null" else None
        changes.append(f"level_sensor={args.level_sensor}")

    # Settings updates
    settings = bay.setdefault("settings", DEFAULT_BAY_SETTINGS.copy())

    if args.water_level_min is not None:
        settings["water_level_min"] = args.water_level_min
        changes.append(f"min={args.water_level_min}")

    if args.water_level_max is not None:
        settings["water_level_max"] = args.water_level_max
        changes.append(f"max={args.water_level_max}")

    if args.water_level_offset is not None:
        settings["water_level_offset"] = args.water_level_offset
        changes.append(f"offset={args.water_level_offset}")

    if args.flush_time is not None:
        settings["flush_time_on_water"] = args.flush_time
        changes.append(f"flush_time={args.flush_time}")

    log_transaction(
        config, "edit", "bay", args.id, bay["name"],
        ", ".join(changes)
    )
    save_config(config)

    print(json.dumps({
        "success": True,
        "bay_id": args.id,
        "message": f"Updated bay '{bay['name']}'"
    }))
    return 0


def cmd_assign_device(args: argparse.Namespace) -> int:
    """Assign a device to a bay slot."""
    config = load_config()
    bays = config.get("bays", {})

    if args.bay not in bays:
        print(json.dumps({"error": f"Bay '{args.bay}' not found"}))
        return 1

    if args.slot not in DEVICE_SLOTS:
        print(json.dumps({"error": f"Invalid slot '{args.slot}'. Valid: {DEVICE_SLOTS}"}))
        return 1

    device_type = args.type or "door"
    if device_type not in DEVICE_TYPES:
        print(json.dumps({"error": f"Invalid type '{device_type}'. Valid: {DEVICE_TYPES}"}))
        return 1

    bay = bays[args.bay]

    # Handle "null" or empty to unassign
    if args.device in (None, "null", "unset", ""):
        bay[args.slot] = {"device": None, "type": None}
        action = "unassigned"
    else:
        bay[args.slot] = {
            "device": args.device,
            "type": device_type,
        }
        # Add label if provided
        if args.label:
            bay[args.slot]["label"] = args.label
        action = f"assigned {args.device}"

    log_transaction(
        config, "assign_device", "bay", args.bay, bay["name"],
        f"{args.slot}: {action}"
    )
    save_config(config)

    print(json.dumps({
        "success": True,
        "bay_id": args.bay,
        "slot": args.slot,
        "device": args.device,
        "message": f"Slot {args.slot} {action} on bay '{bay['name']}'"
    }))
    return 0


# =============================================================================
# SYSTEM COMMANDS
# =============================================================================


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize the PWM system."""
    config = load_config()

    # Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if config.get("initialized"):
        print(json.dumps({
            "success": True,
            "message": "System already initialized",
            "paddock_count": len(config.get("paddocks", {})),
            "bay_count": len(config.get("bays", {})),
        }))
        return 0

    # Initialize
    now = datetime.now().isoformat(timespec="seconds")
    config["initialized"] = True
    config["version"] = "1.0.0"
    config.setdefault("paddocks", {})
    config.setdefault("bays", {})
    config.setdefault("transactions", [])
    config["created"] = now
    config["modified"] = now

    save_config(config)

    print(json.dumps({
        "success": True,
        "message": "PWM system initialized",
    }))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Return system status."""
    config = load_config()

    paddocks = config.get("paddocks", {})
    bays = config.get("bays", {})
    enabled_count = sum(1 for p in paddocks.values() if p.get("enabled"))

    # Count backups
    backup_count = len(list(BACKUP_DIR.glob("*.json"))) if BACKUP_DIR.exists() else 0

    status = {
        "initialized": config.get("initialized", False),
        "config_exists": CONFIG_FILE.exists(),
        "version": config.get("version", "unknown"),
        "total_paddocks": len(paddocks),
        "enabled_paddocks": enabled_count,
        "total_bays": len(bays),
        "transaction_count": len(config.get("transactions", [])),
        "backup_count": backup_count,
        "created": config.get("created"),
        "modified": config.get("modified"),
    }

    print(json.dumps(status))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export config to a timestamped backup."""
    if not CONFIG_FILE.exists():
        print(json.dumps({"error": "No config file to export"}))
        return 1

    backup_path = create_backup("export")

    print(json.dumps({
        "success": True,
        "backup_file": str(backup_path.name),
        "message": f"Exported to {backup_path.name}"
    }))
    return 0


def cmd_import_backup(args: argparse.Namespace) -> int:
    """Import config from a backup file."""
    backup_path = BACKUP_DIR / args.filename

    if not backup_path.exists():
        print(json.dumps({"error": f"Backup file '{args.filename}' not found"}))
        return 1

    # Create pre-import backup
    if CONFIG_FILE.exists():
        create_backup("pre_import")

    try:
        backup_data = json.loads(backup_path.read_text(encoding="utf-8"))
        # Validate structure
        if "paddocks" not in backup_data and "bays" not in backup_data:
            print(json.dumps({"error": "Invalid backup file structure"}))
            return 1

        save_config(backup_data)

        print(json.dumps({
            "success": True,
            "message": f"Imported from {args.filename}",
            "paddock_count": len(backup_data.get("paddocks", {})),
            "bay_count": len(backup_data.get("bays", {})),
        }))
        return 0
    except (json.JSONDecodeError, IOError) as e:
        print(json.dumps({"error": f"Failed to import: {e}"}))
        return 1


def cmd_reset(args: argparse.Namespace) -> int:
    """Reset the system (requires confirmation token)."""
    if args.token != "CONFIRM_RESET":
        print(json.dumps({
            "error": "Reset requires --token CONFIRM_RESET",
            "message": "This will delete all paddock and bay configurations!"
        }))
        return 1

    # Create backup before reset
    if CONFIG_FILE.exists():
        create_backup("pre_reset")

    # Reset to empty state
    now = datetime.now().isoformat(timespec="seconds")
    config = {
        "initialized": True,
        "paddocks": {},
        "bays": {},
        "transactions": [],
        "version": "1.0.0",
        "created": now,
        "modified": now,
    }
    save_config(config)

    print(json.dumps({
        "success": True,
        "message": "System reset complete. All paddocks and bays deleted."
    }))
    return 0


def cmd_backup_list(args: argparse.Namespace) -> int:
    """List available backup files."""
    if not BACKUP_DIR.exists():
        print(json.dumps({"backups": []}))
        return 0

    backups = sorted(BACKUP_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    backup_list = []
    for b in backups[:20]:  # Last 20
        backup_list.append({
            "filename": b.name,
            "size": b.stat().st_size,
            "modified": datetime.fromtimestamp(b.stat().st_mtime).isoformat(timespec="seconds"),
        })

    print(json.dumps({"backups": backup_list}))
    return 0


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(description="PWM Backend")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Paddock commands
    p_add = subparsers.add_parser("add_paddock", help="Add a new paddock")
    p_add.add_argument("--farm", help="Farm ID")
    p_add.add_argument("--name", required=True, help="Paddock name")
    p_add.add_argument("--bay_prefix", default="B-", help="Bay prefix (e.g., B-)")
    p_add.add_argument("--bay_count", type=int, required=True, help="Number of bays")
    p_add.add_argument("--individual", action="store_true", help="Enable individual bay automation")

    p_edit = subparsers.add_parser("edit_paddock", help="Edit a paddock")
    p_edit.add_argument("--id", required=True, help="Paddock ID")
    p_edit.add_argument("--name", help="New name")
    p_edit.add_argument("--farm", help="Farm ID")
    p_edit.add_argument("--individual", type=lambda x: x.lower() == "true", help="Individual mode (true/false)")

    p_del = subparsers.add_parser("delete_paddock", help="Delete a paddock")
    p_del.add_argument("--id", required=True, help="Paddock ID")

    p_en = subparsers.add_parser("enable_paddock", help="Enable a paddock")
    p_en.add_argument("--id", required=True, help="Paddock ID")

    p_dis = subparsers.add_parser("disable_paddock", help="Disable a paddock")
    p_dis.add_argument("--id", required=True, help="Paddock ID")

    # Bay commands
    b_edit = subparsers.add_parser("edit_bay", help="Edit bay configuration")
    b_edit.add_argument("--id", required=True, help="Bay ID")
    b_edit.add_argument("--level_sensor", help="Level sensor device")
    b_edit.add_argument("--water_level_min", type=int, help="Min water level (cm)")
    b_edit.add_argument("--water_level_max", type=int, help="Max water level (cm)")
    b_edit.add_argument("--water_level_offset", type=float, help="Water level offset (cm)")
    b_edit.add_argument("--flush_time", type=int, help="Flush time on water (seconds)")

    b_assign = subparsers.add_parser("assign_device", help="Assign device to bay slot")
    b_assign.add_argument("--bay", required=True, help="Bay ID")
    b_assign.add_argument("--slot", required=True, help="Slot (supply_1, supply_2, drain_1, drain_2)")
    b_assign.add_argument("--device", help="Device name (or 'null' to unassign)")
    b_assign.add_argument("--type", default="door", help="Device type (door, valve, spur, channel_supply)")
    b_assign.add_argument("--label", help="Custom label for device")

    # System commands
    subparsers.add_parser("init", help="Initialize the system")
    subparsers.add_parser("status", help="Get system status")
    subparsers.add_parser("export", help="Export to backup")

    p_import = subparsers.add_parser("import_backup", help="Import from backup")
    p_import.add_argument("--filename", required=True, help="Backup filename")

    p_reset = subparsers.add_parser("reset", help="Reset system (destructive)")
    p_reset.add_argument("--token", required=True, help="Confirmation token")

    subparsers.add_parser("backup_list", help="List backup files")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "add_paddock": cmd_add_paddock,
        "edit_paddock": cmd_edit_paddock,
        "delete_paddock": cmd_delete_paddock,
        "enable_paddock": cmd_enable_paddock,
        "disable_paddock": cmd_disable_paddock,
        "edit_bay": cmd_edit_bay,
        "assign_device": cmd_assign_device,
        "init": cmd_init,
        "status": cmd_status,
        "export": cmd_export,
        "import_backup": cmd_import_backup,
        "reset": cmd_reset,
        "backup_list": cmd_backup_list,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        return cmd_func(args)

    print(json.dumps({"error": f"Unknown command: {args.command}"}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
