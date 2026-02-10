#!/usr/bin/env python3
"""
Farm Registry Backend - PaddiSense Shared Core
PaddiSense Farm Management System

This script handles all write operations for the farm registry:
  - Paddock management: add_paddock, edit_paddock, delete_paddock
  - Bay management: add_bay, edit_bay, delete_bay
  - Season management: add_season, edit_season, delete_season, set_active_season
  - System: init, status, export, import_backup, reset, backup_list, migrate

Data is stored in: /config/local_data/registry/config.json
Backups are stored in: /config/local_data/registry/backups/

Usage:
  python3 registry_backend.py init
  python3 registry_backend.py status
  python3 registry_backend.py add_paddock --farm farm_1 --name "SW6" --bay_count 5
  python3 registry_backend.py add_season --name "CY26" --start 2025-04-01 --end 2026-03-31
  python3 registry_backend.py set_active_season --id cy26
  python3 registry_backend.py migrate_from_pwm
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# File locations
DATA_DIR = Path("/config/local_data/registry")
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"

# PWM data for migration
PWM_CONFIG_FILE = Path("/config/local_data/pwm/config.json")


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
            "seasons": {},
            "version": "1.0.0",
        }
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {
            "initialized": False,
            "paddocks": {},
            "bays": {},
            "seasons": {},
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
    bay_prefix = args.bay_prefix or "B-"

    paddocks[paddock_id] = {
        "farm_id": args.farm or "farm_1",
        "name": args.name,
        "bay_prefix": bay_prefix,
        "bay_count": args.bay_count,
        "current_season": args.current_season if args.current_season is not None else True,
        "created": now,
        "modified": now,
    }

    # Create bays
    for i in range(1, args.bay_count + 1):
        bay_name = f"{bay_prefix}{i:02d}"
        bay_id = f"{paddock_id}_{generate_id(bay_name)}"
        is_last = i == args.bay_count

        bays[bay_id] = {
            "paddock_id": paddock_id,
            "name": bay_name,
            "order": i,
            "is_last_bay": is_last,
            "created": now,
            "modified": now,
        }

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

    if args.current_season is not None:
        paddock["current_season"] = args.current_season
        changes.append(f"current_season={args.current_season}")

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


def cmd_set_current_season(args: argparse.Namespace) -> int:
    """Set paddock current_season flag."""
    config = load_config()
    paddocks = config.get("paddocks", {})

    if args.id not in paddocks:
        print(json.dumps({"error": f"Paddock '{args.id}' not found"}))
        return 1

    paddock = paddocks[args.id]

    # Toggle if no value specified, otherwise set to specified value
    if args.value is not None:
        new_value = args.value
    else:
        new_value = not paddock.get("current_season", True)

    paddock["current_season"] = new_value
    paddock["modified"] = datetime.now().isoformat(timespec="seconds")

    log_transaction(
        config, "set_current_season", "paddock", args.id, paddock["name"],
        f"current_season={new_value}"
    )
    save_config(config)

    print(json.dumps({
        "success": True,
        "paddock_id": args.id,
        "current_season": new_value,
        "message": f"Set {paddock['name']} current_season to {new_value}"
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


# =============================================================================
# BAY COMMANDS
# =============================================================================


def cmd_add_bay(args: argparse.Namespace) -> int:
    """Add a bay to an existing paddock."""
    config = load_config()
    paddocks = config.get("paddocks", {})
    bays = config.setdefault("bays", {})

    if args.paddock not in paddocks:
        print(json.dumps({"error": f"Paddock '{args.paddock}' not found"}))
        return 1

    paddock = paddocks[args.paddock]
    bay_id = f"{args.paddock}_{generate_id(args.name)}"

    if bay_id in bays:
        print(json.dumps({"error": f"Bay '{bay_id}' already exists"}))
        return 1

    # Determine order
    existing_bays = [b for b in bays.values() if b.get("paddock_id") == args.paddock]
    max_order = max([b.get("order", 0) for b in existing_bays], default=0)

    now = datetime.now().isoformat(timespec="seconds")
    bays[bay_id] = {
        "paddock_id": args.paddock,
        "name": args.name,
        "order": args.order if args.order else max_order + 1,
        "is_last_bay": args.is_last or False,
        "created": now,
        "modified": now,
    }

    # Update paddock bay count
    paddock["bay_count"] = len([b for b in bays.values() if b.get("paddock_id") == args.paddock])
    paddock["modified"] = now

    log_transaction(config, "add", "bay", bay_id, args.name, f"Added to {args.paddock}")
    save_config(config)

    print(json.dumps({
        "success": True,
        "bay_id": bay_id,
        "message": f"Added bay '{args.name}' to paddock"
    }))
    return 0


def cmd_edit_bay(args: argparse.Namespace) -> int:
    """Edit bay basic info."""
    config = load_config()
    bays = config.get("bays", {})

    if args.id not in bays:
        print(json.dumps({"error": f"Bay '{args.id}' not found"}))
        return 1

    bay = bays[args.id]
    changes = []

    if args.name is not None:
        bay["name"] = args.name
        changes.append(f"name={args.name}")

    if args.order is not None:
        bay["order"] = args.order
        changes.append(f"order={args.order}")

    if args.is_last is not None:
        bay["is_last_bay"] = args.is_last
        changes.append(f"is_last={args.is_last}")

    bay["modified"] = datetime.now().isoformat(timespec="seconds")

    log_transaction(config, "edit", "bay", args.id, bay["name"], ", ".join(changes))
    save_config(config)

    print(json.dumps({
        "success": True,
        "bay_id": args.id,
        "message": f"Updated bay '{bay['name']}'"
    }))
    return 0


def cmd_delete_bay(args: argparse.Namespace) -> int:
    """Delete a bay."""
    config = load_config()
    bays = config.get("bays", {})
    paddocks = config.get("paddocks", {})

    if args.id not in bays:
        print(json.dumps({"error": f"Bay '{args.id}' not found"}))
        return 1

    bay = bays[args.id]
    bay_name = bay.get("name", args.id)
    paddock_id = bay.get("paddock_id")

    del bays[args.id]

    # Update paddock bay count
    if paddock_id and paddock_id in paddocks:
        paddocks[paddock_id]["bay_count"] = len(
            [b for b in bays.values() if b.get("paddock_id") == paddock_id]
        )
        paddocks[paddock_id]["modified"] = datetime.now().isoformat(timespec="seconds")

    log_transaction(config, "delete", "bay", args.id, bay_name, "")
    save_config(config)

    print(json.dumps({
        "success": True,
        "bay_id": args.id,
        "message": f"Deleted bay '{bay_name}'"
    }))
    return 0


# =============================================================================
# SEASON COMMANDS
# =============================================================================


def cmd_add_season(args: argparse.Namespace) -> int:
    """Add a new season."""
    config = load_config()
    seasons = config.setdefault("seasons", {})

    season_id = generate_id(args.name)

    if season_id in seasons:
        print(json.dumps({"error": f"Season '{season_id}' already exists"}))
        return 1

    now = datetime.now().isoformat(timespec="seconds")
    seasons[season_id] = {
        "name": args.name,
        "start_date": args.start,
        "end_date": args.end,
        "active": args.active or False,
        "created": now,
        "modified": now,
    }

    # If this is set as active, deactivate others
    if args.active:
        for sid, season in seasons.items():
            if sid != season_id:
                season["active"] = False

    log_transaction(config, "add", "season", season_id, args.name, f"{args.start} to {args.end}")
    save_config(config)

    print(json.dumps({
        "success": True,
        "season_id": season_id,
        "message": f"Created season '{args.name}'"
    }))
    return 0


def cmd_edit_season(args: argparse.Namespace) -> int:
    """Edit a season."""
    config = load_config()
    seasons = config.get("seasons", {})

    if args.id not in seasons:
        print(json.dumps({"error": f"Season '{args.id}' not found"}))
        return 1

    season = seasons[args.id]
    changes = []

    if args.name is not None:
        season["name"] = args.name
        changes.append(f"name={args.name}")

    if args.start is not None:
        season["start_date"] = args.start
        changes.append(f"start={args.start}")

    if args.end is not None:
        season["end_date"] = args.end
        changes.append(f"end={args.end}")

    season["modified"] = datetime.now().isoformat(timespec="seconds")

    log_transaction(config, "edit", "season", args.id, season["name"], ", ".join(changes))
    save_config(config)

    print(json.dumps({
        "success": True,
        "season_id": args.id,
        "message": f"Updated season '{season['name']}'"
    }))
    return 0


def cmd_delete_season(args: argparse.Namespace) -> int:
    """Delete a season."""
    config = load_config()
    seasons = config.get("seasons", {})

    if args.id not in seasons:
        print(json.dumps({"error": f"Season '{args.id}' not found"}))
        return 1

    season_name = seasons[args.id].get("name", args.id)
    del seasons[args.id]

    log_transaction(config, "delete", "season", args.id, season_name, "")
    save_config(config)

    print(json.dumps({
        "success": True,
        "season_id": args.id,
        "message": f"Deleted season '{season_name}'"
    }))
    return 0


def cmd_set_active_season(args: argparse.Namespace) -> int:
    """Set the active season."""
    config = load_config()
    seasons = config.get("seasons", {})

    if args.id not in seasons:
        print(json.dumps({"error": f"Season '{args.id}' not found"}))
        return 1

    # Deactivate all, then activate the specified one
    for sid, season in seasons.items():
        season["active"] = sid == args.id
        season["modified"] = datetime.now().isoformat(timespec="seconds")

    season_name = seasons[args.id].get("name", args.id)
    log_transaction(config, "set_active", "season", args.id, season_name, "")
    save_config(config)

    print(json.dumps({
        "success": True,
        "season_id": args.id,
        "message": f"Set active season to '{season_name}'"
    }))
    return 0


# =============================================================================
# FARM COMMANDS
# =============================================================================


def cmd_add_farm(args: argparse.Namespace) -> int:
    """Add a new farm."""
    config = load_config()
    farms = config.setdefault("farms", {})

    farm_id = generate_id(args.name)

    if farm_id in farms:
        print(json.dumps({"error": f"Farm '{farm_id}' already exists"}))
        return 1

    now = datetime.now().isoformat(timespec="seconds")
    farms[farm_id] = {
        "name": args.name,
        "created": now,
        "modified": now,
    }

    log_transaction(config, "add", "farm", farm_id, args.name, "")
    save_config(config)

    print(json.dumps({
        "success": True,
        "farm_id": farm_id,
        "message": f"Created farm '{args.name}'"
    }))
    return 0


def cmd_edit_farm(args: argparse.Namespace) -> int:
    """Edit an existing farm."""
    config = load_config()
    farms = config.get("farms", {})

    if args.id not in farms:
        print(json.dumps({"error": f"Farm '{args.id}' not found"}))
        return 1

    farm = farms[args.id]
    changes = []

    if args.name is not None:
        farm["name"] = args.name
        changes.append(f"name={args.name}")

    farm["modified"] = datetime.now().isoformat(timespec="seconds")

    log_transaction(config, "edit", "farm", args.id, farm["name"], ", ".join(changes))
    save_config(config)

    print(json.dumps({
        "success": True,
        "farm_id": args.id,
        "message": f"Updated farm '{farm['name']}'"
    }))
    return 0


def cmd_delete_farm(args: argparse.Namespace) -> int:
    """Delete a farm (only if no paddocks assigned)."""
    config = load_config()
    farms = config.get("farms", {})
    paddocks = config.get("paddocks", {})

    if args.id not in farms:
        print(json.dumps({"error": f"Farm '{args.id}' not found"}))
        return 1

    # Check for assigned paddocks
    assigned_paddocks = [p for p in paddocks.values() if p.get("farm_id") == args.id]
    if assigned_paddocks:
        print(json.dumps({
            "error": f"Cannot delete farm with {len(assigned_paddocks)} assigned paddocks",
            "paddock_count": len(assigned_paddocks)
        }))
        return 1

    farm_name = farms[args.id].get("name", args.id)
    del farms[args.id]

    log_transaction(config, "delete", "farm", args.id, farm_name, "")
    save_config(config)

    print(json.dumps({
        "success": True,
        "farm_id": args.id,
        "message": f"Deleted farm '{farm_name}'"
    }))
    return 0


# =============================================================================
# SYSTEM COMMANDS
# =============================================================================


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize the registry system."""
    config = load_config()

    # Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if config.get("initialized"):
        print(json.dumps({
            "success": True,
            "message": "Registry already initialized",
            "paddock_count": len(config.get("paddocks", {})),
            "bay_count": len(config.get("bays", {})),
            "season_count": len(config.get("seasons", {})),
        }))
        return 0

    # Initialize
    now = datetime.now().isoformat(timespec="seconds")
    config["initialized"] = True
    config["version"] = "1.0.0"
    config.setdefault("paddocks", {})
    config.setdefault("bays", {})
    config.setdefault("seasons", {})
    config.setdefault("transactions", [])
    config["created"] = now
    config["modified"] = now

    save_config(config)

    print(json.dumps({
        "success": True,
        "message": "Farm Registry initialized",
    }))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Return system status."""
    config = load_config()

    paddocks = config.get("paddocks", {})
    bays = config.get("bays", {})
    seasons = config.get("seasons", {})

    # Get active season
    active_season = None
    for sid, s in seasons.items():
        if s.get("active"):
            active_season = sid
            break

    # Count backups
    backup_count = len(list(BACKUP_DIR.glob("*.json"))) if BACKUP_DIR.exists() else 0

    status = {
        "initialized": config.get("initialized", False),
        "config_exists": CONFIG_FILE.exists(),
        "version": config.get("version", "unknown"),
        "total_paddocks": len(paddocks),
        "total_bays": len(bays),
        "total_seasons": len(seasons),
        "active_season": active_season,
        "transaction_count": len(config.get("transactions", [])),
        "backup_count": backup_count,
        "created": config.get("created"),
        "modified": config.get("modified"),
    }

    print(json.dumps(status))
    return 0


def cmd_migrate_from_pwm(args: argparse.Namespace) -> int:
    """Migrate paddock/bay data from PWM to registry."""
    if not PWM_CONFIG_FILE.exists():
        print(json.dumps({"error": "PWM config not found"}))
        return 1

    try:
        pwm_data = json.loads(PWM_CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        print(json.dumps({"error": f"Failed to read PWM config: {e}"}))
        return 1

    config = load_config()

    # Create backup before migration
    if CONFIG_FILE.exists():
        create_backup("pre_migration")

    now = datetime.now().isoformat(timespec="seconds")

    # Migrate paddocks (extract registry-relevant fields only)
    pwm_paddocks = pwm_data.get("paddocks", {})
    registry_paddocks = config.setdefault("paddocks", {})

    for pid, paddock in pwm_paddocks.items():
        if pid not in registry_paddocks:
            registry_paddocks[pid] = {
                "farm_id": paddock.get("farm_id", "farm_1"),
                "name": paddock.get("name", pid),
                "bay_prefix": paddock.get("bay_prefix", "B-"),
                "bay_count": paddock.get("bay_count", 0),
                "current_season": paddock.get("current_season", True),
                "created": paddock.get("created", now),
                "modified": now,
            }

    # Migrate bays (extract registry-relevant fields only)
    pwm_bays = pwm_data.get("bays", {})
    registry_bays = config.setdefault("bays", {})

    for bid, bay in pwm_bays.items():
        if bid not in registry_bays:
            registry_bays[bid] = {
                "paddock_id": bay.get("paddock_id", ""),
                "name": bay.get("name", bid),
                "order": bay.get("order", 0),
                "is_last_bay": bay.get("is_last_bay", False),
                "created": bay.get("created", now) if "created" in bay else now,
                "modified": now,
            }

    config["initialized"] = True
    config["version"] = "1.0.0"
    config["created"] = config.get("created", now)
    config["modified"] = now

    log_transaction(
        config, "migrate", "system", "pwm",
        f"Migrated {len(pwm_paddocks)} paddocks, {len(pwm_bays)} bays",
        "From PWM config"
    )
    save_config(config)

    print(json.dumps({
        "success": True,
        "paddocks_migrated": len(pwm_paddocks),
        "bays_migrated": len(pwm_bays),
        "message": "Migration from PWM complete"
    }))
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
            "message": "This will delete all paddock, bay, and season data!"
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
        "seasons": {},
        "transactions": [],
        "version": "1.0.0",
        "created": now,
        "modified": now,
    }
    save_config(config)

    print(json.dumps({
        "success": True,
        "message": "Registry reset complete. All paddocks, bays, and seasons deleted."
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
    parser = argparse.ArgumentParser(description="Farm Registry Backend")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Paddock commands
    p_add = subparsers.add_parser("add_paddock", help="Add a new paddock")
    p_add.add_argument("--farm", help="Farm ID (default: farm_1)")
    p_add.add_argument("--name", required=True, help="Paddock name")
    p_add.add_argument("--bay_prefix", default="B-", help="Bay prefix (e.g., B-)")
    p_add.add_argument("--bay_count", type=int, required=True, help="Number of bays")
    p_add.add_argument("--current_season", type=lambda x: x.lower() == "true",
                       help="Is paddock in current season (true/false)")

    p_edit = subparsers.add_parser("edit_paddock", help="Edit a paddock")
    p_edit.add_argument("--id", required=True, help="Paddock ID")
    p_edit.add_argument("--name", help="New name")
    p_edit.add_argument("--farm", help="Farm ID")
    p_edit.add_argument("--current_season", type=lambda x: x.lower() == "true",
                        help="Is paddock in current season (true/false)")

    p_del = subparsers.add_parser("delete_paddock", help="Delete a paddock")
    p_del.add_argument("--id", required=True, help="Paddock ID")

    p_season = subparsers.add_parser("set_current_season", help="Set paddock current_season flag")
    p_season.add_argument("--id", required=True, help="Paddock ID")
    p_season.add_argument("--value", type=lambda x: x.lower() == "true",
                          help="Current season value (true/false); omit to toggle")

    # Bay commands
    b_add = subparsers.add_parser("add_bay", help="Add a bay to a paddock")
    b_add.add_argument("--paddock", required=True, help="Paddock ID")
    b_add.add_argument("--name", required=True, help="Bay name")
    b_add.add_argument("--order", type=int, help="Bay order")
    b_add.add_argument("--is_last", action="store_true", help="Mark as last bay")

    b_edit = subparsers.add_parser("edit_bay", help="Edit bay info")
    b_edit.add_argument("--id", required=True, help="Bay ID")
    b_edit.add_argument("--name", help="New name")
    b_edit.add_argument("--order", type=int, help="New order")
    b_edit.add_argument("--is_last", type=lambda x: x.lower() == "true", help="Is last bay (true/false)")

    b_del = subparsers.add_parser("delete_bay", help="Delete a bay")
    b_del.add_argument("--id", required=True, help="Bay ID")

    # Season commands
    s_add = subparsers.add_parser("add_season", help="Add a season")
    s_add.add_argument("--name", required=True, help="Season name (e.g., CY26)")
    s_add.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    s_add.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    s_add.add_argument("--active", action="store_true", help="Set as active season")

    s_edit = subparsers.add_parser("edit_season", help="Edit a season")
    s_edit.add_argument("--id", required=True, help="Season ID")
    s_edit.add_argument("--name", help="New name")
    s_edit.add_argument("--start", help="New start date")
    s_edit.add_argument("--end", help="New end date")

    s_del = subparsers.add_parser("delete_season", help="Delete a season")
    s_del.add_argument("--id", required=True, help="Season ID")

    s_active = subparsers.add_parser("set_active_season", help="Set active season")
    s_active.add_argument("--id", required=True, help="Season ID")

    # Farm commands
    f_add = subparsers.add_parser("add_farm", help="Add a new farm")
    f_add.add_argument("--name", required=True, help="Farm name")

    f_edit = subparsers.add_parser("edit_farm", help="Edit a farm")
    f_edit.add_argument("--id", required=True, help="Farm ID")
    f_edit.add_argument("--name", help="New name")

    f_del = subparsers.add_parser("delete_farm", help="Delete a farm")
    f_del.add_argument("--id", required=True, help="Farm ID")

    # System commands
    subparsers.add_parser("init", help="Initialize the system")
    subparsers.add_parser("status", help="Get system status")
    subparsers.add_parser("export", help="Export to backup")
    subparsers.add_parser("migrate_from_pwm", help="Migrate data from PWM config")

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
        "set_current_season": cmd_set_current_season,
        "add_bay": cmd_add_bay,
        "edit_bay": cmd_edit_bay,
        "delete_bay": cmd_delete_bay,
        "add_season": cmd_add_season,
        "edit_season": cmd_edit_season,
        "delete_season": cmd_delete_season,
        "set_active_season": cmd_set_active_season,
        "add_farm": cmd_add_farm,
        "edit_farm": cmd_edit_farm,
        "delete_farm": cmd_delete_farm,
        "init": cmd_init,
        "status": cmd_status,
        "migrate_from_pwm": cmd_migrate_from_pwm,
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
