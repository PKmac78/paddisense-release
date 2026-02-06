#!/usr/bin/env python3
"""
STR Sensor - Read-only data output for Home Assistant
PaddiSense Farm Management System

This script reads the stock tracker data and outputs JSON for the HA command_line sensor.
It provides:
  - Mob list with details
  - Mobs by location (paddock)
  - Mobs by age class
  - Mobs by cross/breed
  - Head counts (total, on-farm, off-farm)
  - Config data (age classes, crosses, attributes)
  - Paddocks from registry
  - Recent movements

Output format:
{
  "total_mobs": 5,
  "total_head": 450,
  "on_farm_head": 400,
  "off_farm_head": 50,
  "mobs": { "mob_abc123": { ... } },
  "mob_names": ["Weaners 2025", ...],
  "mobs_by_location": { "sw5": [...], ... },
  "mobs_by_age_class": { "Weaners": [...], ... },
  "mobs_by_cross": { "Angus": [...], ... },
  "age_classes": ["Calves", "Weaners", ...],
  "crosses": ["Angus", "Hereford", ...],
  "attributes": [{"id": "...", "name": "..."}, ...],
  "off_farm_locations": ["Agistment", ...],
  "paddocks": { "sw5": {"name": "SW5", ...}, ... },
  "paddock_names": [{"id": "sw5", "name": "SW5"}, ...],
  "recent_movements": [...],
  "system_status": "ready"
}

Data source: /config/local_data/str/mobs.json
Config source: /config/local_data/str/config.json
Registry source: /config/local_data/registry/config.json
"""

import json
from pathlib import Path

DATA_DIR = Path("/config/local_data/str")
MOBS_FILE = DATA_DIR / "mobs.json"
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"
REGISTRY_FILE = Path("/config/local_data/registry/config.json")

# Version file location (in module directory)
VERSION_FILE = Path("/config/PaddiSense/str/VERSION")

# Current config version
CONFIG_VERSION = "1.0.0"

# Default values
DEFAULT_AGE_CLASSES = [
    "Calves", "Weaners", "Yearlings", "Heifers", "Cows", "Bulls", "Steers",
]

DEFAULT_CROSSES = [
    "Angus", "Hereford", "Angus x Hereford", "Brahman", "Droughtmaster",
    "Murray Grey", "Charolais", "Simmental", "Shorthorn",
]

DEFAULT_ATTRIBUTES = [
    {"id": "lick_active", "name": "Lick Active"},
    {"id": "vaccinated", "name": "Vaccinated"},
    {"id": "pregnant", "name": "Pregnant"},
    {"id": "for_sale", "name": "For Sale"},
    {"id": "weaned", "name": "Weaned"},
    {"id": "drenched", "name": "Drenched"},
]

DEFAULT_OFF_FARM_LOCATIONS = [
    "Agistment", "Feedlot", "Sold", "Deceased", "Saleyards", "Abattoir",
]


def get_version() -> str:
    """Read module version from VERSION file."""
    try:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text(encoding="utf-8").strip()
    except IOError:
        pass
    return "unknown"


def load_config() -> dict:
    """Load config from JSON file."""
    if not CONFIG_FILE.exists():
        return {
            "version": None,
            "age_classes": DEFAULT_AGE_CLASSES,
            "crosses": DEFAULT_CROSSES,
            "attributes": DEFAULT_ATTRIBUTES,
            "off_farm_locations": DEFAULT_OFF_FARM_LOCATIONS,
        }

    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return config
    except (json.JSONDecodeError, IOError):
        return {
            "version": None,
            "age_classes": DEFAULT_AGE_CLASSES,
            "crosses": DEFAULT_CROSSES,
            "attributes": DEFAULT_ATTRIBUTES,
            "off_farm_locations": DEFAULT_OFF_FARM_LOCATIONS,
        }


def load_registry() -> dict:
    """Load registry data for paddocks."""
    if not REGISTRY_FILE.exists():
        return {}
    try:
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {}


def get_backup_info() -> dict:
    """Get information about available backups."""
    backups = []
    last_backup = None
    backup_filenames = []

    if BACKUP_DIR.exists():
        for backup_file in sorted(BACKUP_DIR.glob("*.json"), reverse=True):
            try:
                data = json.loads(backup_file.read_text(encoding="utf-8"))
                mob_count = len(data.get("mobs", {}).get("mobs", {}))
                backup_info = {
                    "filename": backup_file.name,
                    "created": data.get("created", ""),
                    "note": data.get("note", ""),
                    "mob_count": mob_count,
                }
                backups.append(backup_info)
                backup_filenames.append(backup_file.name)

                if last_backup is None:
                    last_backup = backup_info
            except (json.JSONDecodeError, IOError):
                backups.append({
                    "filename": backup_file.name,
                    "created": "",
                    "note": "Unable to read",
                    "mob_count": 0,
                })
                backup_filenames.append(backup_file.name)

    return {
        "backup_count": len(backups),
        "last_backup": last_backup,
        "backups": backups,
        "backup_filenames": backup_filenames,
    }


def main():
    # Load config
    config = load_config()

    # Get values from config
    config_version = config.get("version")
    age_classes = config.get("age_classes", DEFAULT_AGE_CLASSES)
    crosses = config.get("crosses", DEFAULT_CROSSES)
    attributes = config.get("attributes", DEFAULT_ATTRIBUTES)
    off_farm_locations = config.get("off_farm_locations", DEFAULT_OFF_FARM_LOCATIONS)

    # Load registry for paddocks
    registry = load_registry()
    paddocks = registry.get("paddocks", {})

    # Build paddock names list for dropdowns (only current season paddocks)
    paddock_names = []
    for pid, pdata in paddocks.items():
        if pdata.get("current_season", True):
            paddock_names.append({
                "id": pid,
                "name": pdata.get("name", pid),
            })
    paddock_names.sort(key=lambda x: x["name"])

    # Determine system status
    config_exists = CONFIG_FILE.exists()
    mobs_file_exists = MOBS_FILE.exists()
    registry_exists = REGISTRY_FILE.exists()

    if config_exists or mobs_file_exists:
        system_status = "ready"
    else:
        system_status = "not_initialized"

    # Get backup info
    backup_info = get_backup_info()

    # Get version
    version = get_version()

    # Default empty output
    empty_output = {
        "total_mobs": 0,
        "total_head": 0,
        "on_farm_head": 0,
        "off_farm_head": 0,
        "mobs": {},
        "mob_names": [],
        "mob_ids": [],
        "mobs_by_location": {},
        "mobs_by_age_class": {},
        "mobs_by_cross": {},
        "on_farm_mobs": [],
        "off_farm_mobs": [],
        "age_classes": age_classes,
        "crosses": crosses,
        "attributes": attributes,
        "attribute_ids": [a["id"] for a in attributes],
        "off_farm_locations": off_farm_locations,
        "paddocks": paddocks,
        "paddock_names": paddock_names,
        "recent_movements": [],
        "system_status": system_status,
        "config_exists": config_exists,
        "mobs_file_exists": mobs_file_exists,
        "registry_exists": registry_exists,
        "config_version": config_version or "1.0.0",
        "backup_count": backup_info["backup_count"],
        "last_backup": backup_info["last_backup"],
        "backup_filenames": backup_info["backup_filenames"],
        "version": version,
    }

    if not MOBS_FILE.exists():
        print(json.dumps(empty_output))
        return

    try:
        data = json.loads(MOBS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        empty_output["system_status"] = "error"
        print(json.dumps(empty_output))
        return

    mobs = data.get("mobs", {})
    movements = data.get("movements", [])

    # Build output structures
    mob_names = []
    mob_ids = []
    mobs_by_location = {}
    mobs_by_age_class = {}
    mobs_by_cross = {}
    on_farm_mobs = []
    off_farm_mobs = []

    total_head = 0
    on_farm_head = 0
    off_farm_head = 0

    for mob_id, mob in mobs.items():
        name = mob.get("name", mob_id)
        mob_names.append(name)
        mob_ids.append(mob_id)

        head_count = int(mob.get("head_count", 0))
        total_head += head_count

        # Add display fields to mob
        mob["display_name"] = name
        mob["display_location"] = mob.get("location_name", mob.get("location", ""))

        # Build attribute display names
        mob_attrs = mob.get("attributes", [])
        attr_names = []
        for attr in attributes:
            if attr["id"] in mob_attrs:
                attr_names.append(attr["name"])
        mob["attribute_names"] = attr_names

        # Group by on-farm/off-farm
        if mob.get("off_farm", False):
            off_farm_head += head_count
            off_farm_mobs.append({
                "id": mob_id,
                "name": name,
                "head_count": head_count,
                "reason": mob.get("off_farm_details", {}).get("reason", ""),
            })
        else:
            on_farm_head += head_count
            on_farm_mobs.append({
                "id": mob_id,
                "name": name,
                "head_count": head_count,
                "location": mob.get("location", ""),
                "location_name": mob.get("location_name", ""),
            })

            # Group by location
            location = mob.get("location", "")
            if location:
                if location not in mobs_by_location:
                    mobs_by_location[location] = {
                        "location_id": location,
                        "location_name": mob.get("location_name", location),
                        "mobs": [],
                        "total_head": 0,
                    }
                mobs_by_location[location]["mobs"].append({
                    "id": mob_id,
                    "name": name,
                    "head_count": head_count,
                })
                mobs_by_location[location]["total_head"] += head_count

        # Group by age class
        age_class = mob.get("age_class", "")
        if age_class:
            if age_class not in mobs_by_age_class:
                mobs_by_age_class[age_class] = {
                    "age_class": age_class,
                    "mobs": [],
                    "total_head": 0,
                }
            mobs_by_age_class[age_class]["mobs"].append({
                "id": mob_id,
                "name": name,
                "head_count": head_count,
            })
            mobs_by_age_class[age_class]["total_head"] += head_count

        # Group by cross
        cross = mob.get("cross", "")
        if cross:
            if cross not in mobs_by_cross:
                mobs_by_cross[cross] = {
                    "cross": cross,
                    "mobs": [],
                    "total_head": 0,
                }
            mobs_by_cross[cross]["mobs"].append({
                "id": mob_id,
                "name": name,
                "head_count": head_count,
            })
            mobs_by_cross[cross]["total_head"] += head_count

    # Get recent movements (last 20)
    recent_movements = sorted(
        movements,
        key=lambda x: x.get("timestamp", ""),
        reverse=True
    )[:20]

    # Build location summaries list (for dashboard display)
    location_summaries = []
    for loc_id, loc_data in mobs_by_location.items():
        location_summaries.append({
            "id": loc_id,
            "name": loc_data["location_name"],
            "mob_count": len(loc_data["mobs"]),
            "total_head": loc_data["total_head"],
        })
    location_summaries.sort(key=lambda x: x["name"])

    # Build age class summaries
    age_class_summaries = []
    for ac_name, ac_data in mobs_by_age_class.items():
        age_class_summaries.append({
            "age_class": ac_name,
            "mob_count": len(ac_data["mobs"]),
            "total_head": ac_data["total_head"],
        })
    age_class_summaries.sort(key=lambda x: x["total_head"], reverse=True)

    output = {
        "total_mobs": len(mobs),
        "total_head": total_head,
        "on_farm_head": on_farm_head,
        "off_farm_head": off_farm_head,
        "mobs": mobs,
        "mob_names": sorted(mob_names),
        "mob_ids": mob_ids,
        "mobs_by_location": mobs_by_location,
        "mobs_by_age_class": mobs_by_age_class,
        "mobs_by_cross": mobs_by_cross,
        "on_farm_mobs": on_farm_mobs,
        "off_farm_mobs": off_farm_mobs,
        "location_summaries": location_summaries,
        "age_class_summaries": age_class_summaries,
        "age_classes": age_classes,
        "crosses": crosses,
        "attributes": attributes,
        "attribute_ids": [a["id"] for a in attributes],
        "off_farm_locations": off_farm_locations,
        "paddocks": paddocks,
        "paddock_names": paddock_names,
        "recent_movements": recent_movements,
        "system_status": "ready",
        "config_exists": config_exists,
        "mobs_file_exists": mobs_file_exists,
        "registry_exists": registry_exists,
        "config_version": config_version or "1.0.0",
        "backup_count": backup_info["backup_count"],
        "last_backup": backup_info["last_backup"],
        "backup_filenames": backup_info["backup_filenames"],
        "version": version,
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
