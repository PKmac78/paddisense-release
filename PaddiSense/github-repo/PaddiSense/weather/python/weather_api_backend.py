#!/usr/bin/env python3
"""
Weather API Backend - Station Management (v1.1.0)
PaddiSense Farm Management System

Manages external Ecowitt API weather station configurations.
Data stored in /config/local_data/weather_api/config.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CONFIG_DIR = Path("/config/local_data/weather_api")
CONFIG_FILE = CONFIG_DIR / "config.json"
VALID_SLOTS = ["1", "2", "3", "4"]
VERSION = "1.1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_config() -> dict:
    return {"stations": {}, "created": None, "modified": None, "version": VERSION}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return default_config()
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default_config()


def save_config(config: dict) -> None:
    config["modified"] = now_iso()
    config.setdefault("created", now_iso())
    config["version"] = VERSION
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def normalise_station(args) -> dict:
    return {
        "enabled": True,
        "name": (args.name or "").strip(),
        "imei": str((args.imei or "").strip()),
        "latitude": float(args.latitude) if args.latitude is not None else -35.0,
        "elevation": int(args.elevation) if args.elevation is not None else 100,
        "created": now_iso(),
        "modified": now_iso(),
    }


def cmd_init(args) -> int:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        cfg = default_config()
        cfg["created"] = now_iso()
        cfg["modified"] = now_iso()
        save_config(cfg)
        print("OK:created:config")
        return 0

    # Ensure version key exists even if old config
    cfg = load_config()
    save_config(cfg)
    print("OK:already_initialized")
    return 0


def cmd_status(args) -> int:
    cfg = load_config()
    initialized = CONFIG_FILE.exists()
    stations = cfg.get("stations", {}) if isinstance(cfg, dict) else {}
    if not isinstance(stations, dict):
        stations = {}

    station_count = len([s for s in stations.values() if isinstance(s, dict) and s.get("enabled")])
    total_configured = len([s for s in stations.values() if isinstance(s, dict) and s.get("name")])

    status = {
        "version": VERSION,
        "initialized": initialized,
        "config_exists": CONFIG_FILE.exists(),
        "station_count": station_count,
        "total_configured": total_configured,
        "status": "ready" if initialized else "not_initialized",
    }
    print(json.dumps(status))
    return 0


def cmd_add_station(args) -> int:
    slot = str(args.slot)

    if slot not in VALID_SLOTS:
        print(f"ERROR: Invalid slot '{slot}'. Must be 1-4.", file=sys.stderr)
        return 1

    name = (args.name or "").strip()
    imei = (args.imei or "").strip()

    if not name:
        print("ERROR: Station name is required.", file=sys.stderr)
        return 1
    if not imei:
        print("ERROR: Station IMEI is required.", file=sys.stderr)
        return 1

    cfg = load_config()
    cfg.setdefault("stations", {})

    if slot in cfg["stations"]:
        print(f"ERROR: Slot {slot} already configured. Use edit_station to modify.", file=sys.stderr)
        return 1

    st = normalise_station(args)
    cfg["stations"][slot] = st
    save_config(cfg)

    print(f"OK:{slot}:{name}")
    return 0


def cmd_edit_station(args) -> int:
    slot = str(args.slot)

    if slot not in VALID_SLOTS:
        print(f"ERROR: Invalid slot '{slot}'. Must be 1-4.", file=sys.stderr)
        return 1

    cfg = load_config()
    cfg.setdefault("stations", {})

    if slot not in cfg["stations"]:
        print(f"ERROR: Slot {slot} not configured. Use add_station first.", file=sys.stderr)
        return 1

    st = cfg["stations"][slot]
    if not isinstance(st, dict):
        st = {}

    if args.name and args.name.strip():
        st["name"] = args.name.strip()
    if args.imei and args.imei.strip():
        st["imei"] = str(args.imei.strip())
    if args.latitude is not None:
        st["latitude"] = float(args.latitude)
    if args.elevation is not None:
        st["elevation"] = int(args.elevation)

    st.setdefault("enabled", True)
    st["modified"] = now_iso()
    cfg["stations"][slot] = st
    save_config(cfg)

    print(f"OK:{slot}:{st.get('name','')}")
    return 0


def cmd_remove_station(args) -> int:
    slot = str(args.slot)

    if slot not in VALID_SLOTS:
        print(f"ERROR: Invalid slot '{slot}'. Must be 1-4.", file=sys.stderr)
        return 1

    cfg = load_config()
    cfg.setdefault("stations", {})

    if slot not in cfg["stations"]:
        print(f"ERROR: Slot {slot} not configured.", file=sys.stderr)
        return 1

    name = (cfg["stations"][slot] or {}).get("name", f"Station {slot}")
    del cfg["stations"][slot]
    save_config(cfg)

    print(f"OK:{slot}:{name}")
    return 0


def cmd_enable_station(args) -> int:
    slot = str(args.slot)
    if slot not in VALID_SLOTS:
        print(f"ERROR: Invalid slot '{slot}'. Must be 1-4.", file=sys.stderr)
        return 1

    cfg = load_config()
    cfg.setdefault("stations", {})
    if slot not in cfg["stations"]:
        print(f"ERROR: Slot {slot} not configured.", file=sys.stderr)
        return 1

    cfg["stations"][slot]["enabled"] = True
    cfg["stations"][slot]["modified"] = now_iso()
    save_config(cfg)
    print(f"OK:{slot}:enabled")
    return 0


def cmd_disable_station(args) -> int:
    slot = str(args.slot)
    if slot not in VALID_SLOTS:
        print(f"ERROR: Invalid slot '{slot}'. Must be 1-4.", file=sys.stderr)
        return 1

    cfg = load_config()
    cfg.setdefault("stations", {})
    if slot not in cfg["stations"]:
        print(f"ERROR: Slot {slot} not configured.", file=sys.stderr)
        return 1

    cfg["stations"][slot]["enabled"] = False
    cfg["stations"][slot]["modified"] = now_iso()
    save_config(cfg)
    print(f"OK:{slot}:disabled")
    return 0


def cmd_list_stations(args) -> int:
    cfg = load_config()
    stations = cfg.get("stations", {}) if isinstance(cfg, dict) else {}
    if not isinstance(stations, dict):
        stations = {}

    result = []
    for slot in VALID_SLOTS:
        if slot in stations and isinstance(stations[slot], dict):
            s = stations[slot]
            imei = str(s.get("imei") or "")
            result.append(
                {
                    "slot": slot,
                    "name": s.get("name", ""),
                    "imei": imei[-4:] if imei else "",
                    "enabled": bool(s.get("enabled", False)),
                    "latitude": s.get("latitude"),
                    "elevation": s.get("elevation"),
                }
            )

    print(json.dumps(result))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Weather API Backend")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("init", help="Initialize the system")
    subparsers.add_parser("status", help="Get system status")

    p_add = subparsers.add_parser("add_station", help="Add a weather station")
    p_add.add_argument("--slot", type=int, required=True, help="Station slot (1-4)")
    p_add.add_argument("--name", required=True, help="Station name")
    p_add.add_argument("--imei", required=True, help="Station IMEI/MAC")
    p_add.add_argument("--latitude", type=float, help="Station latitude")
    p_add.add_argument("--elevation", type=int, help="Station elevation (m)")

    p_edit = subparsers.add_parser("edit_station", help="Edit a weather station")
    p_edit.add_argument("--slot", type=int, required=True, help="Station slot (1-4)")
    p_edit.add_argument("--name", help="Station name")
    p_edit.add_argument("--imei", help="Station IMEI/MAC")
    p_edit.add_argument("--latitude", type=float, help="Station latitude")
    p_edit.add_argument("--elevation", type=int, help="Station elevation (m)")

    p_remove = subparsers.add_parser("remove_station", help="Remove a weather station")
    p_remove.add_argument("--slot", type=int, required=True, help="Station slot (1-4)")

    p_enable = subparsers.add_parser("enable_station", help="Enable a weather station")
    p_enable.add_argument("--slot", type=int, required=True, help="Station slot (1-4)")

    p_disable = subparsers.add_parser("disable_station", help="Disable a weather station")
    p_disable.add_argument("--slot", type=int, required=True, help="Station slot (1-4)")

    subparsers.add_parser("list_stations", help="List all stations")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "add_station": cmd_add_station,
        "edit_station": cmd_edit_station,
        "remove_station": cmd_remove_station,
        "enable_station": cmd_enable_station,
        "disable_station": cmd_disable_station,
        "list_stations": cmd_list_stations,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
