#!/usr/bin/env python3
"""
WSS Sensor - Worker Safety System
PaddiSense Farm Management System

Read-only sensor script that outputs JSON data for Home Assistant.
This script reads config.json and users.json and outputs a combined
JSON structure for the wss_data sensor.

Usage:
  python3 wss_sensor.py

Output JSON structure:
{
  "system_status": "ready|not_initialized|error",
  "version": "1.0.0",
  "enabled_count": 3,
  "alert_count": 0,
  "users": {...},
  "user_list": [...],
  "zones": {...},
  "zone_list": [...],
  "monitored_zones": [...],
  "away_zones": [...],
  "roles": {...},
  "timing": {...},
  "working_hours": {...}
}
"""

import json
import sys
from pathlib import Path
from typing import Any

# Data file locations
DATA_DIR = Path("/config/local_data/wss")
CONFIG_FILE = DATA_DIR / "config.json"
USERS_FILE = DATA_DIR / "users.json"
VERSION_FILE = Path("/config/PaddiSense/wss/VERSION")


def load_config() -> dict[str, Any]:
    """Load config from JSON file."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {}


def load_users() -> dict[str, Any]:
    """Load users from JSON file."""
    if not USERS_FILE.exists():
        return {"users": {}}
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"users": {}}


def get_version() -> str:
    """Read version from VERSION file."""
    if not VERSION_FILE.exists():
        return "unknown"
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except IOError:
        return "unknown"


def main() -> int:
    """Generate sensor output JSON."""
    output = {
        "system_status": "not_initialized",
        "version": get_version(),
        "enabled_count": 0,
        "alert_count": 0,
        "users": {},
        "user_list": [],
        "user_names": [],
        "enabled_users": [],
        "zones": {},
        "zone_list": [],
        "monitored_zones": [],
        "away_zones": [],
        "roles": {
            "primary": "",
            "secondary": "",
            "admins": [],
        },
        "primary_username": "",
        "secondary_username": "",
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
        "config_exists": CONFIG_FILE.exists(),
        "users_file_exists": USERS_FILE.exists(),
    }

    # Load config
    config = load_config()
    if config:
        output["system_status"] = "ready"
        output["timing"] = config.get("timing", output["timing"])
        output["working_hours"] = config.get("working_hours", output["working_hours"])
        output["roles"] = config.get("roles", output["roles"])

        # Process zones
        zones = config.get("zones", {})
        output["zones"] = zones

        zone_list = []
        monitored_zones = []
        away_zones = []

        for zone_id, zone_data in zones.items():
            zone_entry = {
                "id": zone_id,
                "name": zone_data.get("name", zone_id),
                "monitored": zone_data.get("monitored", False),
                "away": zone_data.get("away", False),
            }
            zone_list.append(zone_entry)

            if zone_data.get("monitored", False):
                monitored_zones.append(zone_data.get("name", zone_id))

            if zone_data.get("away", False):
                away_zones.append(zone_data.get("name", zone_id))

        output["zone_list"] = zone_list
        output["monitored_zones"] = monitored_zones
        output["away_zones"] = away_zones

    # Load users
    users_data = load_users()
    users = users_data.get("users", {})
    output["users"] = users

    user_list = []
    user_names = []
    enabled_users = []

    for user_id, user_data in users.items():
        user_entry = {
            "id": user_id,
            "username": user_data.get("username", ""),
            "person_id": user_data.get("person_id", ""),
            "tracker_id": user_data.get("tracker_id", ""),
            "activity_id": user_data.get("activity_id", ""),
            "notify_id": user_data.get("notify_id", ""),
            "enabled": user_data.get("enabled", False),
            "track_external": user_data.get("track_external", False),
        }
        user_list.append(user_entry)
        user_names.append(user_data.get("username", user_id))

        if user_data.get("enabled", False):
            enabled_users.append({
                "id": user_id,
                "username": user_data.get("username", ""),
                "person_id": user_data.get("person_id", ""),
                "tracker_id": user_data.get("tracker_id", ""),
                "activity_id": user_data.get("activity_id", ""),
                "notify_id": user_data.get("notify_id", ""),
                "track_external": user_data.get("track_external", False),
            })

    output["user_list"] = user_list
    output["user_names"] = user_names
    output["enabled_users"] = enabled_users
    output["enabled_count"] = len(enabled_users)

    # Resolve role usernames for display
    roles = output["roles"]
    primary_id = roles.get("primary", "")
    secondary_id = roles.get("secondary", "")

    if primary_id and primary_id in users:
        output["primary_username"] = users[primary_id].get("username", primary_id)

    if secondary_id and secondary_id in users:
        output["secondary_username"] = users[secondary_id].get("username", secondary_id)

    # Output JSON
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
