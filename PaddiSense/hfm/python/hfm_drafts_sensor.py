#!/usr/bin/env python3
"""
HFM Drafts Sensor - Hey Farmer Module
Read-only sensor providing active draft data for multi-user support.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Paths
DATA_DIR = Path("/config/local_data/hfm")
DRAFTS_DIR = DATA_DIR / "drafts"
CONFIG_FILE = DATA_DIR / "config.json"
APPLICATORS_FILE = DATA_DIR / "applicators.json"
VERSION_FILE = Path("/config/PaddiSense/hfm/VERSION")
REGISTRY_FILE = Path("/config/local_data/registry/config.json")


def get_version() -> str:
    """Get module version."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except (IOError, FileNotFoundError):
        return "unknown"


def load_json(path: Path, default: Any = None) -> Any:
    """Load JSON file, returning default if not found or invalid."""
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return default


def get_paddock_map() -> dict:
    """Get paddock ID to name mapping from Registry."""
    registry = load_json(REGISTRY_FILE, {})
    paddocks = registry.get("paddocks", {})
    return {pid: p.get("name", pid) for pid, p in paddocks.items()}


def get_farm_map() -> dict:
    """Get farm ID to name mapping from Registry."""
    registry = load_json(REGISTRY_FILE, {})
    farms = registry.get("farms", {})
    return {fid: f.get("name", fid) for fid, f in farms.items()}


def get_paddocks_by_farm() -> dict:
    """Get paddocks grouped by farm_id."""
    registry = load_json(REGISTRY_FILE, {})
    paddocks = registry.get("paddocks", {})

    by_farm = {}
    for pid, pdata in paddocks.items():
        farm_id = pdata.get("farm_id", "unknown")
        if farm_id not in by_farm:
            by_farm[farm_id] = []
        by_farm[farm_id].append({
            "id": pid,
            "name": pdata.get("name", pid),
            "area_ha": pdata.get("area_ha"),
            "current_season": pdata.get("current_season", False)
        })

    return by_farm


def get_applicators() -> dict:
    """Get active applicators for dropdown selection."""
    data = load_json(APPLICATORS_FILE, {"applicators": []})
    applicators = data.get("applicators", [])

    # Active applicators only
    active = [a for a in applicators if a.get("active", True)]

    # Group by type
    by_type = {}
    for app in active:
        app_type = app.get("type", "unknown")
        if app_type not in by_type:
            by_type[app_type] = []
        by_type[app_type].append({
            "id": app["id"],
            "name": app["name"],
            "type": app_type
        })

    return {
        "list": active,
        "by_type": by_type,
        "names": [a["name"] for a in active],
        "ids": [a["id"] for a in active]
    }


def calculate_draft_age_hours(draft: dict) -> float:
    """Calculate age of draft in hours."""
    updated_at = draft.get("updated_at") or draft.get("started_at")
    if not updated_at:
        return 0
    try:
        draft_time = datetime.fromisoformat(updated_at)
        age_seconds = (datetime.now() - draft_time).total_seconds()
        return age_seconds / 3600
    except (ValueError, TypeError):
        return 0


def main():
    """Generate drafts sensor output."""

    # Load config for device mappings
    config = load_json(CONFIG_FILE, {})
    devices_config = config.get("devices", {})

    # Load all drafts
    drafts = {}
    draft_count = 0
    active_devices = []

    if DRAFTS_DIR.exists():
        for draft_file in DRAFTS_DIR.glob("*.json"):
            draft_data = load_json(draft_file, None)
            if draft_data:
                device_id = draft_data.get("device_id", draft_file.stem)

                # Enrich with user name from config if not set
                if not draft_data.get("user_name") and device_id in devices_config:
                    draft_data["user_name"] = devices_config[device_id].get("user_name", "")

                # Add computed fields
                draft_data["age_hours"] = round(calculate_draft_age_hours(draft_data), 2)

                drafts[device_id] = draft_data
                draft_count += 1
                active_devices.append({
                    "device_id": device_id,
                    "user_name": draft_data.get("user_name", ""),
                    "wizard_step": draft_data.get("wizard_step", 1),
                    "event_type": draft_data.get("data", {}).get("event_type"),
                    "started_at": draft_data.get("started_at"),
                    "updated_at": draft_data.get("updated_at"),
                    "age_hours": draft_data["age_hours"]
                })

    # Get registry data for dropdown population
    paddock_map = get_paddock_map()
    farm_map = get_farm_map()
    paddocks_by_farm = get_paddocks_by_farm()

    # Get applicator data
    applicator_data = get_applicators()

    # Build output
    output = {
        # Main state value
        "draft_count": draft_count,

        # All drafts keyed by device_id
        "drafts": drafts,

        # Summary of active devices
        "active_devices": active_devices,

        # Registry data for UI
        "farms": farm_map,
        "paddock_map": paddock_map,
        "paddocks_by_farm": paddocks_by_farm,

        # Applicator data for UI
        "applicators": applicator_data["list"],
        "applicators_by_type": applicator_data["by_type"],
        "applicator_names": applicator_data["names"],
        "applicator_ids": applicator_data["ids"],

        # Device config
        "registered_devices": devices_config,

        # System info
        "version": get_version(),
        "last_updated": datetime.now().isoformat()
    }

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
