#!/usr/bin/env python3
"""
STR Backend - Stock Tracker
PaddiSense Farm Management System

This script handles all write operations for the stock tracker system:
  - Mob management: add, edit, delete, adjust counts
  - Movement tracking: move mob, off-farm, return to farm
  - Attribute management: toggle, add/remove types
  - Config management: age classes, crosses, off-farm locations

Data is stored in: /config/local_data/str/mobs.json
Config is stored in: /config/local_data/str/config.json
This file is NOT tracked in git - each farm maintains their own stock data.

Usage:
  python3 str_backend.py init
  python3 str_backend.py add_mob --name "Weaners 2025" --age_class "Weaners" --head_count 150 ...
  python3 str_backend.py move_mob --id "mob_abc123" --to_location "sw5"
"""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Data file locations (outside of git-tracked folders)
DATA_DIR = Path("/config/local_data/str")
MOBS_FILE = DATA_DIR / "mobs.json"
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"

# Registry location for paddock data
REGISTRY_FILE = Path("/config/local_data/registry/config.json")

# Current config version
CONFIG_VERSION = "1.0.0"

# Default age classes
DEFAULT_AGE_CLASSES = [
    "Calves",
    "Weaners",
    "Yearlings",
    "Heifers",
    "Cows",
    "Bulls",
    "Steers",
]

# Default crosses/breeds
DEFAULT_CROSSES = [
    "Angus",
    "Hereford",
    "Angus x Hereford",
    "Brahman",
    "Droughtmaster",
    "Murray Grey",
    "Charolais",
    "Simmental",
    "Shorthorn",
]

# Default attributes
DEFAULT_ATTRIBUTES = [
    {"id": "lick_active", "name": "Lick Active"},
    {"id": "vaccinated", "name": "Vaccinated"},
    {"id": "pregnant", "name": "Pregnant"},
    {"id": "for_sale", "name": "For Sale"},
    {"id": "weaned", "name": "Weaned"},
    {"id": "drenched", "name": "Drenched"},
]

# Default off-farm locations
DEFAULT_OFF_FARM_LOCATIONS = [
    "Agistment",
    "Feedlot",
    "Sold",
    "Deceased",
    "Saleyards",
    "Abattoir",
]


def generate_mob_id() -> str:
    """Generate a unique mob ID."""
    return f"mob_{uuid.uuid4().hex[:8]}"


def load_mobs() -> dict[str, Any]:
    """Load mobs from JSON file, or return empty structure."""
    if not MOBS_FILE.exists():
        return {"mobs": {}, "movements": []}
    try:
        return json.loads(MOBS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"mobs": {}, "movements": []}


def save_mobs(data: dict[str, Any]) -> None:
    """Save mobs to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data["modified"] = datetime.now().isoformat(timespec="seconds")
    MOBS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def load_config() -> dict[str, Any]:
    """Load config from JSON file, or return default structure."""
    if not CONFIG_FILE.exists():
        return create_default_config()
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return config
    except (json.JSONDecodeError, IOError):
        return create_default_config()


def create_default_config() -> dict[str, Any]:
    """Create a new default config."""
    return {
        "version": CONFIG_VERSION,
        "age_classes": DEFAULT_AGE_CLASSES.copy(),
        "crosses": DEFAULT_CROSSES.copy(),
        "attributes": [a.copy() for a in DEFAULT_ATTRIBUTES],
        "off_farm_locations": DEFAULT_OFF_FARM_LOCATIONS.copy(),
        "created": datetime.now().isoformat(timespec="seconds"),
        "modified": datetime.now().isoformat(timespec="seconds"),
    }


def save_config(config: dict[str, Any]) -> None:
    """Save config to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    config["modified"] = datetime.now().isoformat(timespec="seconds")
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def load_registry() -> dict[str, Any]:
    """Load registry data to get paddocks."""
    if not REGISTRY_FILE.exists():
        return {}
    try:
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {}


def get_paddock_name(paddock_id: str) -> str:
    """Get paddock display name from registry."""
    registry = load_registry()
    paddocks = registry.get("paddocks", {})
    paddock = paddocks.get(paddock_id, {})
    return paddock.get("name", paddock_id)


def log_movement(
    data: dict,
    mob_id: str,
    mob_name: str,
    action: str,
    from_location: str = "",
    to_location: str = "",
    head_count: int = 0,
    note: str = "",
) -> None:
    """Append a movement record for audit trail."""
    data.setdefault("movements", []).append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "mob_id": mob_id,
        "mob_name": mob_name,
        "action": action,
        "from_location": from_location,
        "to_location": to_location,
        "head_count": head_count,
        "note": note,
    })


# =========================================================================
# SYSTEM COMMANDS
# =========================================================================

def cmd_status(args: argparse.Namespace) -> int:
    """Return system status as JSON."""
    status = {
        "mobs_file_exists": MOBS_FILE.exists(),
        "config_file_exists": CONFIG_FILE.exists(),
        "registry_exists": REGISTRY_FILE.exists(),
        "config_version": "",
        "status": "not_initialized",
        "mob_count": 0,
        "total_head": 0,
        "movement_count": 0,
        "on_farm_head": 0,
        "off_farm_head": 0,
    }

    # Check config
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            status["config_version"] = config.get("version", "1.0.0")
        except Exception:
            status["status"] = "error"
            status["error"] = "Config file corrupted"
            print(json.dumps(status))
            return 0

    # Check mobs
    if MOBS_FILE.exists():
        try:
            data = load_mobs()
            mobs = data.get("mobs", {})
            status["mob_count"] = len(mobs)
            status["movement_count"] = len(data.get("movements", []))

            total_head = 0
            on_farm_head = 0
            off_farm_head = 0
            for mob in mobs.values():
                head = int(mob.get("head_count", 0))
                total_head += head
                if mob.get("off_farm", False):
                    off_farm_head += head
                else:
                    on_farm_head += head

            status["total_head"] = total_head
            status["on_farm_head"] = on_farm_head
            status["off_farm_head"] = off_farm_head
            status["status"] = "ready"
        except Exception as e:
            status["status"] = "error"
            status["error"] = f"Mobs file corrupted: {e}"
    elif CONFIG_FILE.exists():
        status["status"] = "ready"

    print(json.dumps(status))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize the STR system - create config and mobs files."""
    created = []

    # Create directory
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Create config if missing
    if not CONFIG_FILE.exists():
        config = create_default_config()
        save_config(config)
        created.append("config")

    # Create empty mobs if missing
    if not MOBS_FILE.exists():
        data = {
            "mobs": {},
            "movements": [],
            "created": datetime.now().isoformat(timespec="seconds"),
            "modified": datetime.now().isoformat(timespec="seconds"),
        }
        save_mobs(data)
        created.append("mobs")

    if created:
        print(f"OK:created:{','.join(created)}")
    else:
        print("OK:already_initialized")
    return 0


# =========================================================================
# MOB MANAGEMENT COMMANDS
# =========================================================================

def cmd_add_mob(args: argparse.Namespace) -> int:
    """Add a new mob to the system."""
    config = load_config()
    data = load_mobs()
    mobs = data.setdefault("mobs", {})

    # Validate required fields
    name = args.name.strip() if args.name else ""
    if not name:
        print("ERROR: Mob name is required", file=sys.stderr)
        return 1

    # Validate age class
    age_class = args.age_class.strip() if args.age_class else ""
    if age_class and age_class not in config.get("age_classes", []):
        print(f"ERROR: Invalid age class '{age_class}'", file=sys.stderr)
        return 1

    # Validate cross
    cross = args.cross.strip() if args.cross else ""
    if cross and cross not in config.get("crosses", []):
        print(f"ERROR: Invalid cross '{cross}'", file=sys.stderr)
        return 1

    # Parse head count
    head_count = int(args.head_count) if args.head_count else 0
    if head_count < 0:
        head_count = 0

    # Validate location
    location = args.location.strip() if args.location else ""
    location_name = ""
    if location:
        registry = load_registry()
        paddocks = registry.get("paddocks", {})
        if location not in paddocks:
            print(f"ERROR: Invalid paddock '{location}'", file=sys.stderr)
            return 1
        location_name = paddocks[location].get("name", location)

    # Parse attributes
    attributes = []
    if args.attributes and args.attributes.strip():
        try:
            parsed = json.loads(args.attributes)
            if isinstance(parsed, list):
                valid_attr_ids = [a["id"] for a in config.get("attributes", [])]
                attributes = [a for a in parsed if a in valid_attr_ids]
        except json.JSONDecodeError:
            pass

    # Generate ID
    mob_id = generate_mob_id()
    now = datetime.now().isoformat(timespec="seconds")

    # Create mob record
    mob = {
        "id": mob_id,
        "name": name,
        "cross": cross,
        "age_class": age_class,
        "head_count": head_count,
        "location": location,
        "location_name": location_name,
        "off_farm": False,
        "off_farm_details": None,
        "attributes": attributes,
        "notes": args.notes.strip() if args.notes else "",
        "created": now,
        "modified": now,
    }

    mobs[mob_id] = mob

    # Log movement if location set
    if location:
        log_movement(
            data,
            mob_id=mob_id,
            mob_name=name,
            action="add",
            to_location=location,
            head_count=head_count,
            note="Mob created",
        )

    save_mobs(data)
    print(f"OK:{mob_id}")
    return 0


def cmd_edit_mob(args: argparse.Namespace) -> int:
    """Edit an existing mob's details."""
    config = load_config()
    data = load_mobs()
    mobs = data.get("mobs", {})

    mob_id = args.id.strip() if args.id else ""
    if mob_id not in mobs:
        print(f"ERROR: Mob '{mob_id}' not found", file=sys.stderr)
        return 1

    mob = mobs[mob_id]

    # Update fields if provided
    if args.name is not None:
        mob["name"] = args.name.strip()

    if args.age_class is not None:
        age_class = args.age_class.strip()
        if age_class and age_class not in config.get("age_classes", []):
            print(f"ERROR: Invalid age class '{age_class}'", file=sys.stderr)
            return 1
        mob["age_class"] = age_class

    if args.cross is not None:
        cross = args.cross.strip()
        if cross and cross not in config.get("crosses", []):
            print(f"ERROR: Invalid cross '{cross}'", file=sys.stderr)
            return 1
        mob["cross"] = cross

    if args.notes is not None:
        mob["notes"] = args.notes.strip()

    mob["modified"] = datetime.now().isoformat(timespec="seconds")

    save_mobs(data)
    print(f"OK:{mob_id}")
    return 0


def cmd_delete_mob(args: argparse.Namespace) -> int:
    """Delete a mob from the system."""
    data = load_mobs()
    mobs = data.get("mobs", {})

    mob_id = args.id.strip() if args.id else ""
    if mob_id not in mobs:
        print(f"ERROR: Mob '{mob_id}' not found", file=sys.stderr)
        return 1

    # Require confirmation token
    token = args.token.strip() if args.token else ""
    if token != "CONFIRM":
        print("ERROR: Delete requires --token CONFIRM", file=sys.stderr)
        return 1

    mob_name = mobs[mob_id].get("name", mob_id)
    del mobs[mob_id]

    log_movement(
        data,
        mob_id=mob_id,
        mob_name=mob_name,
        action="delete",
        note="Mob deleted",
    )

    save_mobs(data)
    print(f"OK:deleted:{mob_id}")
    return 0


def cmd_adjust_count(args: argparse.Namespace) -> int:
    """Adjust the head count of a mob (births, deaths, sales)."""
    data = load_mobs()
    mobs = data.get("mobs", {})

    mob_id = args.id.strip() if args.id else ""
    if mob_id not in mobs:
        print(f"ERROR: Mob '{mob_id}' not found", file=sys.stderr)
        return 1

    mob = mobs[mob_id]
    delta = int(args.delta) if args.delta else 0

    if delta == 0:
        print(f"OK:{mob['head_count']}")
        return 0

    old_count = int(mob.get("head_count", 0))
    new_count = max(0, old_count + delta)

    mob["head_count"] = new_count
    mob["modified"] = datetime.now().isoformat(timespec="seconds")

    # Determine action based on delta
    if delta > 0:
        action = "births"
    else:
        reason = args.reason.strip() if args.reason else "reduction"
        action = reason  # death, sale, transfer

    log_movement(
        data,
        mob_id=mob_id,
        mob_name=mob.get("name", mob_id),
        action=action,
        head_count=abs(delta),
        note=args.note.strip() if args.note else f"{action}: {abs(delta)} head",
    )

    save_mobs(data)
    print(f"OK:{new_count}")
    return 0


# =========================================================================
# MOVEMENT COMMANDS
# =========================================================================

def cmd_move_mob(args: argparse.Namespace) -> int:
    """Move a mob to a new paddock."""
    data = load_mobs()
    mobs = data.get("mobs", {})

    mob_id = args.id.strip() if args.id else ""
    if mob_id not in mobs:
        print(f"ERROR: Mob '{mob_id}' not found", file=sys.stderr)
        return 1

    mob = mobs[mob_id]

    # Cannot move if off-farm
    if mob.get("off_farm", False):
        print("ERROR: Cannot move off-farm mob. Return to farm first.", file=sys.stderr)
        return 1

    # Validate destination
    to_location = args.to_location.strip() if args.to_location else ""
    if not to_location:
        print("ERROR: Destination location is required", file=sys.stderr)
        return 1

    registry = load_registry()
    paddocks = registry.get("paddocks", {})
    if to_location not in paddocks:
        print(f"ERROR: Invalid paddock '{to_location}'", file=sys.stderr)
        return 1

    from_location = mob.get("location", "")
    from_name = mob.get("location_name", from_location)
    to_name = paddocks[to_location].get("name", to_location)

    mob["location"] = to_location
    mob["location_name"] = to_name
    mob["modified"] = datetime.now().isoformat(timespec="seconds")

    log_movement(
        data,
        mob_id=mob_id,
        mob_name=mob.get("name", mob_id),
        action="move",
        from_location=from_location,
        to_location=to_location,
        head_count=int(mob.get("head_count", 0)),
        note=args.note.strip() if args.note else "",
    )

    save_mobs(data)
    print(f"OK:moved:{to_location}")
    return 0


def cmd_set_off_farm(args: argparse.Namespace) -> int:
    """Mark a mob as off-farm with a reason."""
    config = load_config()
    data = load_mobs()
    mobs = data.get("mobs", {})

    mob_id = args.id.strip() if args.id else ""
    if mob_id not in mobs:
        print(f"ERROR: Mob '{mob_id}' not found", file=sys.stderr)
        return 1

    mob = mobs[mob_id]

    if mob.get("off_farm", False):
        print("ERROR: Mob is already off-farm", file=sys.stderr)
        return 1

    # Validate off-farm reason
    reason = args.reason.strip() if args.reason else ""
    if not reason:
        print("ERROR: Off-farm reason is required", file=sys.stderr)
        return 1

    valid_reasons = config.get("off_farm_locations", DEFAULT_OFF_FARM_LOCATIONS)
    if reason not in valid_reasons:
        print(f"ERROR: Invalid off-farm reason '{reason}'", file=sys.stderr)
        return 1

    from_location = mob.get("location", "")

    mob["off_farm"] = True
    mob["off_farm_details"] = {
        "reason": reason,
        "date": datetime.now().isoformat(timespec="seconds"),
        "from_location": from_location,
        "note": args.note.strip() if args.note else "",
    }
    mob["location"] = ""
    mob["location_name"] = ""
    mob["modified"] = datetime.now().isoformat(timespec="seconds")

    log_movement(
        data,
        mob_id=mob_id,
        mob_name=mob.get("name", mob_id),
        action="off_farm",
        from_location=from_location,
        to_location=reason,
        head_count=int(mob.get("head_count", 0)),
        note=args.note.strip() if args.note else f"Off-farm: {reason}",
    )

    save_mobs(data)
    print(f"OK:off_farm:{reason}")
    return 0


def cmd_return_to_farm(args: argparse.Namespace) -> int:
    """Return an off-farm mob back to the farm."""
    data = load_mobs()
    mobs = data.get("mobs", {})

    mob_id = args.id.strip() if args.id else ""
    if mob_id not in mobs:
        print(f"ERROR: Mob '{mob_id}' not found", file=sys.stderr)
        return 1

    mob = mobs[mob_id]

    if not mob.get("off_farm", False):
        print("ERROR: Mob is not off-farm", file=sys.stderr)
        return 1

    # Validate destination
    to_location = args.to_location.strip() if args.to_location else ""
    if not to_location:
        print("ERROR: Destination paddock is required", file=sys.stderr)
        return 1

    registry = load_registry()
    paddocks = registry.get("paddocks", {})
    if to_location not in paddocks:
        print(f"ERROR: Invalid paddock '{to_location}'", file=sys.stderr)
        return 1

    off_farm_details = mob.get("off_farm_details", {})
    from_location = off_farm_details.get("reason", "off-farm")
    to_name = paddocks[to_location].get("name", to_location)

    mob["off_farm"] = False
    mob["off_farm_details"] = None
    mob["location"] = to_location
    mob["location_name"] = to_name
    mob["modified"] = datetime.now().isoformat(timespec="seconds")

    log_movement(
        data,
        mob_id=mob_id,
        mob_name=mob.get("name", mob_id),
        action="return",
        from_location=from_location,
        to_location=to_location,
        head_count=int(mob.get("head_count", 0)),
        note=args.note.strip() if args.note else "Returned to farm",
    )

    save_mobs(data)
    print(f"OK:returned:{to_location}")
    return 0


# =========================================================================
# ATTRIBUTE COMMANDS
# =========================================================================

def cmd_toggle_attribute(args: argparse.Namespace) -> int:
    """Toggle an attribute on/off for a mob."""
    config = load_config()
    data = load_mobs()
    mobs = data.get("mobs", {})

    mob_id = args.id.strip() if args.id else ""
    if mob_id not in mobs:
        print(f"ERROR: Mob '{mob_id}' not found", file=sys.stderr)
        return 1

    attr_id = args.attribute.strip() if args.attribute else ""
    valid_attrs = [a["id"] for a in config.get("attributes", [])]
    if attr_id not in valid_attrs:
        print(f"ERROR: Invalid attribute '{attr_id}'", file=sys.stderr)
        return 1

    mob = mobs[mob_id]
    attributes = mob.get("attributes", [])

    if attr_id in attributes:
        attributes.remove(attr_id)
        action = "removed"
    else:
        attributes.append(attr_id)
        action = "added"

    mob["attributes"] = attributes
    mob["modified"] = datetime.now().isoformat(timespec="seconds")

    save_mobs(data)
    print(f"OK:{action}:{attr_id}")
    return 0


def cmd_add_attribute_type(args: argparse.Namespace) -> int:
    """Add a new attribute definition."""
    config = load_config()

    attr_id = args.id.strip() if args.id else ""
    attr_name = args.name.strip() if args.name else ""

    if not attr_id or not attr_name:
        print("ERROR: Attribute ID and name are required", file=sys.stderr)
        return 1

    # Sanitize ID
    attr_id = re.sub(r"[^a-z0-9_]", "_", attr_id.lower())

    attributes = config.get("attributes", [])
    existing_ids = [a["id"] for a in attributes]

    if attr_id in existing_ids:
        print(f"ERROR: Attribute '{attr_id}' already exists", file=sys.stderr)
        return 1

    attributes.append({"id": attr_id, "name": attr_name})
    config["attributes"] = attributes
    save_config(config)

    print(f"OK:{attr_id}")
    return 0


def cmd_remove_attribute_type(args: argparse.Namespace) -> int:
    """Remove an attribute definition."""
    config = load_config()

    attr_id = args.id.strip() if args.id else ""
    if not attr_id:
        print("ERROR: Attribute ID is required", file=sys.stderr)
        return 1

    attributes = config.get("attributes", [])
    matching = [a for a in attributes if a["id"] == attr_id]

    if not matching:
        print(f"ERROR: Attribute '{attr_id}' not found", file=sys.stderr)
        return 1

    # Check if in use by any mob
    data = load_mobs()
    for mob in data.get("mobs", {}).values():
        if attr_id in mob.get("attributes", []):
            print(f"ERROR: Attribute '{attr_id}' is in use", file=sys.stderr)
            return 1

    config["attributes"] = [a for a in attributes if a["id"] != attr_id]
    save_config(config)

    print(f"OK:removed:{attr_id}")
    return 0


# =========================================================================
# CONFIG COMMANDS
# =========================================================================

def cmd_add_age_class(args: argparse.Namespace) -> int:
    """Add a new age class."""
    config = load_config()

    name = args.name.strip() if args.name else ""
    if not name:
        print("ERROR: Age class name is required", file=sys.stderr)
        return 1

    age_classes = config.get("age_classes", [])
    if name in age_classes:
        print(f"ERROR: Age class '{name}' already exists", file=sys.stderr)
        return 1

    age_classes.append(name)
    config["age_classes"] = age_classes
    save_config(config)

    print(f"OK:{name}")
    return 0


def cmd_remove_age_class(args: argparse.Namespace) -> int:
    """Remove an age class."""
    config = load_config()

    name = args.name.strip() if args.name else ""
    if not name:
        print("ERROR: Age class name is required", file=sys.stderr)
        return 1

    age_classes = config.get("age_classes", [])
    if name not in age_classes:
        print(f"ERROR: Age class '{name}' not found", file=sys.stderr)
        return 1

    # Check if in use
    data = load_mobs()
    for mob in data.get("mobs", {}).values():
        if mob.get("age_class") == name:
            print(f"ERROR: Age class '{name}' is in use", file=sys.stderr)
            return 1

    config["age_classes"] = [a for a in age_classes if a != name]
    save_config(config)

    print(f"OK:removed:{name}")
    return 0


def cmd_add_cross(args: argparse.Namespace) -> int:
    """Add a new cross/breed."""
    config = load_config()

    name = args.name.strip() if args.name else ""
    if not name:
        print("ERROR: Cross name is required", file=sys.stderr)
        return 1

    crosses = config.get("crosses", [])
    if name in crosses:
        print(f"ERROR: Cross '{name}' already exists", file=sys.stderr)
        return 1

    crosses.append(name)
    config["crosses"] = crosses
    save_config(config)

    print(f"OK:{name}")
    return 0


def cmd_remove_cross(args: argparse.Namespace) -> int:
    """Remove a cross/breed."""
    config = load_config()

    name = args.name.strip() if args.name else ""
    if not name:
        print("ERROR: Cross name is required", file=sys.stderr)
        return 1

    crosses = config.get("crosses", [])
    if name not in crosses:
        print(f"ERROR: Cross '{name}' not found", file=sys.stderr)
        return 1

    # Check if in use
    data = load_mobs()
    for mob in data.get("mobs", {}).values():
        if mob.get("cross") == name:
            print(f"ERROR: Cross '{name}' is in use", file=sys.stderr)
            return 1

    config["crosses"] = [c for c in crosses if c != name]
    save_config(config)

    print(f"OK:removed:{name}")
    return 0


def cmd_add_off_farm_location(args: argparse.Namespace) -> int:
    """Add a new off-farm location type."""
    config = load_config()

    name = args.name.strip() if args.name else ""
    if not name:
        print("ERROR: Off-farm location name is required", file=sys.stderr)
        return 1

    locations = config.get("off_farm_locations", [])
    if name in locations:
        print(f"ERROR: Off-farm location '{name}' already exists", file=sys.stderr)
        return 1

    locations.append(name)
    config["off_farm_locations"] = locations
    save_config(config)

    print(f"OK:{name}")
    return 0


def cmd_remove_off_farm_location(args: argparse.Namespace) -> int:
    """Remove an off-farm location type."""
    config = load_config()

    name = args.name.strip() if args.name else ""
    if not name:
        print("ERROR: Off-farm location name is required", file=sys.stderr)
        return 1

    locations = config.get("off_farm_locations", [])
    if name not in locations:
        print(f"ERROR: Off-farm location '{name}' not found", file=sys.stderr)
        return 1

    # Check if in use
    data = load_mobs()
    for mob in data.get("mobs", {}).values():
        details = mob.get("off_farm_details", {})
        if details and details.get("reason") == name:
            print(f"ERROR: Off-farm location '{name}' is in use", file=sys.stderr)
            return 1

    config["off_farm_locations"] = [loc for loc in locations if loc != name]
    save_config(config)

    print(f"OK:removed:{name}")
    return 0


# =========================================================================
# DATA MANAGEMENT COMMANDS
# =========================================================================

def cmd_export(args: argparse.Namespace) -> int:
    """Export mobs and config to a timestamped backup file."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = BACKUP_DIR / f"stock_{timestamp}.json"

    mobs_data = load_mobs()
    config = load_config()

    backup_data = {
        "version": CONFIG_VERSION,
        "created": datetime.now().isoformat(timespec="seconds"),
        "type": "str_backup",
        "mobs": mobs_data,
        "config": config,
    }

    backup_file.write_text(
        json.dumps(backup_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"OK:{backup_file.name}")
    return 0


def cmd_import_backup(args: argparse.Namespace) -> int:
    """Import mobs and config from a backup file."""
    filename = args.filename.strip() if args.filename else ""
    if not filename:
        print("ERROR: Filename is required", file=sys.stderr)
        return 1

    backup_file = BACKUP_DIR / filename
    if not backup_file.exists():
        print(f"ERROR: Backup file '{filename}' not found", file=sys.stderr)
        return 1

    try:
        backup_data = json.loads(backup_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in backup file: {e}", file=sys.stderr)
        return 1

    if backup_data.get("type") != "str_backup":
        print("ERROR: File is not a valid STR backup", file=sys.stderr)
        return 1

    mobs_data = backup_data.get("mobs")
    config = backup_data.get("config")

    if not isinstance(mobs_data, dict):
        print("ERROR: Backup contains invalid mobs data", file=sys.stderr)
        return 1

    # Create pre-import backup
    current_mobs = load_mobs()
    current_config = load_config()

    pre_import_backup = {
        "version": CONFIG_VERSION,
        "created": datetime.now().isoformat(timespec="seconds"),
        "type": "str_backup",
        "note": "Pre-import automatic backup",
        "mobs": current_mobs,
        "config": current_config,
    }

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    pre_import_file = BACKUP_DIR / f"pre_import_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
    pre_import_file.write_text(
        json.dumps(pre_import_backup, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Import the data
    save_mobs(mobs_data)
    if config and isinstance(config, dict):
        save_config(config)

    mob_count = len(mobs_data.get("mobs", {}))
    print(f"OK:imported:{mob_count}:{pre_import_file.name}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    """Reset all STR data (requires confirmation token)."""
    token = args.token.strip() if args.token else ""

    if token != "CONFIRM_RESET":
        print("ERROR: Invalid confirmation token. Use --token CONFIRM_RESET", file=sys.stderr)
        return 1

    # Create backup before reset
    current_mobs = load_mobs()
    current_config = load_config()

    if current_mobs.get("mobs"):
        pre_reset_backup = {
            "version": CONFIG_VERSION,
            "created": datetime.now().isoformat(timespec="seconds"),
            "type": "str_backup",
            "note": "Pre-reset automatic backup",
            "mobs": current_mobs,
            "config": current_config,
        }

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        pre_reset_file = BACKUP_DIR / f"pre_reset_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
        pre_reset_file.write_text(
            json.dumps(pre_reset_backup, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # Reset to empty state
    empty_mobs = {
        "mobs": {},
        "movements": [],
        "created": datetime.now().isoformat(timespec="seconds"),
        "modified": datetime.now().isoformat(timespec="seconds"),
    }
    save_mobs(empty_mobs)

    # Reset config to defaults
    reset_config = create_default_config()
    save_config(reset_config)

    print("OK:reset")
    return 0


def cmd_backup_list(args: argparse.Namespace) -> int:
    """List available backup files."""
    backups = []

    if BACKUP_DIR.exists():
        for backup_file in sorted(BACKUP_DIR.glob("*.json"), reverse=True):
            try:
                data = json.loads(backup_file.read_text(encoding="utf-8"))
                mob_count = len(data.get("mobs", {}).get("mobs", {}))
                backups.append({
                    "filename": backup_file.name,
                    "created": data.get("created", ""),
                    "note": data.get("note", ""),
                    "mob_count": mob_count,
                    "size_kb": round(backup_file.stat().st_size / 1024, 1),
                })
            except (json.JSONDecodeError, IOError):
                backups.append({
                    "filename": backup_file.name,
                    "created": "",
                    "note": "Unable to read",
                    "mob_count": 0,
                    "size_kb": round(backup_file.stat().st_size / 1024, 1),
                })

    result = {
        "total": len(backups),
        "backups": backups,
    }

    print(json.dumps(result))
    return 0


# =========================================================================
# ARGUMENT PARSER
# =========================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="str_backend.py",
        description="STR Stock Tracker Backend - PaddiSense"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ----- System Commands -----
    status_p = subparsers.add_parser("status", help="Get system status")
    status_p.set_defaults(func=cmd_status)

    init_p = subparsers.add_parser("init", help="Initialize STR system")
    init_p.set_defaults(func=cmd_init)

    # ----- Mob Management Commands -----
    add_mob_p = subparsers.add_parser("add_mob", help="Add a new mob")
    add_mob_p.add_argument("--name", required=True, help="Mob name")
    add_mob_p.add_argument("--age_class", default="", help="Age class")
    add_mob_p.add_argument("--cross", default="", help="Cross/breed")
    add_mob_p.add_argument("--head_count", type=int, default=0, help="Head count")
    add_mob_p.add_argument("--location", default="", help="Initial paddock ID")
    add_mob_p.add_argument("--attributes", default="[]", help="Attributes as JSON array")
    add_mob_p.add_argument("--notes", default="", help="Notes")
    add_mob_p.set_defaults(func=cmd_add_mob)

    edit_mob_p = subparsers.add_parser("edit_mob", help="Edit mob details")
    edit_mob_p.add_argument("--id", required=True, help="Mob ID")
    edit_mob_p.add_argument("--name", help="New name")
    edit_mob_p.add_argument("--age_class", help="New age class")
    edit_mob_p.add_argument("--cross", help="New cross/breed")
    edit_mob_p.add_argument("--notes", help="New notes")
    edit_mob_p.set_defaults(func=cmd_edit_mob)

    del_mob_p = subparsers.add_parser("delete_mob", help="Delete a mob")
    del_mob_p.add_argument("--id", required=True, help="Mob ID")
    del_mob_p.add_argument("--token", required=True, help="Confirmation token (CONFIRM)")
    del_mob_p.set_defaults(func=cmd_delete_mob)

    adjust_p = subparsers.add_parser("adjust_count", help="Adjust head count")
    adjust_p.add_argument("--id", required=True, help="Mob ID")
    adjust_p.add_argument("--delta", type=int, required=True, help="Change amount (+/-)")
    adjust_p.add_argument("--reason", default="", help="Reason (death, sale, transfer)")
    adjust_p.add_argument("--note", default="", help="Note")
    adjust_p.set_defaults(func=cmd_adjust_count)

    # ----- Movement Commands -----
    move_p = subparsers.add_parser("move_mob", help="Move mob to paddock")
    move_p.add_argument("--id", required=True, help="Mob ID")
    move_p.add_argument("--to_location", required=True, help="Destination paddock ID")
    move_p.add_argument("--note", default="", help="Note")
    move_p.set_defaults(func=cmd_move_mob)

    off_farm_p = subparsers.add_parser("set_off_farm", help="Mark mob as off-farm")
    off_farm_p.add_argument("--id", required=True, help="Mob ID")
    off_farm_p.add_argument("--reason", required=True, help="Off-farm reason")
    off_farm_p.add_argument("--note", default="", help="Note")
    off_farm_p.set_defaults(func=cmd_set_off_farm)

    return_p = subparsers.add_parser("return_to_farm", help="Return mob to farm")
    return_p.add_argument("--id", required=True, help="Mob ID")
    return_p.add_argument("--to_location", required=True, help="Destination paddock ID")
    return_p.add_argument("--note", default="", help="Note")
    return_p.set_defaults(func=cmd_return_to_farm)

    # ----- Attribute Commands -----
    toggle_attr_p = subparsers.add_parser("toggle_attribute", help="Toggle mob attribute")
    toggle_attr_p.add_argument("--id", required=True, help="Mob ID")
    toggle_attr_p.add_argument("--attribute", required=True, help="Attribute ID")
    toggle_attr_p.set_defaults(func=cmd_toggle_attribute)

    add_attr_p = subparsers.add_parser("add_attribute_type", help="Add attribute type")
    add_attr_p.add_argument("--id", required=True, help="Attribute ID")
    add_attr_p.add_argument("--name", required=True, help="Attribute name")
    add_attr_p.set_defaults(func=cmd_add_attribute_type)

    rem_attr_p = subparsers.add_parser("remove_attribute_type", help="Remove attribute type")
    rem_attr_p.add_argument("--id", required=True, help="Attribute ID")
    rem_attr_p.set_defaults(func=cmd_remove_attribute_type)

    # ----- Config Commands -----
    add_age_p = subparsers.add_parser("add_age_class", help="Add age class")
    add_age_p.add_argument("--name", required=True, help="Age class name")
    add_age_p.set_defaults(func=cmd_add_age_class)

    rem_age_p = subparsers.add_parser("remove_age_class", help="Remove age class")
    rem_age_p.add_argument("--name", required=True, help="Age class name")
    rem_age_p.set_defaults(func=cmd_remove_age_class)

    add_cross_p = subparsers.add_parser("add_cross", help="Add cross/breed")
    add_cross_p.add_argument("--name", required=True, help="Cross name")
    add_cross_p.set_defaults(func=cmd_add_cross)

    rem_cross_p = subparsers.add_parser("remove_cross", help="Remove cross/breed")
    rem_cross_p.add_argument("--name", required=True, help="Cross name")
    rem_cross_p.set_defaults(func=cmd_remove_cross)

    add_off_farm_p = subparsers.add_parser("add_off_farm_location", help="Add off-farm location")
    add_off_farm_p.add_argument("--name", required=True, help="Location name")
    add_off_farm_p.set_defaults(func=cmd_add_off_farm_location)

    rem_off_farm_p = subparsers.add_parser("remove_off_farm_location", help="Remove off-farm location")
    rem_off_farm_p.add_argument("--name", required=True, help="Location name")
    rem_off_farm_p.set_defaults(func=cmd_remove_off_farm_location)

    # ----- Data Management Commands -----
    export_p = subparsers.add_parser("export", help="Export data to backup file")
    export_p.set_defaults(func=cmd_export)

    import_p = subparsers.add_parser("import_backup", help="Import data from backup file")
    import_p.add_argument("--filename", required=True, help="Backup filename")
    import_p.set_defaults(func=cmd_import_backup)

    reset_p = subparsers.add_parser("reset", help="Reset all data (requires confirmation)")
    reset_p.add_argument("--token", required=True, help="Confirmation token (CONFIRM_RESET)")
    reset_p.set_defaults(func=cmd_reset)

    backup_list_p = subparsers.add_parser("backup_list", help="List available backups")
    backup_list_p.set_defaults(func=cmd_backup_list)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
