"""
Open-Meteo Air Quality API client.

Endpoints used (both free — no API key required):
  Geocoding:   https://geocoding-api.open-meteo.com/v1/search
  Air quality: https://air-quality-api.open-meteo.com/v1/air-quality

Unit note:
  Open-Meteo reports carbon_monoxide in µg/m³.
  CPCB AQI breakpoints for CO use mg/m³.
  This module divides CO by 1 000 before returning.

Python 3.15 async upgrade path (see requirements-py315.txt):
  Replace `requests` with `httpx.AsyncClient` and add `async`/`await`.
  The public function signatures stay identical; only the HTTP call changes.
"""

from __future__ import annotations

import time

import requests
from requests.exceptions import RequestException, Timeout

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
REQUEST_TIMEOUT = 8  # seconds

_HOURLY_VARS = [
    "pm10",
    "pm2_5",
    "nitrogen_dioxide",
    "ozone",
    "carbon_monoxide",
    "sulphur_dioxide",
]


class APIError(Exception):
    """Raised when an external API call fails for any reason."""


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def geocode(city: str) -> list[dict]:
    """
    Search Open-Meteo Geocoding API for cities matching *city*.

    Returns a list (possibly empty) of dicts with keys:
        name, country, admin1, latitude, longitude

    Raises:
        APIError: on timeout or any HTTP / network error.
    """
    try:
        response = requests.get(
            GEOCODE_URL,
            params={
                "name": city,
                "count": 6,
                "language": "en",
                "format": "json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except Timeout:
        raise APIError("Geocoding request timed out. Please try again.")
    except RequestException as exc:
        raise APIError(f"Geocoding request failed: {exc}") from exc

    results = data.get("results") or []
    return [
        {
            "name": r.get("name", ""),
            "country": r.get("country", ""),
            "admin1": r.get("admin1", ""),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
        }
        for r in results
        if r.get("latitude") is not None and r.get("longitude") is not None
    ]


# ---------------------------------------------------------------------------
# Air Quality
# ---------------------------------------------------------------------------

def get_air_quality(lat: float, lon: float) -> dict:
    """
    Fetch current and past-24-hour air quality measurements from Open-Meteo.

    Returns:
        {
            "current": {
                "pm2_5": float | None,   # µg/m³
                "pm10":  float | None,   # µg/m³
                "no2":   float | None,   # µg/m³
                "o3":    float | None,   # µg/m³
                "co":    float | None,   # mg/m³  ← converted from µg/m³
                "so2":   float | None,   # µg/m³
            },
            "hourly": {
                "time":  list[str],
                "pm2_5": list[float | None],
                ...
            },
            "timestamp": str,  # ISO-8601
        }

    Raises:
        APIError: on timeout or any HTTP / network error.
    """
    try:
        response = requests.get(
            AIR_QUALITY_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": ",".join(_HOURLY_VARS),
                "current": ",".join(_HOURLY_VARS),
                "timezone": "auto",
                "past_days": 1,
                "forecast_days": 0,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except Timeout:
        raise APIError("Air quality request timed out. Please try again.")
    except RequestException as exc:
        raise APIError(f"Air quality request failed: {exc}") from exc

    current_raw = data.get("current") or {}
    hourly_raw = data.get("hourly") or {}

    def _safe(val: object) -> float | None:
        return float(val) if isinstance(val, (int, float)) else None

    def _co_to_mg(val: object) -> float | None:
        """Convert CO from µg/m³ (Open-Meteo) to mg/m³ (CPCB)."""
        return float(val) / 1000.0 if isinstance(val, (int, float)) else None

    current = {
        "pm2_5": _safe(current_raw.get("pm2_5")),
        "pm10":  _safe(current_raw.get("pm10")),
        "no2":   _safe(current_raw.get("nitrogen_dioxide")),
        "o3":    _safe(current_raw.get("ozone")),
        "co":    _co_to_mg(current_raw.get("carbon_monoxide")),
        "so2":   _safe(current_raw.get("sulphur_dioxide")),
    }

    raw_co_hourly = hourly_raw.get("carbon_monoxide") or []
    hourly = {
        "time":  hourly_raw.get("time") or [],
        "pm2_5": hourly_raw.get("pm2_5") or [],
        "pm10":  hourly_raw.get("pm10") or [],
        "no2":   hourly_raw.get("nitrogen_dioxide") or [],
        "o3":    hourly_raw.get("ozone") or [],
        "co":    [_co_to_mg(v) for v in raw_co_hourly],
        "so2":   hourly_raw.get("sulphur_dioxide") or [],
    }

    # Keep only the most recent 24 hourly entries
    for key, values in hourly.items():
        if isinstance(values, list) and len(values) > 24:
            hourly[key] = values[-24:]

    timestamp = current_raw.get("time") or time.strftime("%Y-%m-%dT%H:%M")

    return {"current": current, "hourly": hourly, "timestamp": timestamp}
