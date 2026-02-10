"""PaddiSense license validation (offline-capable with optional tracking)."""
from __future__ import annotations

import base64
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

try:
    import aiohttp
except ImportError:
    aiohttp = None

_LOGGER = logging.getLogger(__name__)

PUBLIC_KEY_PATH = Path(__file__).parent / "keys" / "public.pem"
LICENSE_PREFIX = "PADDISENSE."

# Tracking endpoint configuration
# Set via environment variable or edit directly here
# Example: export PADDISENSE_TRACKING_URL="http://your-server:5051/activations"
import os
TRACKING_URL: str | None = os.environ.get("PADDISENSE_TRACKING_URL")


class LicenseError(Exception):
    """License validation error."""

    pass


class LicenseInfo:
    """Validated license information."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize license info from decoded payload."""
        self.email: str = data["email"]
        self.season: str = data["season"]
        self.expiry: date = date.fromisoformat(data["expiry"])
        self.modules: list[str] = data.get("modules", [])
        self.issued: date = date.fromisoformat(data["issued"])
        self.github_token: str | None = data.get("github_token")

    @property
    def is_expired(self) -> bool:
        """Check if license has expired."""
        return date.today() > self.expiry

    @property
    def days_remaining(self) -> int:
        """Get days until expiry (negative if expired)."""
        return (self.expiry - date.today()).days

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        result = {
            "email": self.email,
            "season": self.season,
            "expiry": self.expiry.isoformat(),
            "modules": self.modules,
            "issued": self.issued.isoformat(),
        }
        if self.github_token:
            result["github_token"] = self.github_token
        return result


def validate_license(key: str) -> LicenseInfo:
    """
    Validate a license key offline using Ed25519 signature verification.

    Args:
        key: The license key string (PADDISENSE.payload.signature)

    Returns:
        LicenseInfo with decoded license data

    Raises:
        LicenseError: If key is invalid, tampered, or expired
    """
    # Import cryptography here to provide better error if not installed
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except ImportError as err:
        raise LicenseError("missing_cryptography") from err

    # Check prefix
    if not key.startswith(LICENSE_PREFIX):
        raise LicenseError("invalid_format")

    try:
        # Split into payload and signature
        parts = key[len(LICENSE_PREFIX) :].split(".")
        if len(parts) != 2:
            raise LicenseError("invalid_format")

        payload_b64, signature_b64 = parts

        # Decode base64 (add padding if needed)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + "==")
        signature = base64.urlsafe_b64decode(signature_b64 + "==")

        # Load public key
        if not PUBLIC_KEY_PATH.exists():
            raise LicenseError("missing_public_key")

        public_key = load_pem_public_key(PUBLIC_KEY_PATH.read_bytes())

        # Verify signature
        public_key.verify(signature, payload_bytes)

        # Parse payload
        data = json.loads(payload_bytes.decode("utf-8"))

        # Validate required fields
        required_fields = ["email", "season", "expiry", "issued"]
        for field in required_fields:
            if field not in data:
                raise LicenseError("invalid_key")

        license_info = LicenseInfo(data)

        # Check expiry
        if license_info.is_expired:
            raise LicenseError("expired")

        return license_info

    except LicenseError:
        raise
    except Exception as err:
        raise LicenseError("invalid_key") from err


async def track_activation(license_info: LicenseInfo, ha_uuid: str | None = None) -> bool:
    """
    Report license activation to tracking server (optional).

    This is fire-and-forget - failures are logged but don't affect validation.

    Args:
        license_info: The validated license
        ha_uuid: Home Assistant installation UUID for deduplication

    Returns:
        True if tracking succeeded, False otherwise
    """
    if not TRACKING_URL or aiohttp is None:
        return False

    try:
        payload = {
            "email": license_info.email,
            "season": license_info.season,
            "modules": license_info.modules,
            "issued": license_info.issued.isoformat(),
            "expiry": license_info.expiry.isoformat(),
            "activated_at": date.today().isoformat(),
        }
        if ha_uuid:
            payload["installation_id"] = ha_uuid

        async with aiohttp.ClientSession() as session:
            async with session.post(
                TRACKING_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    _LOGGER.debug("License activation tracked for %s", license_info.email)
                    return True
                else:
                    _LOGGER.warning("Tracking failed with status %s", resp.status)
                    return False
    except Exception as err:
        _LOGGER.debug("Tracking failed (offline or server unavailable): %s", err)
        return False


def check_license_status(key: str) -> dict[str, Any]:
    """
    Check license status without raising on expiry.

    Returns dict with status info for sensors/UI.
    """
    try:
        license_info = validate_license(key)
        return {
            "valid": True,
            "expired": False,
            "days_remaining": license_info.days_remaining,
            "expiry": license_info.expiry.isoformat(),
            "email": license_info.email,
            "modules": license_info.modules,
            "status": "valid",
        }
    except LicenseError as err:
        error_code = str(err)
        if error_code == "expired":
            # Still decode the info for display
            try:
                parts = key[len(LICENSE_PREFIX) :].split(".")
                payload_bytes = base64.urlsafe_b64decode(parts[0] + "==")
                data = json.loads(payload_bytes.decode("utf-8"))
                return {
                    "valid": False,
                    "expired": True,
                    "days_remaining": (
                        date.fromisoformat(data["expiry"]) - date.today()
                    ).days,
                    "expiry": data["expiry"],
                    "email": data.get("email", "Unknown"),
                    "modules": data.get("modules", []),
                    "status": "expired",
                }
            except Exception:
                pass
        return {
            "valid": False,
            "expired": error_code == "expired",
            "days_remaining": 0,
            "expiry": None,
            "email": None,
            "modules": [],
            "status": error_code,
        }
