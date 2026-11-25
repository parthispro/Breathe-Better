"""
Open-Meteo Air Quality and Weather Forecast API client.

Endpoints used (all free — no API key required):
  Geocoding:   https://geocoding-api.open-meteo.com/v1/search
  Air quality: https://air-quality-api.open-meteo.com/v1/air-quality
  Forecast:    https://api.open-meteo.com/v1/forecast

Unit notes:
  Open-Meteo reports carbon_monoxide in µg/m³.
  CPCB AQI breakpoints for CO use mg/m³.
  This module divides CO by 1 000 before returning.
  wind_speed_10m defaults to km/h; wind_speed_unit=ms requests m/s directly.

Python 3.15 async upgrade path (see requirements-py315.txt):
  Replace `requests` with `httpx.AsyncClient` and add `async`/`await`.
  The public function signatures stay identical; only the HTTP call changes.
"""

from __future__ import annotations

import time

import requests
from requests.exceptions import RequestException, Timeout

GEOCODE_URL      = "https://geocoding-api.open-meteo.com/v1/search"
AIR_QUALITY_URL  = "https://air-quality-api.open-meteo.com/v1/air-quality"
FORECAST_URL     = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT  = 8  # seconds
FORECAST_TIMEOUT = 4  # strict cap because ventilation runs alongside air quality

_HOURLY_VARS = [
    "pm10",
    "pm2_5",
    "nitrogen_dioxide",
    "ozone",
    "carbon_monoxide",
    "sulphur_dioxide",
]

_CURRENT_EXTRA = ["us_aqi", "european_aqi"]


class APIError(Exception):
    """Raised when an external API call fails for any reason."""


def _safe(val: object) -> float | None:
    return float(val) if isinstance(val, (int, float)) else None


def _co_to_mg(val: object) -> float | None:
    """Convert CO from µg/m³ (Open-Meteo) to mg/m³ (CPCB)."""
    return float(val) / 1000.0 if isinstance(val, (int, float)) else None


def _parse_current(current_raw: dict) -> dict[str, float | None]:
    """Normalize Open-Meteo current pollutant keys into CPCB-unit short keys."""
    return {
        "pm2_5": _safe(current_raw.get("pm2_5")),
        "pm10":  _safe(current_raw.get("pm10")),
        "no2":   _safe(current_raw.get("nitrogen_dioxide")),
        "o3":    _safe(current_raw.get("ozone")),
        "co":    _co_to_mg(current_raw.get("carbon_monoxide")),
        "so2":   _safe(current_raw.get("sulphur_dioxide")),
    }


def _parse_external_indices(current_raw: dict) -> dict[str, float | None]:
    """Extract US EPA and EU EEA AQI values from an Open-Meteo current block."""
    return {
        "us_aqi":       _safe(current_raw.get("us_aqi")),
        "european_aqi": _safe(current_raw.get("european_aqi")),
    }


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
            "name":      r.get("name", ""),
            "country":   r.get("country", ""),
            "admin1":    r.get("admin1", ""),
            "latitude":  r.get("latitude"),
            "longitude": r.get("longitude"),
        }
        for r in results
        if r.get("latitude") is not None and r.get("longitude") is not None
    ]


def get_air_quality(lat: float, lon: float) -> dict:
    """
    Fetch current, external AQI indices, and past-24-hour air quality from Open-Meteo.

    Raises:
        APIError: on timeout or any HTTP / network error.
    """
    try:
        response = requests.get(
            AIR_QUALITY_URL,
            params={
                "latitude":      lat,
                "longitude":     lon,
                "hourly":        ",".join(_HOURLY_VARS),
                "current":       ",".join(_HOURLY_VARS + _CURRENT_EXTRA),
                "timezone":      "auto",
                "past_days":     1,
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
    hourly_raw  = data.get("hourly")  or {}

    current = _parse_current(current_raw)
    external_indices = _parse_external_indices(current_raw)

    raw_co_hourly = hourly_raw.get("carbon_monoxide") or []
    hourly = {
        "time":  hourly_raw.get("time")             or [],
        "pm2_5": hourly_raw.get("pm2_5")            or [],
        "pm10":  hourly_raw.get("pm10")             or [],
        "no2":   hourly_raw.get("nitrogen_dioxide") or [],
        "o3":    hourly_raw.get("ozone")            or [],
        "co":    [_co_to_mg(v) for v in raw_co_hourly],
        "so2":   hourly_raw.get("sulphur_dioxide")  or [],
    }

    for key, values in hourly.items():
        if isinstance(values, list) and len(values) > 24:
            hourly[key] = values[-24:]

    timestamp = current_raw.get("time") or time.strftime("%Y-%m-%dT%H:%M")

    return {
        "current":          current,
        "hourly":           hourly,
        "external_indices": external_indices,
        "timestamp":        timestamp,
    }


def get_ventilation(lat: float, lon: float) -> dict:
    """
    Fetch current wind speed (m/s), wind direction (deg), and boundary layer
    height (m) from Open-Meteo Forecast API with a strict 4-second timeout.

    Raises:
        APIError: on timeout or any HTTP / network error.
    """
    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "latitude":        lat,
                "longitude":       lon,
                "current":         "wind_speed_10m,wind_direction_10m,boundary_layer_height",
                "wind_speed_unit": "ms",
                "timezone":        "auto",
                "forecast_days":   1,
            },
            timeout=FORECAST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except Timeout:
        raise APIError("Forecast ventilation request timed out.")
    except RequestException as exc:
        raise APIError(f"Forecast ventilation request failed: {exc}") from exc

    cur = data.get("current") or {}
    return {
        "wind_speed_ms":           _safe(cur.get("wind_speed_10m")),
        "wind_direction_deg":      _safe(cur.get("wind_direction_10m")),
        "boundary_layer_height_m": _safe(cur.get("boundary_layer_height")),
    }


def get_air_quality_batch(coords: list[tuple[float, float]]) -> list[dict]:
    """
    Batch-fetch current air quality for 1–4 coordinate pairs in a single HTTP call.

    Open-Meteo returns a dict for 1 coordinate and a JSON list for 2+ coordinates;
    this function normalizes both to a list.

    Raises:
        APIError: on timeout or any HTTP / network error.
    """
    if not coords:
        return []

    lats = ",".join(str(c[0]) for c in coords)
    lons = ",".join(str(c[1]) for c in coords)

    try:
        response = requests.get(
            AIR_QUALITY_URL,
            params={
                "latitude":  lats,
                "longitude": lons,
                "current":   ",".join(_HOURLY_VARS + _CURRENT_EXTRA),
                "timezone":  "auto",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except Timeout:
        raise APIError("Batch air quality request timed out.")
    except RequestException as exc:
        raise APIError(f"Batch air quality request failed: {exc}") from exc

    results = [data] if isinstance(data, dict) else data
    output: list[dict] = []

    for i, r in enumerate(results):
        req_lat, req_lon = coords[i] if i < len(coords) else (None, None)
        cur_raw = r.get("current") or {}
        output.append({
            "lat":              req_lat,
            "lon":              req_lon,
            "grid_lat":         _safe(r.get("latitude")),
            "grid_lon":         _safe(r.get("longitude")),
            "current":          _parse_current(cur_raw),
            "external_indices": _parse_external_indices(cur_raw),
            "timestamp":        cur_raw.get("time") or time.strftime("%Y-%m-%dT%H:%M"),
        })

    return output
