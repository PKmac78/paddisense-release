#!/usr/bin/env python3
"""
PWM Sensor - Precision Water Management
PaddiSense Farm Management System

This script provides read-only JSON output for the Home Assistant sensor.
It reads the config file and server.yaml, outputting data for template sensors.

Output includes:
  - paddocks: All paddock configurations
  - bays: All bay configurations with device assignments
  - farms: Farm definitions from server.yaml
  - paddock_names: List of paddock names for dropdowns
  - enabled_paddocks: List of enabled paddock IDs
  - device_list: All unique devices in use
  - status: System status information
"""

import json
import sys
from pathlib import Path
from typing import Any

import yaml

# Paths
DATA_DIR = Path("/config/local_data/pwm")
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"
SERVER_YAML = Path("/config/server.yaml")
VERSION_FILE = Path("/config/PaddiSense/pwm/VERSION")


def get_version() -> str:
    """Read module version from VERSION file."""
    try:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text(encoding="utf-8").strip()
    except IOError:
        pass
    return "unknown"


def load_config() -> dict[str, Any]:
    """Load PWM config from JSON file."""
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


def load_server_yaml() -> dict[str, Any]:
    """Load server.yaml for farm definitions."""
    if not SERVER_YAML.exists():
        return {}
    try:
        content = SERVER_YAML.read_text(encoding="utf-8")
        return yaml.safe_load(content) or {}
    except (yaml.YAMLError, IOError):
        return {}


def extract_farms(server_config: dict[str, Any]) -> dict[str, Any]:
    """Extract farm definitions from server.yaml."""
    pwm_config = server_config.get("pwm", {})
    farms = pwm_config.get("farms", {})
    return farms


def collect_devices(bays: dict[str, Any]) -> list[str]:
    """Collect all unique device names from bay configurations."""
    devices = set()
    for bay_id, bay in bays.items():
        # Check all device slots
        for slot in ["supply_1", "supply_2", "drain_1", "drain_2"]:
            slot_data = bay.get(slot, {})
            if isinstance(slot_data, dict):
                device = slot_data.get("device")
                if device and device not in (None, "null", "unset", ""):
                    devices.add(device)
        # Level sensor
        level_sensor = bay.get("level_sensor")
        if level_sensor and level_sensor not in (None, "null", "unset", ""):
            devices.add(level_sensor)
    return sorted(devices)


def build_paddock_summary(
    paddocks: dict[str, Any], bays: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build summary list of paddocks with bay counts and status."""
    summary = []
    for pid, paddock in paddocks.items():
        # Count bays for this paddock
        bay_count = sum(1 for b in bays.values() if b.get("paddock_id") == pid)
        # Count enabled bays (bays with at least one device assigned)
        configured_bays = sum(
            1
            for b in bays.values()
            if b.get("paddock_id") == pid
            and (
                b.get("level_sensor")
                or (b.get("supply_1", {}) or {}).get("device")
            )
        )
        summary.append(
            {
                "id": pid,
                "name": paddock.get("name", pid),
                "farm_id": paddock.get("farm_id", ""),
                "enabled": paddock.get("enabled", False),
                "individual_mode": paddock.get("automation_state_individual", False),
                "bay_count": bay_count,
                "configured_bays": configured_bays,
            }
        )
    return sorted(summary, key=lambda x: x["name"])


def build_bay_summary(bays: dict[str, Any], paddocks: dict[str, Any]) -> list[dict[str, Any]]:
    """Build summary list of bays with device info."""
    summary = []
    for bid, bay in bays.items():
        paddock_id = bay.get("paddock_id", "")
        paddock = paddocks.get(paddock_id, {})

        # Get device names
        supply_1 = (bay.get("supply_1", {}) or {}).get("device")
        supply_2 = (bay.get("supply_2", {}) or {}).get("device")
        drain_1 = (bay.get("drain_1", {}) or {}).get("device")
        drain_2 = (bay.get("drain_2", {}) or {}).get("device")
        level = bay.get("level_sensor")

        summary.append(
            {
                "id": bid,
                "name": bay.get("name", bid),
                "paddock_id": paddock_id,
                "paddock_name": paddock.get("name", paddock_id),
                "order": bay.get("order", 0),
                "is_last_bay": bay.get("is_last_bay", False),
                "supply_1": supply_1,
                "supply_2": supply_2,
                "drain_1": drain_1,
                "drain_2": drain_2,
                "level_sensor": level,
                "has_device": bool(level or supply_1),
                "settings": bay.get("settings", {}),
            }
        )
    return sorted(summary, key=lambda x: (x["paddock_name"], x["order"]))


def main() -> int:
    config = load_config()
    server = load_server_yaml()

    # Check if PWM is enabled in server.yaml
    modules = server.get("modules", {})
    pwm_enabled = modules.get("pwm", False)

    # Extract data
    paddocks = config.get("paddocks", {})
    bays = config.get("bays", {})
    farms = extract_farms(server)

    # System status
    initialized = config.get("initialized", False)
    config_ok = CONFIG_FILE.exists()

    # Build lists for dropdowns
    paddock_names = sorted([p.get("name", pid) for pid, p in paddocks.items()])
    enabled_paddock_ids = [pid for pid, p in paddocks.items() if p.get("enabled", False)]
    farm_names = sorted([f.get("name", fid) for fid, f in farms.items()])

    # Collect devices in use
    device_list = collect_devices(bays)

    # Build summaries
    paddock_summary = build_paddock_summary(paddocks, bays)
    bay_summary = build_bay_summary(bays, paddocks)

    # Count backups
    backup_count = 0
    if BACKUP_DIR.exists():
        backup_count = len(list(BACKUP_DIR.glob("*.json")))

    # Get version
    version = get_version()

    output = {
        # System status
        "status": "ready" if initialized else "not_initialized",
        "initialized": initialized,
        "config_ok": config_ok,
        "pwm_enabled": pwm_enabled,
        "version": version,
        # Counts
        "total_paddocks": len(paddocks),
        "total_bays": len(bays),
        "total_farms": len(farms),
        "enabled_paddock_count": len(enabled_paddock_ids),
        "device_count": len(device_list),
        "backup_count": backup_count,
        # Raw data
        "paddocks": paddocks,
        "bays": bays,
        "farms": farms,
        # Summaries for UI
        "paddock_summary": paddock_summary,
        "bay_summary": bay_summary,
        # Lists for dropdowns
        "paddock_names": paddock_names,
        "enabled_paddock_ids": enabled_paddock_ids,
        "farm_names": farm_names,
        "device_list": device_list,
    }

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
