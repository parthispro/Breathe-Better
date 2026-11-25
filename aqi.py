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

_AGE_GUIDANCE: dict[str, dict[str, list[str]]] = {
    "Good": {
        "overall": [
            "Air quality is safe for all age groups.",
            "Enjoy outdoor activities freely.",
        ],
        "infants_toddlers": [
            "Safe for stroller walks and outdoor play.",
            "Normal indoor ventilation is fine.",
        ],
        "kids_school": [
            "All outdoor PE and sports activities can proceed normally.",
            "No air-quality restrictions apply.",
        ],
        "teens": [
            "Outdoor training and sports are unrestricted.",
            "Follow standard hydration routines.",
        ],
        "seniors": [
            "Safe for normal outdoor walks and gardening.",
        ],
        "asthmatic": [
            "Favorable air quality — keep routine inhaler on hand.",
        ],
    },
    "Satisfactory": {
        "overall": [
            "Generally safe for most people.",
            "Unusually sensitive individuals may notice mild discomfort.",
        ],
        "infants_toddlers": [
            "Outdoor play is safe; bring child indoors if eye or throat irritation appears.",
            "Keep living spaces comfortably ventilated.",
        ],
        "kids_school": [
            "Outdoor PE and recess can proceed normally.",
            "Monitor children with known allergies or asthma during long exertion.",
        ],
        "teens": [
            "Outdoor sports and practices are fine.",
            "Ease intensity if coughing or throat dryness develops.",
        ],
        "seniors": [
            "Normal outdoor activity is fine.",
            "Sensitive seniors should avoid unusually long outdoor exertion.",
        ],
        "asthmatic": [
            "Generally safe — carry your reliever inhaler.",
            "Step indoors if wheezing or chest tightness begins.",
        ],
    },
    "Moderate": {
        "overall": [
            "Sensitive groups (children, seniors, asthmatics) should reduce prolonged outdoor exertion.",
            "Healthy adults may continue normal outdoor routines.",
        ],
        "infants_toddlers": [
            "Keep ages 0–4 indoors during peak traffic hours; limit walks to brief, calm outings.",
            "Keep windows closed along busy roads and focus on clean indoor air.",
        ],
        "kids_school": [
            "Shorten outdoor PE sessions to under 30 minutes and add indoor water breaks.",
            "Cancel prolonged outdoor assemblies when pollution rises.",
        ],
        "teens": [
            "Cut long outdoor cardio drills in half and move sprint intervals indoors.",
            "Stop exercise immediately if coughing, wheezing, or shortness of breath occurs.",
        ],
        "seniors": [
            "Avoid prolonged or strenuous outdoor exertion.",
            "Shift walks indoors or away from high-traffic corridors.",
        ],
        "asthmatic": [
            "Carry your reliever inhaler at all times.",
            "Move workouts indoors and monitor peak flow readings.",
        ],
    },
    "Poor": {
        "overall": [
            "Everyone should limit prolonged or heavy outdoor exertion.",
            "Children, seniors, and sensitive individuals should remain indoors.",
        ],
        "infants_toddlers": [
            "Avoid outdoor time for ages 0–4 — keep infants and toddlers indoors.",
            "Keep windows and doors shut and run a HEPA air purifier indoors if available.",
        ],
        "kids_school": [
            "Move all outdoor PE, sports practices, and recess indoors.",
            "Alert school nurses and parents of children with asthma or allergies.",
        ],
        "teens": [
            "Move all athletic training indoors and cancel outdoor endurance events.",
            "Wear a well-fitted N95 mask if commuting outdoors is unavoidable.",
        ],
        "seniors": [
            "Stay indoors and avoid outdoor physical exertion.",
            "Keep prescribed heart and respiratory medications accessible.",
        ],
        "asthmatic": [
            "Stay indoors with windows closed and air filtration running if available.",
            "Follow your asthma action plan and contact a doctor if symptoms worsen.",
        ],
    },
    "Very Poor": {
        "overall": [
            "Everyone should avoid prolonged outdoor activities.",
            "Keep indoor air sealed and filtered; use N95 protection outdoors.",
        ],
        "infants_toddlers": [
            "Keep ages 0–4 strictly indoors at all times.",
            "Seal window and door gaps and run an indoor HEPA purifier continuously.",
        ],
        "kids_school": [
            "Suspend all outdoor school activities and consider online classes where practical.",
            "Closely monitor students with asthma for early symptoms.",
        ],
        "teens": [
            "Cancel all outdoor practices, matches, and runs.",
            "Wear an N95 or FFP2 mask during essential outdoor transit.",
        ],
        "seniors": [
            "Remain indoors with windows sealed and filtration active.",
            "Seek medical advice promptly if breathing becomes labored.",
        ],
        "asthmatic": [
            "Stay indoors; wear a fitted N95 respirator only if leaving home is unavoidable.",
            "Keep rescue inhaler, nebulizer, and emergency contacts immediately accessible.",
        ],
    },
    "Severe": {
        "overall": [
            "Health emergency conditions — avoid all outdoor exposure.",
            "Follow local official health advisories and indoor shelter guidance.",
        ],
        "infants_toddlers": [
            "Keep children aged 0–4 strictly indoors with doors and windows sealed.",
            "Do not use face coverings on ages 0–4 due to suffocation risk; rely solely on clean filtered indoor air.",
            "Seek immediate medical care if rapid or labored breathing appears.",
        ],
        "kids_school": [
            "Transition classes online and halt all outdoor sports, assemblies, and commuting.",
            "Keep indoor classrooms sealed with filtered air if schools remain open.",
        ],
        "teens": [
            "Prohibit all outdoor sports and physical training.",
            "Wear a properly fitted N95 or FFP2 mask if any essential outdoor travel occurs.",
        ],
        "seniors": [
            "Remain indoors continuously unless seeking urgent care.",
            "Call emergency services immediately for chest pain or shortness of breath.",
        ],
        "asthmatic": [
            "Treat as a personal health emergency — remain strictly indoors with filtered air.",
            "Contact your physician promptly for any flare-up; keep rescue medications ready.",
        ],
    },
}

_COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

_US_EPA_CATEGORIES: list[tuple[int, str, str]] = [
    (50,  "Good",                           "#00e400"),
    (100, "Moderate",                       "#ffff00"),
    (150, "Unhealthy for Sensitive Groups", "#ff7e00"),
    (200, "Unhealthy",                      "#ff0000"),
    (300, "Very Unhealthy",                 "#8f3f97"),
]

_EU_EEA_CATEGORIES: list[tuple[int, str, str]] = [
    (20,  "Good",      "#50f0e6"),
    (40,  "Fair",      "#50ccaa"),
    (60,  "Moderate",  "#f0e641"),
    (80,  "Poor",      "#ff5050"),
    (100, "Very Poor", "#960032"),
]


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


def get_age_and_kids_guidance(category: str) -> dict[str, list[str]]:
    """
    Return age-segmented and sensitive-group guidance for a CPCB category.

    Keys returned: overall, infants_toddlers, kids_school, teens,
    seniors, asthmatic. Unknown categories return empty lists for all keys.
    """
    tiers = _AGE_GUIDANCE.get(category)
    if tiers is None:
        return {
            "overall": [],
            "infants_toddlers": [],
            "kids_school": [],
            "teens": [],
            "seniors": [],
            "asthmatic": [],
        }
    return {k: list(v) for k, v in tiers.items()}


def interpret_ventilation(
    wind_speed_ms: float | None,
    wind_dir_deg: float | None,
    boundary_layer_height_m: float | None,
) -> dict | None:
    """
    Compute the atmospheric Ventilation Coefficient and dispersion tier.

    VC = wind_speed_ms * boundary_layer_height_m  (m²/s)

    Tiers (IMD/IITD thresholds):
      < 3000    -> High Trapping Risk
      3000-5999 -> Moderate Dispersion
      >= 6000   -> Good Dispersion

    Returns None if any input is None or negative.
    """
    if wind_speed_ms is None or wind_dir_deg is None or boundary_layer_height_m is None:
        return None
    if wind_speed_ms < 0 or boundary_layer_height_m < 0:
        return None

    vc = round(wind_speed_ms * boundary_layer_height_m)
    compass_index = int(((wind_dir_deg % 360) + 22.5) / 45) % 8
    compass = _COMPASS[compass_index]

    if vc < 3000:
        tier = "High Trapping Risk"
        color = "#dc2626"
    elif vc < 6000:
        tier = "Moderate Dispersion"
        color = "#ca8a04"
    else:
        tier = "Good Dispersion"
        color = "#16a34a"

    return {
        "wind_speed_ms":           round(wind_speed_ms, 2),
        "wind_direction_deg":      round(wind_dir_deg, 1),
        "wind_direction_compass":  compass,
        "boundary_layer_height_m": round(boundary_layer_height_m, 1),
        "ventilation_coeff":       vc,
        "dispersion_tier":         tier,
        "dispersion_color":        color,
    }


def _lookup_open_ended(
    score: int | None,
    bands: list[tuple[int, str, str]],
    top_cat: str,
    top_color: str,
) -> tuple[str, str]:
    """Map an integer score across ascending upper bounds plus an open top tier."""
    if score is None or score < 0:
        return "Data unavailable", "#808080"
    for hi, cat, color in bands:
        if score <= hi:
            return cat, color
    return top_cat, top_color


def build_aqi_comparison(
    cpcb_result: dict,
    us_aqi: float | None,
    european_aqi: float | None,
) -> dict:
    """
    Build a 3-standard AQI transparency comparison card.

    Returns scores, categories, colors, explicit scale denominators, and an
    explanatory note for CPCB (0–500), US EPA (0–500+), and EU EEA (0–100+).
    """
    cpcb_score = cpcb_result.get("aqi")
    cpcb_cat   = cpcb_result.get("category", "Unknown")
    cpcb_color = cpcb_result.get("color", "#808080")

    us_score = round(us_aqi) if isinstance(us_aqi, (int, float)) else None
    us_cat, us_color = _lookup_open_ended(
        us_score, _US_EPA_CATEGORIES, "Hazardous", "#7e0023",
    )

    eu_score = round(european_aqi) if isinstance(european_aqi, (int, float)) else None
    eu_cat, eu_color = _lookup_open_ended(
        eu_score, _EU_EEA_CATEGORIES, "Extremely Poor", "#7d2181",
    )

    return {
        "cpcb": {
            "score":    cpcb_score,
            "category": cpcb_cat,
            "color":    cpcb_color,
            "scale":    "0–500",
        },
        "us_epa": {
            "score":    us_score,
            "category": us_cat,
            "color":    us_color,
            "scale":    "0–500+",
        },
        "eu_eea": {
            "score":    eu_score,
            "category": eu_cat,
            "color":    eu_color,
            "scale":    "0–100+",
        },
        "note": (
            "Each index weighs pollutants and averaging periods differently. "
            "CPCB India uses a 0–500 scale, US EPA uses 0–500+, and EU EEA uses a "
            "compressed 0–100+ scale — so identical air can show very different numbers."
        ),
    }
