"""
Breathe-Better — Flask application entry point.

Routes:
  GET /                                    → index.html (SPA shell)
  GET /api/geocode?q=<city>               → JSON list of matching locations
  GET /api/air-quality?lat=&lon=&city=    → JSON AQI + pollutants + recommendation

Security headers applied to every response:
  Content-Security-Policy, X-Content-Type-Options,
  X-Frame-Options, Referrer-Policy, Permissions-Policy

Caching:
  In-process dict with monotonic-clock TTL (600 s).
  No external cache dependency; suitable for a single-process deployment.
"""

from __future__ import annotations

import re
import time

from flask import Flask, abort, jsonify, render_template, request

from api import APIError, geocode, get_air_quality
from aqi import calculate_aqi, get_recommendation

app = Flask(__name__)


# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------
_cache: dict[str, dict] = {}
_CACHE_TTL: float = 600.0  # seconds


def _cache_get(key: str) -> tuple[dict | None, bool]:
    """Return (data, is_cached). Evicts stale entries."""
    entry = _cache.get(key)
    if entry is None:
        return None, False
    if time.monotonic() - entry["ts"] < _CACHE_TTL:
        return entry["data"], True
    del _cache[key]
    return None, False


def _cache_set(key: str, data: dict) -> None:
    _cache[key] = {"data": data, "ts": time.monotonic()}


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
@app.after_request
def add_security_headers(response):
    csp = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    return response


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
# Allow Unicode letters/digits, spaces, commas, hyphens, dots
_CITY_RE = re.compile(r"^[\w\s,.\-\u0080-\uFFFF]+$", re.UNICODE)


def _validate_city(raw: str) -> str:
    """Strip, truncate, and sanity-check a city name. Aborts on bad input."""
    city = raw.strip()[:100]
    if not city:
        abort(400, description="City name is required.")
    if not _CITY_RE.match(city):
        abort(400, description="City name contains invalid characters.")
    return city


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/geocode")
def api_geocode():
    q = request.args.get("q", "")
    if not q.strip():
        return jsonify({"error": "Query required"}), 400
    city = _validate_city(q)
    try:
        results = geocode(city)
        return jsonify(results)
    except APIError as exc:
        return jsonify({"error": str(exc)}), 503


@app.route("/api/air-quality")
def api_air_quality():
    raw_lat = request.args.get("lat", "")
    raw_lon = request.args.get("lon", "")
    city_name = request.args.get("city", "Unknown location")[:100].strip()

    if not raw_lat or not raw_lon:
        return jsonify({"error": "lat and lon parameters are required"}), 400

    try:
        lat = round(float(raw_lat), 6)
        lon = round(float(raw_lon), 6)
    except ValueError:
        return jsonify({"error": "Invalid coordinates — must be numeric"}), 400

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return jsonify({"error": "Coordinates are out of valid range"}), 400

    cache_key = f"{lat:.4f},{lon:.4f}"
    cached_data, is_cached = _cache_get(cache_key)
    if is_cached:
        # Return a copy so we don't mutate the cache entry
        payload = dict(cached_data)
        payload["cached"] = True
        return jsonify(payload)

    try:
        raw = get_air_quality(lat, lon)
    except APIError as exc:
        return jsonify({"error": str(exc)}), 503

    aqi_result = calculate_aqi(raw["current"])
    recommendation = get_recommendation(aqi_result["category"])

    result: dict = {
        "city": city_name,
        "lat": lat,
        "lon": lon,
        "current": raw["current"],
        "hourly": raw["hourly"],
        "aqi": aqi_result,
        "recommendation": recommendation,
        "cached": False,
        "timestamp": raw["timestamp"],
    }

    _cache_set(cache_key, result)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
