#!/usr/bin/env python3
"""
Farm Registry Sensor - PaddiSense Shared Core
PaddiSense Farm Management System

This script provides read-only JSON output for the Home Assistant sensor.
It reads the registry config and server.yaml, outputting the farm hierarchy
for consumption by all PaddiSense modules (PWM, HFM, IPM, ASM, etc.).

Output includes:
  - grower: Grower/server info from server.yaml
  - farms: Farm definitions from server.yaml
  - paddocks: Paddock configurations from registry
  - bays: Bay configurations from registry
  - seasons: Season definitions with active season
  - status: System status information
"""

import json
import sys
from pathlib import Path
from typing import Any

import yaml

# Paths
DATA_DIR = Path("/config/local_data/registry")
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"
SERVER_YAML = Path("/config/server.yaml")
VERSION_FILE = Path("/config/PaddiSense/registry/VERSION")


def get_version() -> str:
    """Read module version from VERSION file."""
    try:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text(encoding="utf-8").strip()
    except IOError:
        pass
    return "unknown"


def load_config() -> dict[str, Any]:
    """Load registry config from JSON file."""
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


def load_server_yaml() -> dict[str, Any]:
    """Load server.yaml for grower and farm definitions."""
    if not SERVER_YAML.exists():
        return {}
    try:
        content = SERVER_YAML.read_text(encoding="utf-8")
        return yaml.safe_load(content) or {}
    except (yaml.YAMLError, IOError):
        return {}


def extract_grower(server_config: dict[str, Any]) -> dict[str, Any]:
    """Extract grower/server info from server.yaml."""
    server = server_config.get("server", {})
    return {
        "name": server.get("name", "PaddiSense Farm"),
        "location": server.get("location", ""),
    }


def extract_farms(server_config: dict[str, Any], registry_farms: dict[str, Any]) -> dict[str, Any]:
    """
    Merge farm definitions from server.yaml (read-only legacy) and config.json (editable).

    Priority: config.json farms override server.yaml farms if same ID.
    This allows editing farms via UI while preserving backward compatibility.
    """
    # Start with farms from server.yaml (pwm.farms or registry.farms)
    pwm_config = server_config.get("pwm", {})
    server_farms = dict(pwm_config.get("farms", {}))

    # Check for dedicated registry.farms section in server.yaml
    registry_config = server_config.get("registry", {})
    if "farms" in registry_config:
        server_farms.update(registry_config.get("farms", {}))

    # Merge in farms from config.json (these take precedence)
    # This allows farms to be edited via the UI
    merged = dict(server_farms)
    for farm_id, farm_data in registry_farms.items():
        merged[farm_id] = farm_data

    return merged


def get_active_season(seasons: dict[str, Any]) -> str | None:
    """Get the ID of the active season, if any."""
    for season_id, season in seasons.items():
        if season.get("active", False):
            return season_id
    return None


def build_hierarchy_summary(
    farms: dict[str, Any],
    paddocks: dict[str, Any],
    bays: dict[str, Any]
) -> dict[str, Any]:
    """Build a hierarchical summary for the UI."""
    hierarchy = {}

    for farm_id, farm in farms.items():
        farm_paddocks = {
            pid: p for pid, p in paddocks.items()
            if p.get("farm_id") == farm_id
        }

        paddock_data = {}
        for pid, paddock in farm_paddocks.items():
            paddock_bays = [
                {"id": bid, "name": b.get("name"), "order": b.get("order", 0)}
                for bid, b in bays.items()
                if b.get("paddock_id") == pid
            ]
            paddock_bays.sort(key=lambda x: x["order"])

            paddock_data[pid] = {
                "name": paddock.get("name", pid),
                "bay_count": len(paddock_bays),
                "bays": paddock_bays,
            }

        hierarchy[farm_id] = {
            "name": farm.get("name", farm_id),
            "paddock_count": len(farm_paddocks),
            "paddocks": paddock_data,
        }

    return hierarchy


def main() -> int:
    config = load_config()
    server = load_server_yaml()

    # Extract data
    grower = extract_grower(server)
    registry_farms = config.get("farms", {})  # Farms stored in config.json (editable)
    farms = extract_farms(server, registry_farms)  # Merge with server.yaml farms
    paddocks = config.get("paddocks", {})
    bays = config.get("bays", {})
    seasons = config.get("seasons", {})

    # System status
    initialized = config.get("initialized", False)
    config_ok = CONFIG_FILE.exists()

    # Active season
    active_season = get_active_season(seasons)

    # Build lists for dropdowns
    farm_names = sorted([f.get("name", fid) for fid, f in farms.items()])
    paddock_names = sorted([p.get("name", pid) for pid, p in paddocks.items()])
    season_names = sorted([s.get("name", sid) for sid, s in seasons.items()])

    # Build hierarchy
    hierarchy = build_hierarchy_summary(farms, paddocks, bays)

    # Count backups
    backup_count = 0
    if BACKUP_DIR.exists():
        backup_count = len(list(BACKUP_DIR.glob("*.json")))

    # Get version
    version = get_version()

    # Check which modules are enabled
    modules = server.get("modules", {})

    output = {
        # System status
        "status": "ready" if initialized else "not_initialized",
        "initialized": initialized,
        "config_ok": config_ok,
        "version": version,

        # Grower info
        "grower": grower,

        # Counts
        "total_farms": len(farms),
        "total_paddocks": len(paddocks),
        "total_bays": len(bays),
        "total_seasons": len(seasons),
        "backup_count": backup_count,

        # Active season
        "active_season": active_season,
        "active_season_name": seasons.get(active_season, {}).get("name") if active_season else None,

        # Raw data for other modules to consume
        "farms": farms,
        "paddocks": paddocks,
        "bays": bays,
        "seasons": seasons,

        # Hierarchy summary for UI
        "hierarchy": hierarchy,

        # Lists for dropdowns
        "farm_names": farm_names,
        "paddock_names": paddock_names,
        "season_names": season_names,

        # Enabled modules (for conditional UI)
        "modules": modules,
    }

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
