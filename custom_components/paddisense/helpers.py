"""Helper utilities for PaddiSense integration."""
from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .const import (
    LOCAL_CREDENTIALS_FILE,
    MODULE_FOLDERS,
    PADDISENSE_DIR,
    REGISTRY_BACKUP_DIR,
    REGISTRY_CONFIG_FILE,
    REGISTRY_DATA_DIR,
    SERVER_YAML,
    PADDISENSE_VERSION_FILE,
)

_LOGGER = logging.getLogger(__name__)


def generate_id(name: str) -> str:
    """Generate a clean ID from a name."""
    clean = re.sub(r"[^a-z0-9]+", "_", name.lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean[:30] if clean else "unknown"


def get_version() -> str:
    """Read PaddiSense version from VERSION file."""
    try:
        if PADDISENSE_VERSION_FILE.exists():
            return PADDISENSE_VERSION_FILE.read_text(encoding="utf-8").strip()
    except IOError:
        pass
    return "unknown"


def load_registry_config() -> dict[str, Any]:
    """Load registry config from JSON file."""
    if not REGISTRY_CONFIG_FILE.exists():
        return {
            "initialized": False,
            "paddocks": {},
            "bays": {},
            "seasons": {},
            "farms": {},
            "version": "1.0.0",
        }
    try:
        return json.loads(REGISTRY_CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {
            "initialized": False,
            "paddocks": {},
            "bays": {},
            "seasons": {},
            "farms": {},
            "version": "1.0.0",
        }


def save_registry_config(config: dict[str, Any]) -> None:
    """Save registry config to JSON file."""
    config["modified"] = datetime.now().isoformat(timespec="seconds")
    REGISTRY_DATA_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def create_backup(tag: str = "") -> Path:
    """Create a timestamped backup of the config file."""
    REGISTRY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    backup_name = f"backup_{ts}{suffix}.json"
    backup_path = REGISTRY_BACKUP_DIR / backup_name
    if REGISTRY_CONFIG_FILE.exists():
        backup_path.write_text(
            REGISTRY_CONFIG_FILE.read_text(encoding="utf-8"), encoding="utf-8"
        )
    return backup_path


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
        "name": server.get("name", ""),
        "email": server.get("email", ""),
        "location": server.get("location", ""),
    }


def extract_farms(
    server_config: dict[str, Any], registry_farms: dict[str, Any]
) -> dict[str, Any]:
    """Merge farm definitions from server.yaml and config.json."""
    pwm_config = server_config.get("pwm", {})
    server_farms = dict(pwm_config.get("farms", {}))

    registry_config = server_config.get("registry", {})
    if "farms" in registry_config:
        server_farms.update(registry_config.get("farms", {}))

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


def existing_data_detected() -> bool:
    """Check if existing registry data exists."""
    return REGISTRY_CONFIG_FILE.exists()


def existing_repo_detected() -> bool:
    """Check if PaddiSense repo is already cloned."""
    return PADDISENSE_DIR.is_dir() and (PADDISENSE_DIR / ".git").is_dir()


def get_existing_data_summary() -> dict[str, Any]:
    """Get summary of existing data for import."""
    config = load_registry_config()
    return {
        "paddock_count": len(config.get("paddocks", {})),
        "bay_count": len(config.get("bays", {})),
        "season_count": len(config.get("seasons", {})),
        "farm_count": len(config.get("farms", {})),
        "initialized": config.get("initialized", False),
    }


def get_repo_summary() -> dict[str, Any]:
    """Get summary of existing PaddiSense repo."""
    if not existing_repo_detected():
        return {"exists": False}

    summary = {"exists": True}

    # Get version
    if PADDISENSE_VERSION_FILE.exists():
        try:
            summary["version"] = PADDISENSE_VERSION_FILE.read_text(encoding="utf-8").strip()
        except IOError:
            summary["version"] = "unknown"

    # Count installed modules
    from .const import AVAILABLE_MODULES, PACKAGES_DIR

    installed = []
    for mod in AVAILABLE_MODULES:
        symlink = PACKAGES_DIR / f"{mod}.yaml"
        if symlink.exists() or symlink.is_symlink():
            installed.append(mod)

    summary["installed_modules"] = installed
    summary["module_count"] = len(installed)

    return summary


def cleanup_unlicensed_modules(licensed_modules: list[str]) -> dict[str, Any]:
    """Delete folders for modules not included in the license.

    Args:
        licensed_modules: List of module IDs the user is licensed for.

    Returns:
        Dictionary with cleanup results.
    """
    removed = []
    errors = []

    for module_id, folders in MODULE_FOLDERS.items():
        if module_id not in licensed_modules:
            for folder in folders:
                path = PADDISENSE_DIR / folder
                if path.exists():
                    try:
                        shutil.rmtree(path)
                        removed.append(f"{module_id}/{folder}")
                        _LOGGER.info("Removed unlicensed module folder: %s", path)
                    except OSError as e:
                        errors.append(f"{module_id}/{folder}: {e}")
                        _LOGGER.warning("Failed to remove folder %s: %s", path, e)

    return {
        "success": len(errors) == 0,
        "removed": removed,
        "errors": errors,
    }


def load_local_credentials() -> dict[str, Any]:
    """Load locally stored credentials (license key, etc)."""
    if not LOCAL_CREDENTIALS_FILE.exists():
        return {}
    try:
        return json.loads(LOCAL_CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {}


def save_local_credentials(credentials: dict[str, Any]) -> None:
    """Save credentials to local storage."""
    LOCAL_CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_CREDENTIALS_FILE.write_text(
        json.dumps(credentials, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _LOGGER.debug("Saved local credentials to %s", LOCAL_CREDENTIALS_FILE)


def get_saved_license_key() -> str:
    """Get the saved license key, if any."""
    creds = load_local_credentials()
    return creds.get("license_key", "")


def save_license_key(license_key: str) -> None:
    """Save a valid license key to local storage."""
    creds = load_local_credentials()
    creds["license_key"] = license_key
    creds["saved_at"] = datetime.now().isoformat(timespec="seconds")
    save_local_credentials(creds)
