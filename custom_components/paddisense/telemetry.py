"""Telemetry for PaddiSense - reports registration info on update checks.

When users check for updates, this creates/updates a GitHub issue in a
dedicated registration repository. This helps the developer:
- Know who is using PaddiSense
- Contact growers if critical updates are needed
- Understand which modules are popular

Data sent:
- Server ID (anonymous hash)
- Grower name and email
- Installed modules
- PaddiSense version
- Timestamp

No sensitive farm data, paddock names, or operational data is ever sent.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import aiohttp

from .registration import get_registration_info, record_update_check

_LOGGER = logging.getLogger(__name__)

# =============================================================================
# TELEMETRY CONFIGURATION
# =============================================================================
# Token is loaded from /config/local_data/telemetry_config.json
# This keeps the token out of git while allowing telemetry to work.
#
# To enable telemetry, create /config/local_data/telemetry_config.json:
# {
#   "github_token": "github_pat_xxx...",
#   "repo": "PKmac78/paddisense-registrations"
# }
# =============================================================================

TELEMETRY_REPO = "PKmac78/paddisense-registrations"  # Default repo


def _load_telemetry_config() -> tuple[str | None, str]:
    """Load telemetry token from local config file."""
    from pathlib import Path
    import json

    config_file = Path("/config/local_data/telemetry_config.json")
    if not config_file.exists():
        return None, TELEMETRY_REPO

    try:
        config = json.loads(config_file.read_text())
        token = config.get("github_token")
        repo = config.get("repo", TELEMETRY_REPO)
        return token, repo
    except Exception:
        return None, TELEMETRY_REPO


# =============================================================================


async def report_update_check(
    installed_modules: list[str],
    local_version: str | None,
    remote_version: str | None,
    update_available: bool,
) -> dict[str, Any]:
    """Report an update check by creating/updating a GitHub issue.

    Each server gets one issue (identified by server_id in the title).
    The issue body is updated with the latest info on each check.

    Args:
        installed_modules: List of installed module IDs
        local_version: Current installed version
        remote_version: Latest available version
        update_available: Whether an update is available

    Returns:
        Dict with success status
    """
    # Record locally first
    record_update_check()

    # Load telemetry config from local file
    token, repo = _load_telemetry_config()

    # Check if telemetry is configured
    if not token:
        _LOGGER.debug("Telemetry not configured (no token), skipping remote report")
        return {"success": True, "local_only": True}

    # Get registration info
    reg_info = get_registration_info()

    if not reg_info.get("server_id"):
        _LOGGER.debug("No registration found, skipping telemetry")
        return {"success": False, "reason": "not_registered"}

    server_id = reg_info["server_id"]
    grower_name = reg_info.get("grower_name", "Unknown")
    grower_email = reg_info.get("grower_email", "")

    # Build issue content
    issue_title = f"[Registration] {server_id} - {grower_name}"

    issue_body = f"""## PaddiSense Registration

**Server ID:** `{server_id}`
**Grower:** {grower_name}
**Email:** {grower_email}
**Registered:** {reg_info.get("registered_at", "Unknown")}

### Current Status

| Field | Value |
|-------|-------|
| Installed Version | {local_version or "Unknown"} |
| Latest Version | {remote_version or "Not checked"} |
| Update Available | {"Yes" if update_available else "No"} |
| Last Check | {datetime.now().strftime("%Y-%m-%d %H:%M")} |

### Installed Modules

{_format_modules(installed_modules)}

---
*Auto-updated by PaddiSense on update check*
"""

    # Create or update the issue
    return await _create_or_update_issue(server_id, issue_title, issue_body, token, repo)


def _format_modules(modules: list[str]) -> str:
    """Format module list for issue body."""
    if not modules:
        return "_No modules installed_"

    module_names = {
        "ipm": "Inventory Manager",
        "asm": "Asset Service Manager",
        "weather": "Weather Stations",
        "pwm": "Water Management",
        "rtr": "Real Time Rice",
        "str": "Stock Tracker",
        "wss": "Worker Safety",
        "hfm": "Hey Farmer",
    }

    lines = []
    for mod_id in sorted(modules):
        name = module_names.get(mod_id, mod_id.upper())
        lines.append(f"- {name} (`{mod_id}`)")

    return "\n".join(lines)


async def _create_or_update_issue(
    server_id: str,
    title: str,
    body: str,
    token: str,
    repo: str,
) -> dict[str, Any]:
    """Create a new issue or update existing one for this server."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "PaddiSense",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Search for existing issue with this server_id
            search_query = f"repo:{repo} is:issue {server_id} in:title"

            async with session.get(
                "https://api.github.com/search/issues",
                headers=headers,
                params={"q": search_query},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status != 200:
                    _LOGGER.warning("Failed to search issues: %s", response.status)
                    return {"success": False, "error": "search_failed"}

                search_data = await response.json()
                existing_issues = search_data.get("items", [])

            if existing_issues:
                # Update existing issue
                issue_number = existing_issues[0]["number"]

                async with session.patch(
                    f"https://api.github.com/repos/{repo}/issues/{issue_number}",
                    headers=headers,
                    json={"title": title, "body": body},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status == 200:
                        _LOGGER.debug("Updated registration issue #%s", issue_number)
                        return {"success": True, "action": "updated", "issue": issue_number}
                    else:
                        _LOGGER.warning("Failed to update issue: %s", response.status)
                        return {"success": False, "error": "update_failed"}
            else:
                # Create new issue
                async with session.post(
                    f"https://api.github.com/repos/{repo}/issues",
                    headers=headers,
                    json={
                        "title": title,
                        "body": body,
                        "labels": ["registration"],
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status == 201:
                        issue_data = await response.json()
                        issue_number = issue_data.get("number")
                        _LOGGER.debug("Created registration issue #%s", issue_number)
                        return {"success": True, "action": "created", "issue": issue_number}
                    else:
                        error_text = await response.text()
                        _LOGGER.warning("Failed to create issue: %s - %s", response.status, error_text)
                        return {"success": False, "error": "create_failed"}

    except aiohttp.ClientError as e:
        _LOGGER.debug("Telemetry network error (non-critical): %s", e)
        return {"success": False, "error": "network_error"}
    except Exception as e:
        _LOGGER.debug("Telemetry error (non-critical): %s", e)
        return {"success": False, "error": str(e)}
