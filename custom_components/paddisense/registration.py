"""Registration management for PaddiSense (local-only)."""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .const import (
    CONFIG_DIR,
    DATA_DIR,
    DATA_SHARING_AGREEMENT_VERSION,
    FREE_MODULES,
    DATA_SHARING_MODULES,
)

_LOGGER = logging.getLogger(__name__)

# Local registration data file
REGISTRATION_FILE = DATA_DIR / "registration.json"


def generate_server_id() -> str:
    """Generate a unique server ID based on machine characteristics."""
    try:
        # Try to get machine-id if available (Linux)
        machine_id_path = Path("/etc/machine-id")
        if machine_id_path.exists():
            machine_id = machine_id_path.read_text().strip()
        else:
            # Fallback to config directory path hash
            machine_id = str(CONFIG_DIR.resolve())

        # Create a hash-based ID
        hash_input = f"paddisense-{machine_id}"
        server_id = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return f"ps-{server_id}"
    except Exception:
        # Ultimate fallback - random UUID (will change on reinstall)
        return f"ps-{uuid.uuid4().hex[:16]}"


def load_registration() -> dict[str, Any]:
    """Load registration data from local file."""
    if not REGISTRATION_FILE.exists():
        return {}
    try:
        return json.loads(REGISTRATION_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {}


def save_registration(data: dict[str, Any]) -> None:
    """Save registration data to local file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data["modified"] = datetime.now().isoformat(timespec="seconds")
    REGISTRATION_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def is_registered() -> bool:
    """Check if this server is registered."""
    reg_data = load_registration()
    return reg_data.get("registered", False)


def get_registration_info() -> dict[str, Any]:
    """Get registration info for update checks."""
    reg_data = load_registration()
    return {
        "server_id": reg_data.get("server_id", ""),
        "grower_name": reg_data.get("grower_name", ""),
        "grower_email": reg_data.get("grower_email", ""),
        "registered_at": reg_data.get("registered_at", ""),
        "installed_modules": reg_data.get("installed_modules", []),
    }


def update_installed_modules(modules: list[str]) -> None:
    """Update the list of installed modules in registration."""
    reg_data = load_registration()
    reg_data["installed_modules"] = modules
    save_registration(reg_data)


def get_allowed_modules() -> list[str]:
    """Get list of modules this registration allows."""
    reg_data = load_registration()

    if not reg_data.get("registered"):
        return []  # Not registered, no modules

    # Free modules are always available once registered
    allowed = list(FREE_MODULES)

    # Check for data-sharing agreements
    agreements = reg_data.get("agreements", {})
    for module_id in DATA_SHARING_MODULES:
        if module_id in agreements:
            allowed.append(module_id)

    return allowed


def has_agreement(module_id: str) -> bool:
    """Check if user has agreed to data-sharing for a module."""
    reg_data = load_registration()
    agreements = reg_data.get("agreements", {})
    return module_id in agreements


def record_agreement(module_id: str, agreed: bool = True) -> dict[str, Any]:
    """Record a data-sharing agreement for a module."""
    reg_data = load_registration()

    if "agreements" not in reg_data:
        reg_data["agreements"] = {}

    if agreed:
        reg_data["agreements"][module_id] = {
            "agreed_at": datetime.now().isoformat(timespec="seconds"),
            "agreement_version": DATA_SHARING_AGREEMENT_VERSION,
        }
    else:
        reg_data["agreements"].pop(module_id, None)

    save_registration(reg_data)
    return {"success": True, "module_id": module_id, "agreed": agreed}


def register_locally(
    grower_name: str,
    grower_email: str,
) -> dict[str, Any]:
    """Register this server locally (no external calls).

    Args:
        grower_name: Name of the grower/user
        grower_email: Email address

    Returns:
        Dict with registration details
    """
    server_id = generate_server_id()

    reg_data = {
        "registered": True,
        "server_id": server_id,
        "grower_name": grower_name,
        "grower_email": grower_email.lower().strip(),
        "registered_at": datetime.now().isoformat(timespec="seconds"),
        "tos_version": "1.0",
        "agreements": {},
        "installed_modules": [],
        "update_checks": [],  # Track when they check for updates
    }
    save_registration(reg_data)

    _LOGGER.info("Local registration complete for %s (server_id: %s)", grower_name, server_id)

    return {
        "success": True,
        "server_id": server_id,
        "registered_at": reg_data["registered_at"],
        "modules_allowed": list(FREE_MODULES),
    }


def record_update_check() -> None:
    """Record that an update check was performed."""
    reg_data = load_registration()

    if "update_checks" not in reg_data:
        reg_data["update_checks"] = []

    # Keep last 10 update checks
    reg_data["update_checks"].append(datetime.now().isoformat(timespec="seconds"))
    reg_data["update_checks"] = reg_data["update_checks"][-10:]
    reg_data["last_update_check"] = datetime.now().isoformat(timespec="seconds")

    save_registration(reg_data)
