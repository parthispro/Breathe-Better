"""
CPCB (Central Pollution Control Board, India) AQI sub-index calculator.

Reference: National Air Quality Index — CPCB, 2014
  https://cpcb.nic.in/displaypdf.php?id=bmF0aW9uYWwtYWlyLXF1YWxpdHktaW5kZXg=

Concentration units expected by this module:
  pm2_5  → µg/m³  (24-hour average)
  pm10   → µg/m³  (24-hour average)
  no2    → µg/m³  (24-hour average)
  o3     → µg/m³  (8-hour average)
  co     → mg/m³  (8-hour average)   ← NOTE: api.py converts µg/m³ → mg/m³
  so2    → µg/m³  (24-hour average)
"""

from __future__ import annotations

_BREAKPOINTS: dict[str, list[tuple[float, float, int, int]]] = {
    "pm2_5": [
        (0.0,   30.0,   0,   50),
        (30.1,  60.0,  51,  100),
        (60.1,  90.0, 101,  200),
        (90.1, 120.0, 201,  300),
        (120.1, 250.0, 301, 400),
        (250.1, 500.0, 401, 500),
    ],
    "pm10": [
        (0,    50,   0,   50),
        (51,  100,  51,  100),
        (101, 250, 101,  200),
        (251, 350, 201,  300),
        (351, 430, 301,  400),
        (431, 600, 401,  500),
    ],
    "no2": [
        (0,    40,   0,   50),
        (41,   80,  51,  100),
        (81,  180, 101,  200),
        (181, 280, 201,  300),
        (281, 400, 301,  400),
        (401, 800, 401,  500),
    ],
    "o3": [
        (0,    50,   0,   50),
        (51,  100,  51,  100),
        (101, 168, 101,  200),
        (169, 208, 201,  300),
        (209, 748, 301,  400),
        (749, 1200, 401, 500),
    ],
    "co": [
        (0.0,   1.0,   0,   50),
        (1.1,   2.0,  51,  100),
        (2.1,  10.0, 101,  200),
        (10.1, 17.0, 201,  300),
        (17.1, 34.0, 301,  400),
        (34.1, 50.0, 401,  500),
    ],
    "so2": [
        (0,    40,   0,   50),
        (41,   80,  51,  100),
        (81,  380, 101,  200),
        (381, 800, 201,  300),
        (801, 1600, 301, 400),
        (1601, 2500, 401, 500),
    ],
}

_CATEGORIES: list[tuple[int, int, str, str]] = [
    (0,   50,  "Good",         "#00b050"),
    (51,  100, "Satisfactory", "#92d050"),
    (101, 200, "Moderate",     "#ffff00"),
    (201, 300, "Poor",         "#ff7c00"),
    (301, 400, "Very Poor",    "#ff0000"),
    (401, 500, "Severe",       "#7030a0"),
]

_RECOMMENDATIONS: dict[str, dict] = {
    "Good": {
        "headline": "Air quality is good",
        "detail": "Normal outdoor activities are safe for everyone.",
        "precautions": [
            "Enjoy outdoor activities freely.",
        ],
    },
    "Satisfactory": {
        "headline": "Air quality is satisfactory",
        "detail": "Generally safe for most people.",
        "precautions": [
            "Sensitive individuals may experience minor discomfort.",
            "Unusually sensitive people should consider reducing prolonged outdoor exertion.",
        ],
    },
    "Moderate": {
        "headline": "Air quality is moderate",
        "detail": "Sensitive groups should take precautions.",
        "precautions": [
            "People with respiratory or heart conditions should limit prolonged outdoor exertion.",
            "Children and the elderly should take care.",
            "Others may continue normal activities.",
        ],
    },
    "Poor": {
        "headline": "Air quality is poor",
        "detail": "Reduce prolonged outdoor exposure.",
        "precautions": [
            "Everyone should reduce prolonged or heavy outdoor exertion.",
            "People with respiratory or heart conditions should avoid outdoor exertion.",
            "Keep windows closed where possible.",
        ],
    },
    "Very Poor": {
        "headline": "Air quality is very poor",
        "detail": "Avoid prolonged outdoor activities.",
        "precautions": [
            "Everyone should avoid prolonged outdoor activities.",
            "People with respiratory or heart conditions should stay indoors.",
            "Use air purifiers if available.",
            "Wear N95 masks outdoors.",
        ],
    },
    "Severe": {
        "headline": "Air quality is severe",
        "detail": "Minimize outdoor exposure and follow official guidance.",
        "precautions": [
            "Avoid all outdoor activities.",
            "Stay indoors with windows and doors closed.",
            "Follow official health guidance and emergency alerts.",
            "Wear N95 masks if outdoor movement is essential.",
            "Seek medical attention if experiencing respiratory symptoms.",
        ],
    },
}


def sub_index(pollutant: str, concentration: float | None) -> float | None:
    """
    Calculate the CPCB AQI sub-index for a single pollutant using linear
    interpolation over the official breakpoint table.

    Args:
        pollutant:     One of: pm2_5, pm10, no2, o3, co, so2.
        concentration: Measured concentration in the pollutant's standard unit.
                       CO must be in mg/m³ (not µg/m³).

    Returns:
        Sub-index value (0.0–500.0), or None when:
          - concentration is None or negative
          - pollutant is not recognised
    """
    if concentration is None or concentration < 0:
        return None

    breakpoints = _BREAKPOINTS.get(pollutant)
    if breakpoints is None:
        return None

    for c_lo, c_hi, i_lo, i_hi in breakpoints:
        if c_lo <= concentration <= c_hi:
            return ((i_hi - i_lo) / (c_hi - c_lo)) * (concentration - c_lo) + i_lo

    if concentration > breakpoints[-1][1]:
        return 500.0

    return None


def calculate_aqi(measurements: dict) -> dict:
    """
    Calculate the overall CPCB AQI from a pollutant measurements dict.

    The overall AQI equals the maximum sub-index across all available
    pollutants. The pollutant producing that maximum is the dominant
    pollutant.

    Args:
        measurements: Keys are pollutant names; values are floats or None.
                      CO value must be in mg/m³.

    Returns:
        {
            "aqi":                int | None,
            "dominant_pollutant": str | None,
            "category":           str,
            "color":              str,  # hex
            "sub_indices":        dict[str, float],
        }
    """
    sub_indices: dict[str, float] = {}
    for pollutant in _BREAKPOINTS:
        conc = measurements.get(pollutant)
        si = sub_index(pollutant, conc)
        if si is not None:
            sub_indices[pollutant] = round(si, 1)

    if not sub_indices:
        return {
            "aqi": None,
            "dominant_pollutant": None,
            "category": "Unknown",
            "color": "#808080",
            "sub_indices": {},
        }

    dominant = max(sub_indices, key=lambda k: sub_indices[k])
    aqi_value = round(sub_indices[dominant])
    category, color = _get_category(aqi_value)

    return {
        "aqi": aqi_value,
        "dominant_pollutant": dominant,
        "category": category,
        "color": color,
        "sub_indices": sub_indices,
    }


def _get_category(aqi: int) -> tuple[str, str]:
    """Return (category_name, hex_color) for a given AQI value."""
    for lo, hi, cat, color in _CATEGORIES:
        if lo <= aqi <= hi:
            return cat, color
    return "Severe", "#7030a0"


def get_recommendation(category: str) -> dict:
    """
    Return the health recommendation dict for an AQI category string.

    Falls back to a generic 'data unavailable' message for unrecognised
    categories rather than raising an exception.
    """
    return _RECOMMENDATIONS.get(
        category,
        {
            "headline": "Air quality data unavailable",
            "detail": "Could not determine current air quality conditions.",
            "precautions": ["Check back later for updated data."],
        },
    )
