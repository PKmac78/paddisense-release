"""
RTR (Real Time Rice) Backend for PaddiSense Integration.

Fetches and parses Real Time Rice prediction data from CSV endpoint.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests

from ..const import RTR_CACHE_FILE, RTR_CONFIG_FILE, RTR_DATA_DIR

_LOGGER = logging.getLogger(__name__)

# CSV column names from RTR export
CSV_COLUMNS = {
    "id": "ID",
    "zone": "Zone (%)",
    "farm": "Farm",
    "paddock": "Paddock",
    "year": "Year",
    "variety": "Variety",
    "sow_method": "Sow method",
    "sow_date": "Sow date",
    "pw_predict": "PW predict",
    "nup_predict": "Nup@PI predict",
    "pi_predict": "PI predict",
    "flowering_predict": "Flowering predict",
    "moisture_predict_date": "Moisture predict date",
    "moisture_predict": "Moisture predict",
    "harvest_date": "22% moisture date predict",
    "warnings": "Warnings",
}

# Zone to filter for (40-60cm soil depth)
TARGET_ZONE = "40-60"


class RTRBackend:
    """Backend class for RTR data operations."""

    def __init__(self) -> None:
        """Initialize the RTR backend."""
        pass

    def init(self) -> dict[str, Any]:
        """Initialize the RTR data directory."""
        RTR_DATA_DIR.mkdir(parents=True, exist_ok=True)
        return {"success": True, "message": "RTR data directory initialized"}

    def _load_config(self) -> dict[str, Any]:
        """Load RTR config from JSON file."""
        if not RTR_CONFIG_FILE.exists():
            return {"configured": False}
        try:
            return json.loads(RTR_CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {"configured": False}

    def _save_config(self, config: dict[str, Any]) -> None:
        """Save RTR config to JSON file."""
        config["modified"] = datetime.now().isoformat(timespec="seconds")
        RTR_DATA_DIR.mkdir(parents=True, exist_ok=True)
        RTR_CONFIG_FILE.write_text(
            json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _load_cache(self) -> dict[str, Any]:
        """Load cached RTR data."""
        if not RTR_CACHE_FILE.exists():
            return {"paddocks": {}, "last_updated": None}
        try:
            return json.loads(RTR_CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {"paddocks": {}, "last_updated": None}

    def _save_cache(self, data: dict[str, Any]) -> None:
        """Save RTR data to cache file."""
        data["last_updated"] = datetime.now().isoformat(timespec="seconds")
        RTR_DATA_DIR.mkdir(parents=True, exist_ok=True)
        RTR_CACHE_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _extract_csv_url(self, url: str) -> str | None:
        """Extract the CSV URL from a dashboard URL or Microsoft safelinks wrapper.

        Args:
            url: The input URL (may be a safelinks wrapper or direct URL)

        Returns:
            The extracted CSV URL or None if parsing fails
        """
        decoded_url = url

        # Check if it's a Microsoft safelinks URL
        if "safelinks.protection.outlook.com" in url:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            if "url" in query:
                decoded_url = unquote(query["url"][0])
                _LOGGER.debug("Extracted URL from safelinks: %s", decoded_url)

        # Validate it's a realtimerice URL
        if "storage.googleapis.com/realtimerice" not in decoded_url:
            _LOGGER.error("URL does not appear to be a Real Time Rice URL: %s", decoded_url)
            return None

        # Convert HTML URL to CSV URL
        if decoded_url.endswith(".html"):
            csv_url = decoded_url[:-5] + ".csv"
        elif decoded_url.endswith(".csv"):
            csv_url = decoded_url
        else:
            # Try to extract token and construct CSV URL
            match = re.search(r"rtr_dashboard_([a-zA-Z0-9_-]+)\.(html|csv)", decoded_url)
            if match:
                token = match.group(1)
                base_path = decoded_url.rsplit("/", 1)[0]
                csv_url = f"{base_path}/rtr_dashboard_{token}.csv"
            else:
                _LOGGER.error("Could not extract token from URL: %s", decoded_url)
                return None

        return csv_url

    def set_url(self, url: str) -> dict[str, Any]:
        """Parse and validate the RTR URL, extract CSV endpoint, save config.

        Args:
            url: The RTR dashboard URL (may be wrapped in Microsoft safelinks)

        Returns:
            Result dictionary with success status and extracted URLs
        """
        csv_url = self._extract_csv_url(url)

        if not csv_url:
            return {
                "success": False,
                "error": "Could not parse RTR URL. Please provide a valid Real Time Rice dashboard URL.",
            }

        # Save config
        config = {
            "configured": True,
            "original_url": url,
            "csv_url": csv_url,
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        self._save_config(config)

        _LOGGER.info("RTR URL configured: %s", csv_url)

        return {
            "success": True,
            "message": "RTR URL configured successfully",
            "csv_url": csv_url,
        }

    def refresh_data(self) -> dict[str, Any]:
        """Fetch CSV data, parse it, filter for zone 40-60, and cache as JSON.

        Returns:
            Result dictionary with success status and paddock count
        """
        config = self._load_config()

        if not config.get("configured") or not config.get("csv_url"):
            return {
                "success": False,
                "error": "RTR URL not configured. Please set the URL first.",
            }

        csv_url = config["csv_url"]

        try:
            _LOGGER.info("Fetching RTR data from: %s", csv_url)
            response = requests.get(csv_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            _LOGGER.error("Failed to fetch RTR CSV: %s", e)
            return {
                "success": False,
                "error": f"Failed to fetch RTR data: {e}",
            }

        # Parse CSV
        try:
            csv_content = response.text
            reader = csv.DictReader(io.StringIO(csv_content))

            paddocks = {}
            for row in reader:
                zone = row.get(CSV_COLUMNS["zone"], "").strip()

                # Only process zone 40-60 rows
                if zone != TARGET_ZONE:
                    continue

                paddock_name = row.get(CSV_COLUMNS["paddock"], "").strip()
                if not paddock_name:
                    continue

                # Generate a clean paddock ID
                paddock_id = re.sub(r"[^a-z0-9]+", "_", paddock_name.lower()).strip("_")

                # Extract year - RTR uses crop year (e.g., 2025 = CY25 = 2025-2026 season)
                year_str = row.get(CSV_COLUMNS["year"], "").strip()

                # Only update if this is a newer year than existing data
                # This ensures we keep the most recent season's data when CSV has multiple years
                if paddock_id in paddocks:
                    existing_year = paddocks[paddock_id].get("year", "0")
                    try:
                        if int(year_str) <= int(existing_year):
                            continue  # Skip older data
                    except ValueError:
                        pass  # If year parsing fails, overwrite

                paddocks[paddock_id] = {
                    "paddock": paddock_name,
                    "farm": row.get(CSV_COLUMNS["farm"], "").strip(),
                    "year": year_str,
                    "variety": row.get(CSV_COLUMNS["variety"], "").strip(),
                    "sow_date": row.get(CSV_COLUMNS["sow_date"], "").strip(),
                    "sow_method": row.get(CSV_COLUMNS["sow_method"], "").strip(),
                    "pi_date": row.get(CSV_COLUMNS["pi_predict"], "").strip(),
                    "flowering_date": row.get(CSV_COLUMNS["flowering_predict"], "").strip(),
                    "moisture_date": row.get(CSV_COLUMNS["moisture_predict_date"], "").strip(),
                    "moisture_predict": row.get(CSV_COLUMNS["moisture_predict"], "").strip(),
                    "harvest_date": row.get(CSV_COLUMNS["harvest_date"], "").strip(),
                    "warnings": row.get(CSV_COLUMNS["warnings"], "").strip(),
                }

            # Save to cache
            cache_data = {"paddocks": paddocks}
            self._save_cache(cache_data)

            _LOGGER.info("RTR data refreshed: %d paddocks", len(paddocks))

            return {
                "success": True,
                "message": f"RTR data refreshed: {len(paddocks)} paddocks",
                "paddock_count": len(paddocks),
            }

        except Exception as e:
            _LOGGER.error("Failed to parse RTR CSV: %s", e)
            return {
                "success": False,
                "error": f"Failed to parse RTR data: {e}",
            }

    def get_data(self) -> dict[str, Any]:
        """Return cached RTR data.

        Returns:
            Dictionary with paddock predictions and metadata
        """
        return self._load_cache()

    def get_status(self) -> dict[str, Any]:
        """Return RTR configuration status.

        Returns:
            Dictionary with configuration status and metadata
        """
        config = self._load_config()
        cache = self._load_cache()

        return {
            "configured": config.get("configured", False),
            "csv_url": config.get("csv_url"),
            "last_updated": cache.get("last_updated"),
            "paddock_count": len(cache.get("paddocks", {})),
        }

    def clear_config(self) -> dict[str, Any]:
        """Clear RTR configuration and cached data.

        Returns:
            Result dictionary with success status
        """
        try:
            if RTR_CONFIG_FILE.exists():
                RTR_CONFIG_FILE.unlink()
            if RTR_CACHE_FILE.exists():
                RTR_CACHE_FILE.unlink()

            _LOGGER.info("RTR configuration cleared")

            return {
                "success": True,
                "message": "RTR configuration cleared",
            }
        except OSError as e:
            _LOGGER.error("Failed to clear RTR config: %s", e)
            return {
                "success": False,
                "error": f"Failed to clear configuration: {e}",
            }
