#!/usr/bin/env python3
"""
HFM Backend - Hey Farmer Module
Voice-assisted farm event recording module.

Commands:
  init              Initialize HFM with default config
  add_event         Add a new farm event
  edit_event        Edit an existing event
  delete_event      Delete an event
  confirm_event     Confirm a pending event
  add_crop_stage    Add a custom crop stage
  delete_crop_stage Delete a crop stage
  add_device        Add/update a device-to-user mapping
  delete_device     Remove a device mapping
  export            Export events to backup file

Draft Commands (Multi-user support):
  load_draft        Load or create a draft for a device
  update_draft      Update draft fields for a device
  clear_draft       Clear/delete a draft for a device
  submit_draft      Submit draft as event(s)
  cleanup_drafts    Remove drafts older than specified hours
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import secrets
import string

# Paths
DATA_DIR = Path("/config/local_data/hfm")
CONFIG_FILE = DATA_DIR / "config.json"
EVENTS_FILE = DATA_DIR / "events.json"
APPLICATORS_FILE = DATA_DIR / "applicators.json"
BACKUPS_DIR = DATA_DIR / "backups"
DRAFTS_DIR = DATA_DIR / "drafts"
VERSION_FILE = Path("/config/PaddiSense/hfm/VERSION")
REGISTRY_FILE = Path("/config/local_data/registry/config.json")
IPM_CONFIG_FILE = Path("/config/local_data/ipm/config.json")

# Draft schema version
DRAFT_SCHEMA_VERSION = "2.0.0"

# Valid applicator types (must match application_methods in config)
VALID_APPLICATOR_TYPES = ["boom_spray", "broadcast", "aerial", "fertigation", "seed_treatment", "foliar"]


def get_version() -> str:
    """Get module version."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except (IOError, FileNotFoundError):
        return "unknown"


def generate_event_id() -> str:
    """Generate a unique event ID."""
    chars = string.ascii_lowercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(8))
    return f"evt_{suffix}"


def now_iso() -> str:
    """Return current timestamp in ISO format."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def today_date() -> str:
    """Return today's date."""
    return datetime.now().strftime("%Y-%m-%d")


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


def save_json(path: Path, data: Any) -> bool:
    """Save data to JSON file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except IOError as e:
        print(f"ERROR: Failed to save {path}: {e}", file=sys.stderr)
        return False


def load_config() -> dict:
    """Load HFM config."""
    return load_json(CONFIG_FILE, {})


def save_config(config: dict) -> bool:
    """Save HFM config."""
    config["modified"] = now_iso()
    return save_json(CONFIG_FILE, config)


def load_events() -> dict:
    """Load events data."""
    return load_json(EVENTS_FILE, {"events": [], "modified": None})


def save_events(data: dict) -> bool:
    """Save events data."""
    data["modified"] = now_iso()
    return save_json(EVENTS_FILE, data)


def load_registry() -> dict:
    """Load registry to get paddocks."""
    return load_json(REGISTRY_FILE, {})


def load_ipm_config() -> dict:
    """Load IPM config to get products."""
    return load_json(IPM_CONFIG_FILE, {})


# =============================================================================
# Draft Management Functions
# =============================================================================

def get_draft_path(device_id: str) -> Path:
    """Get the file path for a device's draft."""
    # Sanitize device_id to prevent path traversal
    safe_id = "".join(c for c in device_id if c.isalnum() or c in "-_")
    if not safe_id:
        safe_id = "unknown"
    return DRAFTS_DIR / f"{safe_id}.json"


def get_default_draft(device_id: str) -> dict:
    """Return default empty draft structure."""
    return {
        "schema_version": DRAFT_SCHEMA_VERSION,
        "device_id": device_id,
        "user_name": "",
        "wizard_step": 1,
        "started_at": now_iso(),
        "updated_at": now_iso(),
        "data": {
            "event_type": None,
            "date": None,
            "start_time": None,
            "duration_minutes": None,
            "farm_id": None,
            "paddocks": [],
            "products": [],
            "applicator_id": None,
            "application_method": None,
            "crop_stage": None,
            "irrigation_type": None,
            "notes": "",
            "weather": None
        }
    }


def load_draft(device_id: str) -> Optional[dict]:
    """Load a draft for a device, returns None if not found."""
    draft_path = get_draft_path(device_id)
    if not draft_path.exists():
        return None
    return load_json(draft_path, None)


def save_draft(draft: dict) -> bool:
    """Save a draft to file."""
    device_id = draft.get("device_id", "unknown")
    draft_path = get_draft_path(device_id)
    draft["updated_at"] = now_iso()
    return save_json(draft_path, draft)


def delete_draft(device_id: str) -> bool:
    """Delete a draft file."""
    draft_path = get_draft_path(device_id)
    try:
        if draft_path.exists():
            draft_path.unlink()
        return True
    except IOError as e:
        print(f"ERROR: Failed to delete draft: {e}", file=sys.stderr)
        return False


def list_all_drafts() -> list:
    """List all drafts with metadata."""
    drafts = []
    if not DRAFTS_DIR.exists():
        return drafts

    for draft_file in DRAFTS_DIR.glob("*.json"):
        draft_data = load_json(draft_file, None)
        if draft_data:
            drafts.append({
                "device_id": draft_data.get("device_id", draft_file.stem),
                "user_name": draft_data.get("user_name", ""),
                "wizard_step": draft_data.get("wizard_step", 1),
                "started_at": draft_data.get("started_at"),
                "updated_at": draft_data.get("updated_at"),
                "event_type": draft_data.get("data", {}).get("event_type")
            })
    return drafts


def generate_batch_id() -> str:
    """Generate a unique batch ID for multi-paddock submissions."""
    chars = string.ascii_lowercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(8))
    return f"batch_{suffix}"


# =============================================================================
# Applicator Management Functions
# =============================================================================

def generate_applicator_id(name: str) -> str:
    """Generate a unique applicator ID from name."""
    # Create slug from name
    slug = name.lower().replace(" ", "_")
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    # Add random suffix for uniqueness
    chars = string.ascii_lowercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(4))
    return f"app_{slug}_{suffix}"


def load_applicators() -> dict:
    """Load applicators data."""
    default = {
        "version": "1.0.0",
        "applicators": [],
        "attribute_templates": {},
        "created": now_iso(),
        "modified": now_iso()
    }
    return load_json(APPLICATORS_FILE, default)


def save_applicators(data: dict) -> bool:
    """Save applicators data."""
    data["modified"] = now_iso()
    return save_json(APPLICATORS_FILE, data)


def get_applicator_by_id(applicator_id: str) -> Optional[dict]:
    """Get an applicator by ID."""
    data = load_applicators()
    for app in data.get("applicators", []):
        if app.get("id") == applicator_id:
            return app
    return None


def get_applicator_snapshot(applicator_id: str) -> Optional[dict]:
    """Get a snapshot of applicator for embedding in events."""
    app = get_applicator_by_id(applicator_id)
    if not app:
        return None

    return {
        "id": app["id"],
        "name": app["name"],
        "type": app["type"],
        "snapshot_at": now_iso(),
        "attributes": app.get("attributes", {})
    }


def get_default_config() -> dict:
    """Return default HFM configuration."""
    return {
        "version": get_version(),
        "crop_stages": [
            {"id": "germination", "name": "Germination", "order": 1},
            {"id": "tillering", "name": "Tillering", "order": 2},
            {"id": "panicle_init", "name": "Panicle Initiation", "order": 3},
            {"id": "flowering", "name": "Flowering", "order": 4},
            {"id": "maturity", "name": "Maturity", "order": 5},
        ],
        "application_methods": [
            {"id": "boom_spray", "name": "Boom Spray"},
            {"id": "broadcast", "name": "Broadcast"},
            {"id": "aerial", "name": "Aerial"},
            {"id": "fertigation", "name": "Fertigation"},
            {"id": "seed_treatment", "name": "Seed Treatment"},
            {"id": "foliar", "name": "Foliar"},
        ],
        "irrigation_types": [
            {"id": "flush", "name": "Flush"},
            {"id": "permanent_water", "name": "Permanent Water"},
            {"id": "drain", "name": "Drain"},
        ],
        "devices": {},
        "voice_enabled": False,
        "created": now_iso(),
        "modified": now_iso(),
    }


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize HFM with default config."""
    # Create directories
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    # Create config if not exists
    if not CONFIG_FILE.exists():
        config = get_default_config()
        if not save_config(config):
            return 1
        print("OK:config_created")
    else:
        print("OK:config_exists")

    # Create events file if not exists
    if not EVENTS_FILE.exists():
        events_data = {"events": [], "modified": now_iso()}
        if not save_events(events_data):
            return 1
        print("OK:events_created")
    else:
        print("OK:events_exists")

    print("OK:drafts_dir_ready")
    return 0


def cmd_add_event(args: argparse.Namespace) -> int:
    """Add a new farm event."""
    config = load_config()
    if not config:
        print("ERROR: HFM not initialized. Run init first.", file=sys.stderr)
        return 1

    # Validate event type
    valid_types = ["nutrient", "chemical", "irrigation", "crop_stage"]
    if args.event_type not in valid_types:
        print(f"ERROR: Invalid event_type '{args.event_type}'. Must be one of: {valid_types}", file=sys.stderr)
        return 1

    # Parse paddocks (JSON array)
    try:
        paddocks = json.loads(args.paddocks) if args.paddocks else []
    except json.JSONDecodeError:
        # Try as comma-separated string
        paddocks = [p.strip() for p in args.paddocks.split(",") if p.strip()]

    if not paddocks:
        print("ERROR: At least one paddock is required.", file=sys.stderr)
        return 1

    # Validate paddocks against registry
    registry = load_registry()
    reg_paddocks = registry.get("paddocks", {})
    for pid in paddocks:
        if pid not in reg_paddocks:
            print(f"ERROR: Unknown paddock '{pid}'. Check Farm Registry.", file=sys.stderr)
            return 1

    # Parse products (JSON array)
    products = []
    if args.products:
        try:
            products = json.loads(args.products) if args.products else []
        except json.JSONDecodeError:
            print("ERROR: Invalid products JSON.", file=sys.stderr)
            return 1

    # Validate products for nutrient/chemical events
    if args.event_type in ["nutrient", "chemical"] and not products:
        print("ERROR: Products required for nutrient/chemical events.", file=sys.stderr)
        return 1

    # Validate irrigation type
    irrigation_type = None
    if args.event_type == "irrigation":
        if not args.irrigation_type:
            print("ERROR: irrigation_type required for irrigation events.", file=sys.stderr)
            return 1
        valid_irrigation = [it["id"] for it in config.get("irrigation_types", [])]
        if args.irrigation_type not in valid_irrigation:
            print(f"ERROR: Invalid irrigation_type '{args.irrigation_type}'.", file=sys.stderr)
            return 1
        irrigation_type = args.irrigation_type

    # Validate crop stage
    crop_stage = None
    if args.crop_stage:
        valid_stages = [cs["id"] for cs in config.get("crop_stages", [])]
        if args.crop_stage not in valid_stages:
            print(f"ERROR: Invalid crop_stage '{args.crop_stage}'.", file=sys.stderr)
            return 1
        crop_stage = args.crop_stage

    # Validate application method
    application_method = None
    if args.application_method:
        valid_methods = [am["id"] for am in config.get("application_methods", [])]
        if args.application_method not in valid_methods:
            print(f"ERROR: Invalid application_method '{args.application_method}'.", file=sys.stderr)
            return 1
        application_method = args.application_method

    # Determine event date
    event_date = args.event_date if args.event_date else today_date()

    # Create event
    event_id = generate_event_id()
    event = {
        "id": event_id,
        "event_type": args.event_type,
        "event_date": event_date,
        "recorded_at": now_iso(),
        "recorded_by_device": args.device_id or "unknown",
        "paddocks": paddocks,
        "products": products,
        "application_method": application_method,
        "crop_stage": crop_stage,
        "irrigation_type": irrigation_type,
        "notes": args.notes or "",
        "confirmation_status": "confirmed" if not args.pending else "pending",
        "voice_transcript": args.voice_transcript or None,
        "voice_source": args.voice_source or None,
    }

    # Save event
    data = load_events()
    data["events"].append(event)
    if not save_events(data):
        return 1

    print(f"OK:event_added:{event_id}")
    return 0


def cmd_edit_event(args: argparse.Namespace) -> int:
    """Edit an existing event."""
    data = load_events()
    events = data.get("events", [])

    # Find event
    event_idx = None
    for i, evt in enumerate(events):
        if evt.get("id") == args.event_id:
            event_idx = i
            break

    if event_idx is None:
        print(f"ERROR: Event '{args.event_id}' not found.", file=sys.stderr)
        return 1

    event = events[event_idx]
    config = load_config()

    # Update fields if provided
    if args.event_date:
        event["event_date"] = args.event_date

    if args.paddocks:
        try:
            paddocks = json.loads(args.paddocks)
        except json.JSONDecodeError:
            paddocks = [p.strip() for p in args.paddocks.split(",") if p.strip()]
        if paddocks:
            registry = load_registry()
            reg_paddocks = registry.get("paddocks", {})
            for pid in paddocks:
                if pid not in reg_paddocks:
                    print(f"ERROR: Unknown paddock '{pid}'.", file=sys.stderr)
                    return 1
            event["paddocks"] = paddocks

    if args.products:
        try:
            products = json.loads(args.products)
            event["products"] = products
        except json.JSONDecodeError:
            print("ERROR: Invalid products JSON.", file=sys.stderr)
            return 1

    if args.application_method:
        valid_methods = [am["id"] for am in config.get("application_methods", [])]
        if args.application_method not in valid_methods:
            print(f"ERROR: Invalid application_method.", file=sys.stderr)
            return 1
        event["application_method"] = args.application_method

    if args.crop_stage:
        valid_stages = [cs["id"] for cs in config.get("crop_stages", [])]
        if args.crop_stage not in valid_stages:
            print(f"ERROR: Invalid crop_stage.", file=sys.stderr)
            return 1
        event["crop_stage"] = args.crop_stage

    if args.irrigation_type:
        valid_irrigation = [it["id"] for it in config.get("irrigation_types", [])]
        if args.irrigation_type not in valid_irrigation:
            print(f"ERROR: Invalid irrigation_type.", file=sys.stderr)
            return 1
        event["irrigation_type"] = args.irrigation_type

    if args.notes is not None:
        event["notes"] = args.notes

    event["modified_at"] = now_iso()
    events[event_idx] = event
    data["events"] = events

    if not save_events(data):
        return 1

    print(f"OK:event_edited:{args.event_id}")
    return 0


def cmd_delete_event(args: argparse.Namespace) -> int:
    """Delete an event."""
    data = load_events()
    events = data.get("events", [])

    # Find and remove event
    new_events = [e for e in events if e.get("id") != args.event_id]
    if len(new_events) == len(events):
        print(f"ERROR: Event '{args.event_id}' not found.", file=sys.stderr)
        return 1

    data["events"] = new_events
    if not save_events(data):
        return 1

    print(f"OK:event_deleted:{args.event_id}")
    return 0


def cmd_confirm_event(args: argparse.Namespace) -> int:
    """Confirm a pending event."""
    data = load_events()
    events = data.get("events", [])

    for event in events:
        if event.get("id") == args.event_id:
            event["confirmation_status"] = "confirmed"
            event["confirmed_at"] = now_iso()
            if not save_events(data):
                return 1
            print(f"OK:event_confirmed:{args.event_id}")
            return 0

    print(f"ERROR: Event '{args.event_id}' not found.", file=sys.stderr)
    return 1


def cmd_add_crop_stage(args: argparse.Namespace) -> int:
    """Add a custom crop stage."""
    config = load_config()
    if not config:
        print("ERROR: HFM not initialized.", file=sys.stderr)
        return 1

    stages = config.get("crop_stages", [])

    # Check for duplicate ID
    for stage in stages:
        if stage["id"] == args.stage_id:
            print(f"ERROR: Crop stage '{args.stage_id}' already exists.", file=sys.stderr)
            return 1

    # Determine order (add to end)
    max_order = max((s.get("order", 0) for s in stages), default=0)

    stages.append({
        "id": args.stage_id,
        "name": args.name,
        "order": max_order + 1,
    })

    config["crop_stages"] = stages
    if not save_config(config):
        return 1

    print(f"OK:crop_stage_added:{args.stage_id}")
    return 0


def cmd_delete_crop_stage(args: argparse.Namespace) -> int:
    """Delete a crop stage."""
    config = load_config()
    if not config:
        print("ERROR: HFM not initialized.", file=sys.stderr)
        return 1

    stages = config.get("crop_stages", [])
    new_stages = [s for s in stages if s["id"] != args.stage_id]

    if len(new_stages) == len(stages):
        print(f"ERROR: Crop stage '{args.stage_id}' not found.", file=sys.stderr)
        return 1

    config["crop_stages"] = new_stages
    if not save_config(config):
        return 1

    print(f"OK:crop_stage_deleted:{args.stage_id}")
    return 0


def cmd_add_device(args: argparse.Namespace) -> int:
    """Add or update a device-to-user mapping."""
    config = load_config()
    if not config:
        print("ERROR: HFM not initialized.", file=sys.stderr)
        return 1

    devices = config.get("devices", {})
    devices[args.device_id] = {
        "name": args.device_name or args.device_id,
        "user_name": args.user_name,
    }

    config["devices"] = devices
    if not save_config(config):
        return 1

    print(f"OK:device_added:{args.device_id}")
    return 0


def cmd_delete_device(args: argparse.Namespace) -> int:
    """Remove a device mapping."""
    config = load_config()
    if not config:
        print("ERROR: HFM not initialized.", file=sys.stderr)
        return 1

    devices = config.get("devices", {})
    if args.device_id not in devices:
        print(f"ERROR: Device '{args.device_id}' not found.", file=sys.stderr)
        return 1

    del devices[args.device_id]
    config["devices"] = devices
    if not save_config(config):
        return 1

    print(f"OK:device_deleted:{args.device_id}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export events to backup file."""
    data = load_events()
    config = load_config()

    # Create export package
    export_data = {
        "export_type": "hfm_events",
        "exported_at": now_iso(),
        "version": get_version(),
        "config": config,
        "events": data.get("events", []),
    }

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"hfm_export_{timestamp}.json"
    export_path = BACKUPS_DIR / filename

    if not save_json(export_path, export_data):
        return 1

    print(f"OK:exported:{export_path}")
    return 0


# =============================================================================
# Draft Commands
# =============================================================================

def cmd_load_draft(args: argparse.Namespace) -> int:
    """Load or create a draft for a device."""
    device_id = args.device_id
    if not device_id:
        print("ERROR: device_id is required.", file=sys.stderr)
        return 1

    # Ensure drafts directory exists
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    # Try to load existing draft
    draft = load_draft(device_id)

    if draft is None:
        # Create new draft
        draft = get_default_draft(device_id)

        # Look up user name from device mapping if available
        config = load_config()
        devices = config.get("devices", {})
        if device_id in devices:
            draft["user_name"] = devices[device_id].get("user_name", "")

        if not save_draft(draft):
            return 1
        print(f"OK:draft_created:{device_id}")
    else:
        print(f"OK:draft_loaded:{device_id}")

    # Output draft as JSON for parsing
    print(json.dumps(draft, ensure_ascii=False))
    return 0


def cmd_update_draft(args: argparse.Namespace) -> int:
    """Update draft fields for a device."""
    device_id = args.device_id
    if not device_id:
        print("ERROR: device_id is required.", file=sys.stderr)
        return 1

    # Load existing draft or create new one
    draft = load_draft(device_id)
    if draft is None:
        draft = get_default_draft(device_id)

    # Parse updates JSON
    try:
        updates = json.loads(args.data) if args.data else {}
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in data: {e}", file=sys.stderr)
        return 1

    # Apply updates
    # Top-level fields
    if "wizard_step" in updates:
        draft["wizard_step"] = int(updates["wizard_step"])
    if "user_name" in updates:
        draft["user_name"] = updates["user_name"]

    # Data fields (nested under "data")
    data_updates = updates.get("data", {})
    for key, value in data_updates.items():
        if key in draft["data"]:
            draft["data"][key] = value
        else:
            # Allow adding new keys for future extensibility
            draft["data"][key] = value

    # Handle direct data field updates (for convenience)
    direct_data_keys = ["event_type", "date", "start_time", "duration_minutes",
                        "farm_id", "paddocks", "products", "applicator_id",
                        "application_method", "crop_stage", "irrigation_type", "notes"]
    for key in direct_data_keys:
        if key in updates and key not in ["wizard_step", "user_name", "data"]:
            draft["data"][key] = updates[key]

    if not save_draft(draft):
        return 1

    print(f"OK:draft_updated:{device_id}")
    print(json.dumps(draft, ensure_ascii=False))
    return 0


def cmd_clear_draft(args: argparse.Namespace) -> int:
    """Clear/delete a draft for a device."""
    device_id = args.device_id
    if not device_id:
        print("ERROR: device_id is required.", file=sys.stderr)
        return 1

    if delete_draft(device_id):
        print(f"OK:draft_cleared:{device_id}")
        return 0
    return 1


def cmd_submit_draft(args: argparse.Namespace) -> int:
    """Submit draft as event(s). Expands multi-paddock to multiple records."""
    device_id = args.device_id
    if not device_id:
        print("ERROR: device_id is required.", file=sys.stderr)
        return 1

    # Load draft
    draft = load_draft(device_id)
    if draft is None:
        print(f"ERROR: No draft found for device '{device_id}'.", file=sys.stderr)
        return 1

    data = draft.get("data", {})
    config = load_config()
    registry = load_registry()

    # Validate required fields
    event_type = data.get("event_type")
    if not event_type:
        print("ERROR: event_type is required.", file=sys.stderr)
        return 1

    valid_types = ["nutrient", "chemical", "irrigation", "crop_stage"]
    if event_type not in valid_types:
        print(f"ERROR: Invalid event_type '{event_type}'.", file=sys.stderr)
        return 1

    # Get paddocks
    paddocks = data.get("paddocks", [])
    if not paddocks:
        print("ERROR: At least one paddock is required.", file=sys.stderr)
        return 1

    # Validate paddocks
    reg_paddocks = registry.get("paddocks", {})
    reg_farms = registry.get("farms", {})
    for pid in paddocks:
        if pid not in reg_paddocks:
            print(f"ERROR: Unknown paddock '{pid}'.", file=sys.stderr)
            return 1

    # Validate products for nutrient/chemical
    products = data.get("products", [])
    if event_type in ["nutrient", "chemical"] and not products:
        print("ERROR: Products required for nutrient/chemical events.", file=sys.stderr)
        return 1

    # Validate irrigation type
    if event_type == "irrigation":
        irrigation_type = data.get("irrigation_type")
        if not irrigation_type:
            print("ERROR: irrigation_type required for irrigation events.", file=sys.stderr)
            return 1
        valid_irrigation = [it["id"] for it in config.get("irrigation_types", [])]
        if irrigation_type not in valid_irrigation:
            print(f"ERROR: Invalid irrigation_type '{irrigation_type}'.", file=sys.stderr)
            return 1

    # Determine event date
    event_date = data.get("date") or today_date()

    # Generate batch ID if multiple paddocks
    batch_id = generate_batch_id() if len(paddocks) > 1 else None
    batch_total = len(paddocks)

    # Get farm info
    farm_id = data.get("farm_id")
    farm_name = ""
    if farm_id and farm_id in reg_farms:
        farm_name = reg_farms[farm_id].get("name", farm_id)

    # Get user info
    user_name = draft.get("user_name", "")

    # Get applicator snapshot if specified
    applicator_id = data.get("applicator_id")
    applicator_snapshot = None
    if applicator_id:
        applicator_snapshot = get_applicator_snapshot(applicator_id)
        if not applicator_snapshot:
            print(f"WARNING: Applicator '{applicator_id}' not found, continuing without.", file=sys.stderr)

    # Get weather data from draft
    weather_data = data.get("weather")

    # Calculate end_time if start_time and duration provided
    start_time = data.get("start_time")
    duration_minutes = data.get("duration_minutes")
    end_time = None
    if start_time and duration_minutes:
        try:
            start_parts = start_time.split(":")
            start_hour = int(start_parts[0])
            start_min = int(start_parts[1]) if len(start_parts) > 1 else 0
            total_minutes = start_hour * 60 + start_min + int(duration_minutes)
            end_hour = (total_minutes // 60) % 24
            end_min = total_minutes % 60
            end_time = f"{end_hour:02d}:{end_min:02d}"
        except (ValueError, IndexError):
            pass

    # Load events file
    events_data = load_events()
    created_ids = []

    # Create one event per paddock
    for idx, paddock_id in enumerate(paddocks, start=1):
        paddock_info = reg_paddocks.get(paddock_id, {})
        paddock_name = paddock_info.get("name", paddock_id)
        paddock_area = paddock_info.get("area_ha")

        event_id = generate_event_id()

        event = {
            "id": event_id,
            "schema_version": DRAFT_SCHEMA_VERSION,
            "batch_id": batch_id,
            "batch_index": idx if batch_id else None,
            "batch_total": batch_total if batch_id else None,
            "event_type": event_type,
            "farm": {
                "id": farm_id,
                "name": farm_name
            } if farm_id else None,
            "paddock": {
                "id": paddock_id,
                "name": paddock_name,
                "area_ha": paddock_area
            },
            "application_timing": {
                "date": event_date,
                "start_time": start_time,
                "duration_minutes": int(duration_minutes) if duration_minutes else None,
                "end_time": end_time
            } if start_time else {"date": event_date},
            "products": products,
            "applicator": applicator_snapshot,
            "application_method": data.get("application_method"),
            "crop_stage": data.get("crop_stage"),
            "irrigation_type": data.get("irrigation_type"),
            "weather": weather_data,
            "operator": {
                "device_id": device_id,
                "user_name": user_name
            },
            "notes": data.get("notes", ""),
            "confirmation_status": "confirmed",
            "recorded_at": now_iso(),
            "modified_at": None
        }

        events_data["events"].append(event)
        created_ids.append(event_id)

    # Save events
    if not save_events(events_data):
        return 1

    # Delete the draft after successful submission
    delete_draft(device_id)

    # Output result
    if batch_id:
        print(f"OK:events_created:{batch_id}:{len(created_ids)}")
    else:
        print(f"OK:event_created:{created_ids[0]}")

    print(json.dumps({"event_ids": created_ids, "batch_id": batch_id}, ensure_ascii=False))
    return 0


def cmd_cleanup_drafts(args: argparse.Namespace) -> int:
    """Remove drafts older than specified hours."""
    max_age_hours = args.max_age_hours or 24

    if not DRAFTS_DIR.exists():
        print("OK:no_drafts_dir")
        return 0

    now = datetime.now()
    deleted_count = 0
    kept_count = 0

    for draft_file in DRAFTS_DIR.glob("*.json"):
        draft_data = load_json(draft_file, None)
        if draft_data:
            updated_at = draft_data.get("updated_at") or draft_data.get("started_at")
            if updated_at:
                try:
                    draft_time = datetime.fromisoformat(updated_at)
                    age_hours = (now - draft_time).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        draft_file.unlink()
                        deleted_count += 1
                        continue
                except (ValueError, TypeError):
                    pass
        kept_count += 1

    print(f"OK:cleanup_complete:deleted={deleted_count}:kept={kept_count}")
    return 0


# =============================================================================
# Applicator Commands
# =============================================================================

def cmd_add_applicator(args: argparse.Namespace) -> int:
    """Add a new applicator."""
    name = args.name
    app_type = args.type

    if not name:
        print("ERROR: name is required.", file=sys.stderr)
        return 1

    if not app_type:
        print("ERROR: type is required.", file=sys.stderr)
        return 1

    if app_type not in VALID_APPLICATOR_TYPES:
        print(f"ERROR: Invalid type '{app_type}'. Must be one of: {VALID_APPLICATOR_TYPES}", file=sys.stderr)
        return 1

    # Parse attributes JSON
    attributes = {}
    if args.attributes:
        try:
            attributes = json.loads(args.attributes)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid attributes JSON: {e}", file=sys.stderr)
            return 1

    # Load existing data
    data = load_applicators()
    applicators = data.get("applicators", [])

    # Check for duplicate name
    for app in applicators:
        if app.get("name", "").lower() == name.lower():
            print(f"ERROR: Applicator with name '{name}' already exists.", file=sys.stderr)
            return 1

    # Generate ID
    app_id = generate_applicator_id(name)

    # Create applicator
    applicator = {
        "id": app_id,
        "name": name,
        "type": app_type,
        "active": True,
        "attributes": attributes,
        "created": now_iso(),
        "modified": now_iso()
    }

    applicators.append(applicator)
    data["applicators"] = applicators

    if not save_applicators(data):
        return 1

    print(f"OK:applicator_added:{app_id}")
    print(json.dumps(applicator, ensure_ascii=False))
    return 0


def cmd_edit_applicator(args: argparse.Namespace) -> int:
    """Edit an existing applicator."""
    app_id = args.id

    if not app_id:
        print("ERROR: id is required.", file=sys.stderr)
        return 1

    data = load_applicators()
    applicators = data.get("applicators", [])

    # Find applicator
    app_idx = None
    for i, app in enumerate(applicators):
        if app.get("id") == app_id:
            app_idx = i
            break

    if app_idx is None:
        print(f"ERROR: Applicator '{app_id}' not found.", file=sys.stderr)
        return 1

    applicator = applicators[app_idx]

    # Update fields if provided
    if args.name:
        # Check for duplicate name (excluding self)
        for app in applicators:
            if app.get("id") != app_id and app.get("name", "").lower() == args.name.lower():
                print(f"ERROR: Applicator with name '{args.name}' already exists.", file=sys.stderr)
                return 1
        applicator["name"] = args.name

    if args.type:
        if args.type not in VALID_APPLICATOR_TYPES:
            print(f"ERROR: Invalid type '{args.type}'.", file=sys.stderr)
            return 1
        applicator["type"] = args.type

    if args.active is not None:
        applicator["active"] = args.active.lower() == "true"

    if args.attributes:
        try:
            new_attrs = json.loads(args.attributes)
            # Merge with existing attributes
            existing_attrs = applicator.get("attributes", {})
            existing_attrs.update(new_attrs)
            applicator["attributes"] = existing_attrs
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid attributes JSON: {e}", file=sys.stderr)
            return 1

    applicator["modified"] = now_iso()
    applicators[app_idx] = applicator
    data["applicators"] = applicators

    if not save_applicators(data):
        return 1

    print(f"OK:applicator_edited:{app_id}")
    print(json.dumps(applicator, ensure_ascii=False))
    return 0


def cmd_delete_applicator(args: argparse.Namespace) -> int:
    """Delete an applicator (soft delete by setting active=false, or hard delete)."""
    app_id = args.id

    if not app_id:
        print("ERROR: id is required.", file=sys.stderr)
        return 1

    data = load_applicators()
    applicators = data.get("applicators", [])

    if args.hard:
        # Hard delete - remove from list
        new_applicators = [a for a in applicators if a.get("id") != app_id]
        if len(new_applicators) == len(applicators):
            print(f"ERROR: Applicator '{app_id}' not found.", file=sys.stderr)
            return 1
        data["applicators"] = new_applicators
    else:
        # Soft delete - set active=false
        found = False
        for app in applicators:
            if app.get("id") == app_id:
                app["active"] = False
                app["modified"] = now_iso()
                found = True
                break

        if not found:
            print(f"ERROR: Applicator '{app_id}' not found.", file=sys.stderr)
            return 1

        data["applicators"] = applicators

    if not save_applicators(data):
        return 1

    action = "deleted" if args.hard else "deactivated"
    print(f"OK:applicator_{action}:{app_id}")
    return 0


def cmd_list_applicators(args: argparse.Namespace) -> int:
    """List all applicators."""
    data = load_applicators()
    applicators = data.get("applicators", [])

    if args.active_only:
        applicators = [a for a in applicators if a.get("active", True)]

    if args.type:
        applicators = [a for a in applicators if a.get("type") == args.type]

    output = {
        "count": len(applicators),
        "applicators": applicators,
        "attribute_templates": data.get("attribute_templates", {})
    }

    print(json.dumps(output, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description="HFM Backend")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init
    subparsers.add_parser("init", help="Initialize HFM")

    # add_event
    add_event_p = subparsers.add_parser("add_event", help="Add a farm event")
    add_event_p.add_argument("--event_type", required=True, help="Event type: nutrient, chemical, irrigation, crop_stage")
    add_event_p.add_argument("--event_date", help="Event date (YYYY-MM-DD)")
    add_event_p.add_argument("--paddocks", required=True, help="Paddock IDs (JSON array or comma-separated)")
    add_event_p.add_argument("--products", help="Products JSON array")
    add_event_p.add_argument("--application_method", help="Application method ID")
    add_event_p.add_argument("--crop_stage", help="Crop stage ID")
    add_event_p.add_argument("--irrigation_type", help="Irrigation type ID")
    add_event_p.add_argument("--notes", help="Optional notes")
    add_event_p.add_argument("--device_id", help="Recording device ID")
    add_event_p.add_argument("--pending", action="store_true", help="Mark as pending confirmation")
    add_event_p.add_argument("--voice_transcript", help="Voice transcript (for voice-recorded events)")
    add_event_p.add_argument("--voice_source", help="Voice source provider")

    # edit_event
    edit_event_p = subparsers.add_parser("edit_event", help="Edit an event")
    edit_event_p.add_argument("--event_id", required=True, help="Event ID to edit")
    edit_event_p.add_argument("--event_date", help="New event date")
    edit_event_p.add_argument("--paddocks", help="New paddock IDs")
    edit_event_p.add_argument("--products", help="New products JSON")
    edit_event_p.add_argument("--application_method", help="New application method")
    edit_event_p.add_argument("--crop_stage", help="New crop stage")
    edit_event_p.add_argument("--irrigation_type", help="New irrigation type")
    edit_event_p.add_argument("--notes", help="New notes")

    # delete_event
    delete_event_p = subparsers.add_parser("delete_event", help="Delete an event")
    delete_event_p.add_argument("--event_id", required=True, help="Event ID to delete")

    # confirm_event
    confirm_event_p = subparsers.add_parser("confirm_event", help="Confirm a pending event")
    confirm_event_p.add_argument("--event_id", required=True, help="Event ID to confirm")

    # add_crop_stage
    add_stage_p = subparsers.add_parser("add_crop_stage", help="Add a crop stage")
    add_stage_p.add_argument("--stage_id", required=True, help="Unique stage ID")
    add_stage_p.add_argument("--name", required=True, help="Display name")

    # delete_crop_stage
    del_stage_p = subparsers.add_parser("delete_crop_stage", help="Delete a crop stage")
    del_stage_p.add_argument("--stage_id", required=True, help="Stage ID to delete")

    # add_device
    add_device_p = subparsers.add_parser("add_device", help="Add device mapping")
    add_device_p.add_argument("--device_id", required=True, help="Device ID")
    add_device_p.add_argument("--device_name", help="Device display name")
    add_device_p.add_argument("--user_name", required=True, help="User name")

    # delete_device
    del_device_p = subparsers.add_parser("delete_device", help="Remove device mapping")
    del_device_p.add_argument("--device_id", required=True, help="Device ID to remove")

    # export
    subparsers.add_parser("export", help="Export events to backup")

    # --- Draft commands ---

    # load_draft
    load_draft_p = subparsers.add_parser("load_draft", help="Load or create a draft for a device")
    load_draft_p.add_argument("--device-id", required=True, help="Unique device identifier")

    # update_draft
    update_draft_p = subparsers.add_parser("update_draft", help="Update draft fields")
    update_draft_p.add_argument("--device-id", required=True, help="Unique device identifier")
    update_draft_p.add_argument("--data", required=True, help="JSON object with fields to update")

    # clear_draft
    clear_draft_p = subparsers.add_parser("clear_draft", help="Clear/delete a draft")
    clear_draft_p.add_argument("--device-id", required=True, help="Unique device identifier")

    # submit_draft
    submit_draft_p = subparsers.add_parser("submit_draft", help="Submit draft as event(s)")
    submit_draft_p.add_argument("--device-id", required=True, help="Unique device identifier")

    # cleanup_drafts
    cleanup_drafts_p = subparsers.add_parser("cleanup_drafts", help="Remove old drafts")
    cleanup_drafts_p.add_argument("--max-age-hours", type=int, default=24, help="Max age in hours (default: 24)")

    # --- Applicator commands ---

    # add_applicator
    add_app_p = subparsers.add_parser("add_applicator", help="Add a new applicator")
    add_app_p.add_argument("--name", required=True, help="Applicator name")
    add_app_p.add_argument("--type", required=True, help="Applicator type (boom_spray, broadcast, aerial, fertigation, seed_treatment, foliar)")
    add_app_p.add_argument("--attributes", help="JSON object with applicator attributes")

    # edit_applicator
    edit_app_p = subparsers.add_parser("edit_applicator", help="Edit an applicator")
    edit_app_p.add_argument("--id", required=True, help="Applicator ID")
    edit_app_p.add_argument("--name", help="New name")
    edit_app_p.add_argument("--type", help="New type")
    edit_app_p.add_argument("--active", help="Active status (true/false)")
    edit_app_p.add_argument("--attributes", help="JSON object with attributes to update/add")

    # delete_applicator
    del_app_p = subparsers.add_parser("delete_applicator", help="Delete an applicator")
    del_app_p.add_argument("--id", required=True, help="Applicator ID")
    del_app_p.add_argument("--hard", action="store_true", help="Hard delete (remove completely)")

    # list_applicators
    list_app_p = subparsers.add_parser("list_applicators", help="List applicators")
    list_app_p.add_argument("--active-only", action="store_true", help="Only show active applicators")
    list_app_p.add_argument("--type", help="Filter by type")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "init": cmd_init,
        "add_event": cmd_add_event,
        "edit_event": cmd_edit_event,
        "delete_event": cmd_delete_event,
        "confirm_event": cmd_confirm_event,
        "add_crop_stage": cmd_add_crop_stage,
        "delete_crop_stage": cmd_delete_crop_stage,
        "add_device": cmd_add_device,
        "delete_device": cmd_delete_device,
        "export": cmd_export,
        "load_draft": cmd_load_draft,
        "update_draft": cmd_update_draft,
        "clear_draft": cmd_clear_draft,
        "submit_draft": cmd_submit_draft,
        "cleanup_drafts": cmd_cleanup_drafts,
        "add_applicator": cmd_add_applicator,
        "edit_applicator": cmd_edit_applicator,
        "delete_applicator": cmd_delete_applicator,
        "list_applicators": cmd_list_applicators,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
