#!/usr/bin/env python3
"""
Weather API Sensor - External Ecowitt API Weather Stations
PaddiSense Farm Management System

Outputs ONE JSON payload for Home Assistant command_line sensor:
{
  "status": "ready|not_initialized|credentials_missing|error",
  "initialized": bool,
  "credentials_ok": bool,
  "version": "1.1.0",
  "station_count": int,
  "last_update": "ISO8601",
  "stations": {
     "1": { ... }, "2": { ... }, ...
  }
}

Config:
  /config/local_data/weather_api/config.json

Secrets expected in /config/secrets.yaml:
  ecowitt_app_key: "..."
  ecowitt_api_key: "..."
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CONFIG_DIR = Path("/config/local_data/weather_api")
CONFIG_FILE = CONFIG_DIR / "config.json"
SECRETS_FILE = Path("/config/secrets.yaml")

VALID_SLOTS = ["1", "2", "3", "4"]
VERSION = "1.1.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"stations": {}, "created": None, "modified": None}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"stations": {}, "created": None, "modified": None}


def read_secrets_keys() -> tuple[str | None, str | None]:
    """
    Lightweight parse of secrets.yaml without requiring PyYAML.
    Looks for lines like: key: "value" or key: value
    """
    if not SECRETS_FILE.exists():
        return None, None

    app_key = None
    api_key = None

    try:
        for raw in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue

            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")

            if k == "ecowitt_app_key" and v:
                app_key = v
            if k == "ecowitt_api_key" and v:
                api_key = v

        return app_key, api_key
    except Exception:
        return None, None


def base_station_payload(slot: str, cfg: dict) -> dict:
    # Normalise types safely
    imei = cfg.get("imei")
    if imei is not None:
        imei = str(imei)

    lat = cfg.get("latitude")
    try:
        lat = float(lat) if lat is not None else None
    except Exception:
        lat = None

    elev = cfg.get("elevation")
    try:
        elev = int(elev) if elev is not None else None
    except Exception:
        elev = None

    enabled = cfg.get("enabled")
    enabled = bool(enabled) if enabled is not None else True  # default ON if configured

    payload = {
        "slot": slot,
        "enabled": enabled,
        "name": cfg.get("name") or None,
        "imei": imei,
        "latitude": lat,
        "elevation": elev,
        "connected": False,

        # Data blocks (keep keys stable for templates/UI)
        "outdoor": {
            "temperature": None,
            "humidity": None,
            "feels_like": None,
            "dew_point": None,
        },
        "wind": {
            "speed": None,
            "gust": None,
            "direction": None,
        },
        "rain": {
            "rate": None,
            "hourly": None,
            "daily": None,
            "monthly": None,
            "yearly": None,
        },
        "solar": {
            "radiation": None,
            "uv_index": None,
        },
        "pressure": {
            "relative": None,
            "absolute": None,
        },
        "battery": None,
        "updated": None,
    }
    return payload


def try_fetch_ecowitt(station: dict, app_key: str, api_key: str) -> tuple[bool, dict]:
    """
    Fetch weather data from Ecowitt API using /device/info endpoint.
    Returns (success, data_dict) tuple.
    """
    try:
        import requests  # type: ignore
    except Exception:
        return False, {}

    imei = station.get("imei")
    if not imei:
        return False, {}

    # Ensure IMEI has "00" prefix as required by Ecowitt API
    imei_str = str(imei)
    if not imei_str.startswith("00"):
        imei_str = "00" + imei_str

    # Use /device/info endpoint with imei parameter
    url = "https://api.ecowitt.net/api/v3/device/info"
    params = {
        "application_key": app_key,
        "api_key": api_key,
        "imei": imei_str,
    }

    try:
        r = requests.get(url, params=params, timeout=12)
        if r.status_code != 200:
            return False, {}
        data = r.json() if r.text else {}
        # Check for API error
        if data.get("code") != 0:
            return False, {}
        return True, data
    except Exception:
        return False, {}


def map_ecowitt_to_station(station_payload: dict, api_json: dict) -> None:
    """
    Map Ecowitt /device/info response to our stable structure.
    Data is in api_json["data"]["last_update"], with values nested as field["value"].
    Applies unit conversions: F→C, mph→km/h, in→mm, inHg→hPa.
    """
    data = api_json.get("data") if isinstance(api_json, dict) else None
    if not isinstance(data, dict):
        return

    src = data.get("last_update") if isinstance(data, dict) else None
    if not isinstance(src, dict):
        return

    def get_value(d: dict, *keys) -> float | None:
        """Navigate nested keys and extract 'value' field."""
        cur = d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        if isinstance(cur, dict) and "value" in cur:
            try:
                return float(cur["value"])
            except (ValueError, TypeError):
                return None
        return None

    def f_to_c(f: float | None) -> float | None:
        """Fahrenheit to Celsius."""
        return round((f - 32) * 5 / 9, 1) if f is not None else None

    def mph_to_kmh(mph: float | None) -> float | None:
        """Miles per hour to km/h."""
        return round(mph * 1.60934, 1) if mph is not None else None

    def in_to_mm(inches: float | None) -> float | None:
        """Inches to millimeters."""
        return round(inches * 25.4, 1) if inches is not None else None

    def inhg_to_hpa(inhg: float | None) -> float | None:
        """Inches of mercury to hectopascals."""
        return round(inhg * 33.8639, 1) if inhg is not None else None

    # Outdoor (temperatures in °F → °C)
    station_payload["outdoor"]["temperature"] = f_to_c(get_value(src, "outdoor", "temperature"))
    station_payload["outdoor"]["humidity"] = get_value(src, "outdoor", "humidity")
    station_payload["outdoor"]["feels_like"] = f_to_c(get_value(src, "outdoor", "feels_like"))
    station_payload["outdoor"]["dew_point"] = f_to_c(get_value(src, "outdoor", "dew_point"))

    # Wind (mph → km/h, direction in degrees stays as-is)
    station_payload["wind"]["speed"] = mph_to_kmh(get_value(src, "wind", "wind_speed"))
    station_payload["wind"]["gust"] = mph_to_kmh(get_value(src, "wind", "wind_gust"))
    station_payload["wind"]["direction"] = get_value(src, "wind", "wind_direction")

    # Rain (inches → mm)
    station_payload["rain"]["rate"] = in_to_mm(get_value(src, "rainfall", "rain_rate"))
    station_payload["rain"]["hourly"] = in_to_mm(get_value(src, "rainfall", "1_hour"))
    station_payload["rain"]["daily"] = in_to_mm(get_value(src, "rainfall", "daily"))
    station_payload["rain"]["monthly"] = in_to_mm(get_value(src, "rainfall", "monthly"))
    station_payload["rain"]["yearly"] = in_to_mm(get_value(src, "rainfall", "yearly"))

    # Solar / UV (W/m² stays as-is, UV index stays as-is)
    station_payload["solar"]["radiation"] = get_value(src, "solar_and_uvi", "solar")
    station_payload["solar"]["uv_index"] = get_value(src, "solar_and_uvi", "uvi")

    # Pressure (inHg → hPa)
    station_payload["pressure"]["relative"] = inhg_to_hpa(get_value(src, "pressure", "relative"))
    station_payload["pressure"]["absolute"] = inhg_to_hpa(get_value(src, "pressure", "absolute"))

    # Battery (console battery %)
    station_payload["battery"] = get_value(src, "battery", "ws6006_console")


def main() -> int:
    config = load_config()
    initialized = CONFIG_FILE.exists()

    app_key, api_key = read_secrets_keys()
    credentials_ok = bool(app_key and api_key)

    stations_cfg = (config.get("stations") or {}) if isinstance(config, dict) else {}
    stations_out: dict[str, dict] = {}

    # Build stable output
    for slot in VALID_SLOTS:
        cfg = stations_cfg.get(slot) if isinstance(stations_cfg, dict) else None
        if not isinstance(cfg, dict):
            cfg = {}
        st = base_station_payload(slot, cfg)

        configured = bool(st.get("name"))
        if configured and st["enabled"] and credentials_ok:
            ok, api_json = try_fetch_ecowitt(st, app_key, api_key)  # uses st["imei"]
            st["connected"] = bool(ok)
            if ok and isinstance(api_json, dict):
                map_ecowitt_to_station(st, api_json)
                st["updated"] = utc_now_iso()

        stations_out[slot] = st

    station_count = sum(1 for s in stations_out.values() if s.get("enabled") and s.get("name"))

    status = "ready"
    if not initialized:
        status = "not_initialized"
    elif not credentials_ok:
        status = "credentials_missing"

    payload = {
        "status": status,
        "initialized": initialized,
        "credentials_ok": credentials_ok,
        "version": VERSION,
        "station_count": station_count,
        "last_update": utc_now_iso(),
        "stations": stations_out,
    }

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
