#!/usr/bin/env python3
"""
WSS Backend - Worker Safety System
PaddiSense Farm Management System

This script handles all write operations for the worker safety system:
  - System: init, status
  - User discovery and management
  - Zone configuration
  - Role assignment
  - Timing configuration
  - Legacy data import

Data is stored in: /config/local_data/wss/
This file is NOT tracked in git - each farm maintains their own safety data.

Usage:
  python3 wss_backend.py init
  python3 wss_backend.py discover_users
  python3 wss_backend.py set_user_enabled --user_id "user_abc123" --enabled true
"""

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Data file locations (outside of git-tracked folders)
DATA_DIR = Path("/config/local_data/wss")
CONFIG_FILE = DATA_DIR / "config.json"
USERS_FILE = DATA_DIR / "users.json"
BACKUP_DIR = DATA_DIR / "backups"

# Legacy file locations for import
LEGACY_USERS_FILE = Path("/config/PaddiSense/reference/old safety system files/safety_system_users (1).json")
LEGACY_ZONES_FILE = Path("/config/PaddiSense/reference/old safety system files/safety_system_zone_config (1).json")

# Current config version
CONFIG_VERSION = "1.0.0"


def generate_user_id() -> str:
    """Generate a unique user ID."""
    return f"user_{uuid.uuid4().hex[:8]}"


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
        "timing": {
            "stationary_threshold_minutes": 15,
            "first_reminder_minutes": 5,
            "primary_escalation_minutes": 5,
            "secondary_escalation_minutes": 10,
        },
        "working_hours": {
            "start_time": "06:00",
            "end_time": "17:00",
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
        },
        "roles": {
            "primary": "",
            "secondary": "",
            "admins": [],
        },
        "zones": {},
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


def load_users() -> dict[str, Any]:
    """Load users from JSON file, or return empty structure."""
    if not USERS_FILE.exists():
        return {"users": {}}
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"users": {}}


def save_users(data: dict[str, Any]) -> None:
    """Save users to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data["modified"] = datetime.now().isoformat(timespec="seconds")
    USERS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


# =========================================================================
# SYSTEM COMMANDS
# =========================================================================

def cmd_status(args: argparse.Namespace) -> int:
    """Return system status as JSON."""
    status = {
        "config_file_exists": CONFIG_FILE.exists(),
        "users_file_exists": USERS_FILE.exists(),
        "config_version": "",
        "status": "not_initialized",
        "user_count": 0,
        "enabled_user_count": 0,
        "zone_count": 0,
        "monitored_zone_count": 0,
        "has_primary": False,
        "has_secondary": False,
    }

    # Check config
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            status["config_version"] = config.get("version", "1.0.0")
            zones = config.get("zones", {})
            status["zone_count"] = len(zones)
            status["monitored_zone_count"] = sum(
                1 for z in zones.values() if z.get("monitored", False)
            )
            roles = config.get("roles", {})
            status["has_primary"] = bool(roles.get("primary"))
            status["has_secondary"] = bool(roles.get("secondary"))
            status["status"] = "ready"
        except Exception as e:
            status["status"] = "error"
            status["error"] = f"Config file corrupted: {e}"
            print(json.dumps(status))
            return 0

    # Check users
    if USERS_FILE.exists():
        try:
            data = load_users()
            users = data.get("users", {})
            status["user_count"] = len(users)
            status["enabled_user_count"] = sum(
                1 for u in users.values() if u.get("enabled", False)
            )
        except Exception as e:
            status["status"] = "error"
            status["error"] = f"Users file corrupted: {e}"
    elif CONFIG_FILE.exists():
        status["status"] = "ready"

    print(json.dumps(status))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize the WSS system - create config and users files."""
    created = []

    # Create directory
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Create config if missing
    if not CONFIG_FILE.exists():
        config = create_default_config()
        save_config(config)
        created.append("config")

    # Create empty users if missing
    if not USERS_FILE.exists():
        data = {
            "users": {},
            "created": datetime.now().isoformat(timespec="seconds"),
            "modified": datetime.now().isoformat(timespec="seconds"),
        }
        save_users(data)
        created.append("users")

    if created:
        print(f"OK:created:{','.join(created)}")
    else:
        print("OK:already_initialized")
    return 0


# =========================================================================
# USER DISCOVERY AND MANAGEMENT
# =========================================================================

def cmd_discover_users(args: argparse.Namespace) -> int:
    """
    Discover users from Home Assistant Person entities.

    This command accepts discovered user data via:
    - --users_json: JSON string with user array
    - --users_file: Path to JSON file with user array

    Note: The preferred method is now using add_user command in a loop.
    """
    users_json = ""

    # Try to get data from file first
    if hasattr(args, 'users_file') and args.users_file:
        users_file = Path(args.users_file)
        if users_file.exists():
            try:
                users_json = users_file.read_text(encoding='utf-8')
            except IOError as e:
                print(f"ERROR: Failed to read file: {e}", file=sys.stderr)
                return 1

    # Fall back to JSON argument
    if not users_json and hasattr(args, 'users_json') and args.users_json:
        users_json = args.users_json.strip()

    if not users_json:
        print("OK:no_data")
        return 0

    try:
        discovered = json.loads(users_json)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
        return 1

    if not isinstance(discovered, list):
        print("ERROR: users data must be a JSON array", file=sys.stderr)
        return 1

    data = load_users()
    users = data.get("users", {})

    added = 0
    updated = 0

    for person in discovered:
        person_id = person.get("person_id", "")
        if not person_id:
            continue

        # Check if user already exists by person_id
        existing_id = None
        for uid, u in users.items():
            if u.get("person_id") == person_id:
                existing_id = uid
                break

        if existing_id:
            # Update existing user's device IDs (they may have changed)
            users[existing_id]["tracker_id"] = person.get("tracker_id", "")
            users[existing_id]["activity_id"] = person.get("activity_id", "")
            users[existing_id]["notify_id"] = person.get("notify_id", "")
            users[existing_id]["username"] = person.get("username", "")
            updated += 1
        else:
            # Add new user
            user_id = generate_user_id()
            users[user_id] = {
                "id": user_id,
                "person_id": person_id,
                "username": person.get("username", ""),
                "tracker_id": person.get("tracker_id", ""),
                "activity_id": person.get("activity_id", ""),
                "notify_id": person.get("notify_id", ""),
                "enabled": False,  # Default to disabled, admin enables
                "track_external": False,
            }
            added += 1

    data["users"] = users
    save_users(data)

    print(f"OK:added:{added}:updated:{updated}")
    return 0


def cmd_add_user(args: argparse.Namespace) -> int:
    """Add or update a single user (called from HA script)."""
    person_id = args.person_id.strip() if args.person_id else ""
    if not person_id:
        print("ERROR: --person_id is required", file=sys.stderr)
        return 1

    data = load_users()
    users = data.get("users", {})

    # Check if user already exists by person_id
    existing_id = None
    for uid, u in users.items():
        if u.get("person_id") == person_id:
            existing_id = uid
            break

    username = args.username.strip() if args.username else ""
    tracker_id = args.tracker_id.strip() if args.tracker_id else ""
    activity_id = args.activity_id.strip() if args.activity_id else ""
    notify_id = args.notify_id.strip() if args.notify_id else ""

    if existing_id:
        # Update existing user's device IDs (they may have changed)
        users[existing_id]["tracker_id"] = tracker_id
        users[existing_id]["activity_id"] = activity_id
        users[existing_id]["notify_id"] = notify_id
        users[existing_id]["username"] = username
        save_users(data)
        print(f"OK:updated:{existing_id}")
    else:
        # Add new user
        user_id = generate_user_id()
        users[user_id] = {
            "id": user_id,
            "person_id": person_id,
            "username": username,
            "tracker_id": tracker_id,
            "activity_id": activity_id,
            "notify_id": notify_id,
            "enabled": False,  # Default to disabled, admin enables
            "track_external": False,
        }
        data["users"] = users
        save_users(data)
        print(f"OK:added:{user_id}")

    return 0


def cmd_set_user_enabled(args: argparse.Namespace) -> int:
    """Enable or disable a user for safety monitoring."""
    user_id = args.user_id.strip() if args.user_id else ""
    if not user_id:
        print("ERROR: --user_id is required", file=sys.stderr)
        return 1

    enabled = args.enabled.lower() in ("true", "1", "yes", "on") if args.enabled else False

    data = load_users()
    users = data.get("users", {})

    if user_id not in users:
        print(f"ERROR: User '{user_id}' not found", file=sys.stderr)
        return 1

    users[user_id]["enabled"] = enabled
    save_users(data)

    print(f"OK:{user_id}:enabled:{enabled}")
    return 0


def cmd_set_user_track_external(args: argparse.Namespace) -> int:
    """Enable or disable external travel tracking for a user."""
    user_id = args.user_id.strip() if args.user_id else ""
    if not user_id:
        print("ERROR: --user_id is required", file=sys.stderr)
        return 1

    track_external = args.track_external.lower() in ("true", "1", "yes", "on") if args.track_external else False

    data = load_users()
    users = data.get("users", {})

    if user_id not in users:
        print(f"ERROR: User '{user_id}' not found", file=sys.stderr)
        return 1

    users[user_id]["track_external"] = track_external
    save_users(data)

    print(f"OK:{user_id}:track_external:{track_external}")
    return 0


# =========================================================================
# ZONE CONFIGURATION
# =========================================================================

def cmd_set_zone_config(args: argparse.Namespace) -> int:
    """Configure a zone's monitoring settings."""
    zone_id = args.zone_id.strip() if args.zone_id else ""
    if not zone_id:
        print("ERROR: --zone_id is required", file=sys.stderr)
        return 1

    config = load_config()
    zones = config.setdefault("zones", {})

    # Get current zone config or create new
    zone = zones.get(zone_id, {
        "monitored": False,
        "away": False,
        "name": zone_id.replace("zone.", "").replace("_", " ").title(),
    })

    # Update fields if provided
    if args.monitored is not None:
        zone["monitored"] = args.monitored.lower() in ("true", "1", "yes", "on")

    if args.away is not None:
        zone["away"] = args.away.lower() in ("true", "1", "yes", "on")

    if args.name is not None:
        zone["name"] = args.name.strip()

    zones[zone_id] = zone
    save_config(config)

    print(f"OK:{zone_id}:monitored:{zone['monitored']}:away:{zone['away']}")
    return 0


def cmd_add_zone(args: argparse.Namespace) -> int:
    """Add or update a single zone (called from HA script)."""
    zone_id = args.zone_id.strip() if args.zone_id else ""
    if not zone_id:
        print("ERROR: --zone_id is required", file=sys.stderr)
        return 1

    zone_name = args.zone_name.strip() if args.zone_name else zone_id.replace("zone.", "").replace("_", " ").title()

    config = load_config()
    zones = config.setdefault("zones", {})

    if zone_id in zones:
        # Update existing zone's name
        zones[zone_id]["name"] = zone_name
        save_config(config)
        print(f"OK:updated:{zone_id}")
    else:
        # Add new zone with defaults
        zones[zone_id] = {
            "monitored": False,
            "away": False,
            "name": zone_name,
        }
        save_config(config)
        print(f"OK:added:{zone_id}")

    return 0


def cmd_discover_zones(args: argparse.Namespace) -> int:
    """Discover zones from Home Assistant and sync with config.

    - Adds new zones with default settings (monitored=false, away=false)
    - Updates names for existing zones to match HA
    - Removes zones that no longer exist in HA

    Note: The preferred method is now using add_zone command in a loop.
    """
    zones_json = args.zones_json.strip() if hasattr(args, 'zones_json') and args.zones_json else ""

    if not zones_json:
        print("OK:no_data")
        return 0

    try:
        discovered = json.loads(zones_json)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
        return 1

    if not isinstance(discovered, list):
        print("ERROR: Expected JSON array of zones", file=sys.stderr)
        return 1

    config = load_config()
    zones = config.setdefault("zones", {})

    # Build set of zone IDs from HA
    ha_zone_ids = set()
    for zone_data in discovered:
        zone_id = zone_data.get("id", "")
        if zone_id and zone_id.startswith("zone."):
            ha_zone_ids.add(zone_id)

    added = 0
    updated = 0
    removed = 0

    # Add new zones and update names for existing ones
    for zone_data in discovered:
        zone_id = zone_data.get("id", "")
        if not zone_id or not zone_id.startswith("zone."):
            continue

        ha_name = zone_data.get("name", zone_id.replace("zone.", "").replace("_", " ").title())

        if zone_id not in zones:
            # New zone - add with defaults
            zones[zone_id] = {
                "monitored": False,
                "away": False,
                "name": ha_name,
            }
            added += 1
        else:
            # Existing zone - update name to match HA
            if zones[zone_id].get("name") != ha_name:
                zones[zone_id]["name"] = ha_name
                updated += 1

    # Remove zones that no longer exist in HA
    stale_ids = [zid for zid in zones.keys() if zid not in ha_zone_ids]
    for zid in stale_ids:
        del zones[zid]
        removed += 1

    if added > 0 or updated > 0 or removed > 0:
        save_config(config)

    print(f"OK:added:{added}:updated:{updated}:removed:{removed}")
    return 0


def cmd_toggle_zone_monitored(args: argparse.Namespace) -> int:
    """Toggle zone's monitored flag (independent of away setting)."""
    zone_id = args.zone_id.strip() if args.zone_id else ""
    if not zone_id:
        print("ERROR: --zone_id is required", file=sys.stderr)
        return 1

    config = load_config()
    zones = config.setdefault("zones", {})

    zone = zones.get(zone_id, {
        "monitored": False,
        "away": False,
        "name": zone_id.replace("zone.", "").replace("_", " ").title(),
    })

    zone["monitored"] = not zone.get("monitored", False)
    # monitored and away are now independent - no longer mutually exclusive

    zones[zone_id] = zone
    save_config(config)

    print(f"OK:{zone_id}:monitored:{zone['monitored']}")
    return 0


def cmd_toggle_zone_away(args: argparse.Namespace) -> int:
    """Toggle zone's away flag (independent of monitored setting)."""
    zone_id = args.zone_id.strip() if args.zone_id else ""
    if not zone_id:
        print("ERROR: --zone_id is required", file=sys.stderr)
        return 1

    config = load_config()
    zones = config.setdefault("zones", {})

    zone = zones.get(zone_id, {
        "monitored": False,
        "away": False,
        "name": zone_id.replace("zone.", "").replace("_", " ").title(),
    })

    zone["away"] = not zone.get("away", False)
    # monitored and away are now independent - no longer mutually exclusive

    zones[zone_id] = zone
    save_config(config)

    print(f"OK:{zone_id}:away:{zone['away']}")
    return 0


# =========================================================================
# ROLE ASSIGNMENT
# =========================================================================

def cmd_set_role(args: argparse.Namespace) -> int:
    """Set a role assignment (primary, secondary, or admin)."""
    role = args.role.strip().lower() if args.role else ""
    user_id = args.user_id.strip() if args.user_id else ""

    if role not in ("primary", "secondary", "admin"):
        print("ERROR: --role must be 'primary', 'secondary', or 'admin'", file=sys.stderr)
        return 1

    # Validate user exists
    if user_id:
        data = load_users()
        users = data.get("users", {})
        if user_id not in users:
            print(f"ERROR: User '{user_id}' not found", file=sys.stderr)
            return 1

    config = load_config()
    roles = config.setdefault("roles", {"primary": "", "secondary": "", "admins": []})

    if role == "admin":
        # Add to admins list
        admins = roles.get("admins", [])
        if user_id and user_id not in admins:
            admins.append(user_id)
            roles["admins"] = admins
    else:
        # Set primary or secondary
        roles[role] = user_id

    save_config(config)
    print(f"OK:{role}:{user_id}")
    return 0


def cmd_remove_admin(args: argparse.Namespace) -> int:
    """Remove a user from the admin list."""
    user_id = args.user_id.strip() if args.user_id else ""
    if not user_id:
        print("ERROR: --user_id is required", file=sys.stderr)
        return 1

    config = load_config()
    roles = config.setdefault("roles", {"primary": "", "secondary": "", "admins": []})
    admins = roles.get("admins", [])

    if user_id in admins:
        admins.remove(user_id)
        roles["admins"] = admins
        save_config(config)
        print(f"OK:removed:{user_id}")
    else:
        print(f"OK:not_admin:{user_id}")

    return 0


# =========================================================================
# TIMING CONFIGURATION
# =========================================================================

def cmd_set_timing(args: argparse.Namespace) -> int:
    """Set timing thresholds."""
    config = load_config()
    timing = config.setdefault("timing", {
        "stationary_threshold_minutes": 15,
        "first_reminder_minutes": 5,
        "primary_escalation_minutes": 5,
        "secondary_escalation_minutes": 10,
    })

    updated = []

    if args.stationary_threshold is not None:
        val = max(1, min(60, int(args.stationary_threshold)))
        timing["stationary_threshold_minutes"] = val
        updated.append(f"stationary:{val}")

    if args.first_reminder is not None:
        val = max(1, min(30, int(args.first_reminder)))
        timing["first_reminder_minutes"] = val
        updated.append(f"first_reminder:{val}")

    if args.primary_escalation is not None:
        val = max(1, min(30, int(args.primary_escalation)))
        timing["primary_escalation_minutes"] = val
        updated.append(f"primary_escalation:{val}")

    if args.secondary_escalation is not None:
        val = max(1, min(60, int(args.secondary_escalation)))
        timing["secondary_escalation_minutes"] = val
        updated.append(f"secondary_escalation:{val}")

    if updated:
        save_config(config)
        print(f"OK:{','.join(updated)}")
    else:
        print("OK:no_changes")

    return 0


def cmd_set_working_hours(args: argparse.Namespace) -> int:
    """Set working hours configuration."""
    config = load_config()
    working_hours = config.setdefault("working_hours", {
        "start_time": "06:00",
        "end_time": "17:00",
        "workdays": ["mon", "tue", "wed", "thu", "fri"],
    })

    updated = []

    if args.start_time is not None:
        # Validate time format HH:MM
        start_time = args.start_time.strip()
        if len(start_time) >= 5 and ":" in start_time:
            working_hours["start_time"] = start_time[:5]
            updated.append(f"start_time:{start_time[:5]}")

    if args.end_time is not None:
        # Validate time format HH:MM
        end_time = args.end_time.strip()
        if len(end_time) >= 5 and ":" in end_time:
            working_hours["end_time"] = end_time[:5]
            updated.append(f"end_time:{end_time[:5]}")

    if args.workdays is not None:
        workdays_input = args.workdays.strip()
        # Handle presets
        if workdays_input == "Mon-Fri":
            workdays = ["mon", "tue", "wed", "thu", "fri"]
        elif workdays_input == "Mon-Sat":
            workdays = ["mon", "tue", "wed", "thu", "fri", "sat"]
        elif workdays_input == "Every Day":
            workdays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        elif workdays_input == "Custom":
            # Keep existing workdays for custom
            workdays = working_hours.get("workdays", ["mon", "tue", "wed", "thu", "fri"])
        else:
            # Parse comma-separated list of days
            days = [d.strip().lower()[:3] for d in workdays_input.split(",")]
            valid_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            workdays = [d for d in days if d in valid_days]

        working_hours["workdays"] = workdays
        updated.append(f"workdays:{','.join(workdays)}")

    if updated:
        save_config(config)
        print(f"OK:{','.join(updated)}")
    else:
        print("OK:no_changes")

    return 0


# =========================================================================
# DATA MANAGEMENT
# =========================================================================

def cmd_export(args: argparse.Namespace) -> int:
    """Export config and users to a timestamped backup file."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = BACKUP_DIR / f"wss_{timestamp}.json"

    users_data = load_users()
    config = load_config()

    backup_data = {
        "version": CONFIG_VERSION,
        "created": datetime.now().isoformat(timespec="seconds"),
        "type": "wss_backup",
        "config": config,
        "users": users_data,
    }

    backup_file.write_text(
        json.dumps(backup_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"OK:{backup_file.name}")
    return 0


def cmd_import_legacy(args: argparse.Namespace) -> int:
    """Import data from the old safety system JSON files."""
    # Check for legacy files
    users_file = Path(args.users_file) if args.users_file else LEGACY_USERS_FILE
    zones_file = Path(args.zones_file) if args.zones_file else LEGACY_ZONES_FILE

    imported = []

    # Import users
    if users_file.exists():
        try:
            legacy_users = json.loads(users_file.read_text(encoding="utf-8"))
            legacy_user_list = legacy_users.get("users", [])

            data = load_users()
            users = data.get("users", {})

            for lu in legacy_user_list:
                person_id = lu.get("personID", "")
                if not person_id:
                    continue

                # Check if already exists
                exists = any(u.get("person_id") == person_id for u in users.values())
                if exists:
                    continue

                user_id = generate_user_id()
                users[user_id] = {
                    "id": user_id,
                    "person_id": person_id,
                    "username": lu.get("username", ""),
                    "tracker_id": lu.get("trackerID", ""),
                    "activity_id": lu.get("activityID", ""),
                    "notify_id": lu.get("notifyID", ""),
                    "enabled": True,  # Legacy users were enabled
                    "track_external": False,
                }

            data["users"] = users
            save_users(data)
            imported.append(f"users:{len(legacy_user_list)}")
        except Exception as e:
            print(f"ERROR: Failed to import users: {e}", file=sys.stderr)
            return 1

    # Import zones
    if zones_file.exists():
        try:
            legacy_zones = json.loads(zones_file.read_text(encoding="utf-8"))
            legacy_zone_list = legacy_zones.get("zones", [])

            config = load_config()
            zones = config.setdefault("zones", {})

            for lz in legacy_zone_list:
                zone_id = lz.get("entity", "")
                if not zone_id:
                    continue

                zones[zone_id] = {
                    "monitored": lz.get("monitored", False),
                    "away": lz.get("away", False),
                    "name": lz.get("name", zone_id.replace("zone.", "").replace("_", " ").title()),
                }

            save_config(config)
            imported.append(f"zones:{len(legacy_zone_list)}")
        except Exception as e:
            print(f"ERROR: Failed to import zones: {e}", file=sys.stderr)
            return 1

    if imported:
        print(f"OK:{','.join(imported)}")
    else:
        print("ERROR: No legacy files found", file=sys.stderr)
        return 1

    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    """Reset all WSS data (requires confirmation token)."""
    token = args.token.strip() if args.token else ""

    if token != "CONFIRM_RESET":
        print("ERROR: Invalid confirmation token. Use --token CONFIRM_RESET", file=sys.stderr)
        return 1

    # Create backup before reset
    current_users = load_users()
    current_config = load_config()

    if current_users.get("users") or current_config.get("zones"):
        pre_reset_backup = {
            "version": CONFIG_VERSION,
            "created": datetime.now().isoformat(timespec="seconds"),
            "type": "wss_backup",
            "note": "Pre-reset automatic backup",
            "config": current_config,
            "users": current_users,
        }

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        pre_reset_file = BACKUP_DIR / f"pre_reset_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
        pre_reset_file.write_text(
            json.dumps(pre_reset_backup, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # Reset to empty state
    empty_users = {
        "users": {},
        "created": datetime.now().isoformat(timespec="seconds"),
        "modified": datetime.now().isoformat(timespec="seconds"),
    }
    save_users(empty_users)

    # Reset config to defaults
    reset_config = create_default_config()
    save_config(reset_config)

    print("OK:reset")
    return 0


# =========================================================================
# ARGUMENT PARSER
# =========================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="wss_backend.py",
        description="WSS Worker Safety System Backend - PaddiSense"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ----- System Commands -----
    status_p = subparsers.add_parser("status", help="Get system status")
    status_p.set_defaults(func=cmd_status)

    init_p = subparsers.add_parser("init", help="Initialize WSS system")
    init_p.set_defaults(func=cmd_init)

    # ----- User Management Commands -----
    discover_p = subparsers.add_parser("discover_users", help="Discover users from HA (legacy)")
    discover_p.add_argument("--users_json", help="JSON array of discovered users")
    discover_p.add_argument("--users_file", help="Path to JSON file with discovered users")
    discover_p.set_defaults(func=cmd_discover_users)

    add_user_p = subparsers.add_parser("add_user", help="Add or update a single user")
    add_user_p.add_argument("--person_id", required=True, help="Person entity ID")
    add_user_p.add_argument("--username", help="Display name")
    add_user_p.add_argument("--tracker_id", help="Device tracker entity ID")
    add_user_p.add_argument("--activity_id", help="Activity sensor entity ID")
    add_user_p.add_argument("--notify_id", help="Notify service ID")
    add_user_p.set_defaults(func=cmd_add_user)

    enable_p = subparsers.add_parser("set_user_enabled", help="Enable/disable user")
    enable_p.add_argument("--user_id", required=True, help="User ID")
    enable_p.add_argument("--enabled", required=True, help="true/false")
    enable_p.set_defaults(func=cmd_set_user_enabled)

    track_ext_p = subparsers.add_parser("set_user_track_external", help="Set external tracking")
    track_ext_p.add_argument("--user_id", required=True, help="User ID")
    track_ext_p.add_argument("--track_external", required=True, help="true/false")
    track_ext_p.set_defaults(func=cmd_set_user_track_external)

    # ----- Zone Configuration Commands -----
    add_zone_p = subparsers.add_parser("add_zone", help="Add or update a single zone")
    add_zone_p.add_argument("--zone_id", required=True, help="Zone entity ID")
    add_zone_p.add_argument("--zone_name", help="Display name")
    add_zone_p.set_defaults(func=cmd_add_zone)

    disc_zones_p = subparsers.add_parser("discover_zones", help="Discover zones from HA (legacy)")
    disc_zones_p.add_argument("--zones_json", help="JSON array of zones")
    disc_zones_p.set_defaults(func=cmd_discover_zones)

    zone_p = subparsers.add_parser("set_zone_config", help="Configure zone")
    zone_p.add_argument("--zone_id", required=True, help="Zone entity ID")
    zone_p.add_argument("--monitored", help="true/false")
    zone_p.add_argument("--away", help="true/false")
    zone_p.add_argument("--name", help="Display name")
    zone_p.set_defaults(func=cmd_set_zone_config)

    toggle_mon_p = subparsers.add_parser("toggle_zone_monitored", help="Toggle zone monitored")
    toggle_mon_p.add_argument("--zone_id", required=True, help="Zone entity ID")
    toggle_mon_p.set_defaults(func=cmd_toggle_zone_monitored)

    toggle_away_p = subparsers.add_parser("toggle_zone_away", help="Toggle zone away")
    toggle_away_p.add_argument("--zone_id", required=True, help="Zone entity ID")
    toggle_away_p.set_defaults(func=cmd_toggle_zone_away)

    # ----- Role Commands -----
    role_p = subparsers.add_parser("set_role", help="Set role assignment")
    role_p.add_argument("--role", required=True, help="primary/secondary/admin")
    role_p.add_argument("--user_id", required=True, help="User ID")
    role_p.set_defaults(func=cmd_set_role)

    rm_admin_p = subparsers.add_parser("remove_admin", help="Remove admin role")
    rm_admin_p.add_argument("--user_id", required=True, help="User ID")
    rm_admin_p.set_defaults(func=cmd_remove_admin)

    # ----- Timing Commands -----
    timing_p = subparsers.add_parser("set_timing", help="Set timing thresholds")
    timing_p.add_argument("--stationary_threshold", type=int, help="Minutes (5-60)")
    timing_p.add_argument("--first_reminder", type=int, help="Minutes (1-30)")
    timing_p.add_argument("--primary_escalation", type=int, help="Minutes (1-30)")
    timing_p.add_argument("--secondary_escalation", type=int, help="Minutes (5-60)")
    timing_p.set_defaults(func=cmd_set_timing)

    hours_p = subparsers.add_parser("set_working_hours", help="Set working hours")
    hours_p.add_argument("--start_time", help="Start time HH:MM")
    hours_p.add_argument("--end_time", help="End time HH:MM")
    hours_p.add_argument("--workdays", help="Workdays preset or comma-separated days")
    hours_p.set_defaults(func=cmd_set_working_hours)

    # ----- Data Management Commands -----
    export_p = subparsers.add_parser("export", help="Export data to backup file")
    export_p.set_defaults(func=cmd_export)

    import_p = subparsers.add_parser("import_legacy", help="Import from old safety system")
    import_p.add_argument("--users_file", help="Path to legacy users JSON")
    import_p.add_argument("--zones_file", help="Path to legacy zones JSON")
    import_p.set_defaults(func=cmd_import_legacy)

    reset_p = subparsers.add_parser("reset", help="Reset all data (requires confirmation)")
    reset_p.add_argument("--token", required=True, help="Confirmation token (CONFIRM_RESET)")
    reset_p.set_defaults(func=cmd_reset)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
