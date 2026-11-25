"""
Breathe-Better — Flask application entry point.

Routes:
  GET /                                    -> index.html (SPA shell)
  GET /api/geocode?q=<city>               -> JSON list of matching locations
  GET /api/air-quality?lat=&lon=&city=    -> JSON AQI + pollutants + guidance + ventilation + comparator
  GET /api/compare?coords=&cities=        -> JSON multi-city batch AQI comparison

Security headers applied to every response:
  Content-Security-Policy, X-Content-Type-Options,
  X-Frame-Options, Referrer-Policy, Permissions-Policy

Caching:
  Bounded OrderedDict (max 200 entries) with monotonic-clock TTL (600 s).
"""

from __future__ import annotations

import concurrent.futures
import re
import time
from collections import OrderedDict

from flask import Flask, abort, jsonify, render_template, request

from api import (
    APIError,
    geocode,
    get_air_quality,
    get_air_quality_batch,
    get_ventilation,
)
from aqi import (
    build_aqi_comparison,
    calculate_aqi,
    get_age_and_kids_guidance,
    get_recommendation,
    interpret_ventilation,
)

app = Flask(__name__)

_cache: OrderedDict[str, dict] = OrderedDict()
_CACHE_TTL: float = 600.0
_MAX_CACHE_ENTRIES: int = 200


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
    if key in _cache:
        _cache.move_to_end(key)
    elif len(_cache) >= _MAX_CACHE_ENTRIES:
        _cache.popitem(last=False)
    _cache[key] = {"data": data, "ts": time.monotonic()}


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


_CITY_RE = re.compile(r"^[\w\s,.\-\u0080-\uFFFF]+$", re.UNICODE)


def _validate_city(raw: str) -> str:
    """Strip, truncate, and sanity-check a city name. Aborts on bad input."""
    city = raw.strip()[:100]
    if not city:
        abort(400, description="City name is required.")
    if not _CITY_RE.match(city):
        abort(400, description="City name contains invalid characters.")
    return city


def _parse_lat_lon(raw_lat: str, raw_lon: str) -> tuple[float, float] | None:
    """Parse and range-check coordinate pair; return None if invalid."""
    try:
        lat = round(float(raw_lat), 6)
        lon = round(float(raw_lon), 6)
    except ValueError:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


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
    raw_lat   = request.args.get("lat", "")
    raw_lon   = request.args.get("lon", "")
    city_name = request.args.get("city", "Unknown location")[:100].strip()

    if not raw_lat or not raw_lon:
        return jsonify({"error": "lat and lon parameters are required"}), 400

    parsed = _parse_lat_lon(raw_lat, raw_lon)
    if parsed is None:
        return jsonify({"error": "Invalid or out-of-range coordinates"}), 400
    lat, lon = parsed

    cache_key = f"{lat:.4f},{lon:.4f}"
    cached_data, is_cached = _cache_get(cache_key)
    if is_cached:
        payload = dict(cached_data)
        payload["cached"] = True
        return jsonify(payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        aq_future = executor.submit(get_air_quality, lat, lon)
        wx_future = executor.submit(get_ventilation, lat, lon)

    try:
        raw = aq_future.result()
    except APIError as exc:
        return jsonify({"error": str(exc)}), 503

    try:
        wx_raw = wx_future.result()
        ventilation = interpret_ventilation(
            wx_raw.get("wind_speed_ms"),
            wx_raw.get("wind_direction_deg"),
            wx_raw.get("boundary_layer_height_m"),
        )
    except (APIError, ValueError, TypeError, KeyError):
        ventilation = None

    aqi_result     = calculate_aqi(raw["current"])
    recommendation = get_recommendation(aqi_result["category"])
    age_guidance   = get_age_and_kids_guidance(aqi_result["category"])
    ext            = raw.get("external_indices", {})
    comparison     = build_aqi_comparison(
        aqi_result,
        ext.get("us_aqi"),
        ext.get("european_aqi"),
    )

    result: dict = {
        "city":           city_name,
        "lat":            lat,
        "lon":            lon,
        "current":        raw["current"],
        "hourly":         raw["hourly"],
        "aqi":            aqi_result,
        "recommendation": recommendation,
        "age_guidance":   age_guidance,
        "comparison":     comparison,
        "ventilation":    ventilation,
        "cached":         False,
        "timestamp":      raw["timestamp"],
    }

    _cache_set(cache_key, result)
    return jsonify(result)


@app.route("/api/compare")
def api_compare():
    raw_coords = request.args.get("coords", "").strip()
    raw_cities = request.args.get("cities", "").strip()

    if not raw_coords:
        return jsonify({"error": "coords parameter is required"}), 400

    pairs_raw = [p.strip() for p in raw_coords.split(";") if p.strip()]
    if len(pairs_raw) < 2 or len(pairs_raw) > 4:
        return jsonify({"error": "Provide between 2 and 4 coordinate pairs"}), 400

    coords: list[tuple[float, float]] = []
    for pair in pairs_raw:
        parts = pair.split(",")
        if len(parts) != 2:
            return jsonify({"error": f"Invalid coordinate pair: {pair}"}), 400
        parsed = _parse_lat_lon(parts[0].strip(), parts[1].strip())
        if parsed is None:
            return jsonify({"error": f"Invalid or out-of-range coordinates: {pair}"}), 400
        coords.append(parsed)

    city_names = [c.strip()[:100] for c in raw_cities.split("|")] if raw_cities else []
    while len(city_names) < len(coords):
        city_names.append(f"City {len(city_names) + 1}")

    items: list[dict | None] = [None] * len(coords)
    uncached: list[tuple[int, tuple[float, float]]] = []

    for idx, (lat, lon) in enumerate(coords):
        cached_item, hit = _cache_get(f"cmp:{lat:.4f},{lon:.4f}")
        if hit and cached_item is not None:
            copy_item = dict(cached_item)
            copy_item["city"] = city_names[idx] or copy_item.get("city", "")
            items[idx] = copy_item
        else:
            uncached.append((idx, (lat, lon)))

    if uncached:
        try:
            batch = get_air_quality_batch([coord for _, coord in uncached])
        except APIError as exc:
            return jsonify({"error": str(exc)}), 503

        for batch_i, (orig_idx, (lat, lon)) in enumerate(uncached):
            if batch_i >= len(batch):
                continue
            r = batch[batch_i]
            aqi_result = calculate_aqi(r["current"])
            ext        = r.get("external_indices", {})
            comparison = build_aqi_comparison(
                aqi_result,
                ext.get("us_aqi"),
                ext.get("european_aqi"),
            )
            entry = {
                "city":       city_names[orig_idx],
                "lat":        r["lat"],
                "lon":        r["lon"],
                "grid_lat":   r["grid_lat"],
                "grid_lon":   r["grid_lon"],
                "current":    r["current"],
                "aqi":        aqi_result,
                "comparison": comparison,
                "timestamp":  r["timestamp"],
            }
            _cache_set(f"cmp:{lat:.4f},{lon:.4f}", entry)
            items[orig_idx] = entry

    resolved = [it for it in items if it is not None]
    valid_cells = [
        (round(it["grid_lat"], 2), round(it["grid_lon"], 2))
        for it in resolved
        if it.get("grid_lat") is not None and it.get("grid_lon") is not None
    ]
    shared_grid_warning = len(set(valid_cells)) < len(valid_cells)

    return jsonify({
        "cities":              resolved,
        "shared_grid_warning": shared_grid_warning,
    })


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
