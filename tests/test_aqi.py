"""
Unit tests for aqi.py — CPCB AQI sub-index calculations.

Run:
    python3 -m pytest tests/test_aqi.py -v --cov=aqi --cov-report=term-missing
"""

import typing
import unittest

from aqi import (
    _CATEGORIES,
    _get_category,
    build_aqi_comparison,
    calculate_aqi,
    get_age_and_kids_guidance,
    get_recommendation,
    interpret_ventilation,
    sub_index,
)


class TestSubIndex(unittest.TestCase):
    """sub_index() — CPCB linear interpolation."""

    # ── PM2.5 ──────────────────────────────────────────────
    def test_pm25_zero_is_zero(self):
        self.assertAlmostEqual(sub_index("pm2_5", 0), 0.0)

    def test_pm25_good_upper_boundary(self):
        self.assertAlmostEqual(sub_index("pm2_5", 30), 50.0, places=0)

    def test_pm25_satisfactory_range(self):
        result = sub_index("pm2_5", 45)
        self.assertGreater(result, 50)
        self.assertLessEqual(result, 100)

    def test_pm25_moderate_range(self):
        result = sub_index("pm2_5", 75)
        self.assertGreater(result, 100)
        self.assertLessEqual(result, 200)

    def test_pm25_poor_range(self):
        result = sub_index("pm2_5", 105)
        self.assertGreater(result, 200)
        self.assertLessEqual(result, 300)

    def test_pm25_very_poor_range(self):
        result = sub_index("pm2_5", 150)
        self.assertGreater(result, 300)
        self.assertLessEqual(result, 400)

    def test_pm25_severe_range(self):
        result = sub_index("pm2_5", 300)
        self.assertGreater(result, 400)
        self.assertLessEqual(result, 500)

    def test_pm25_above_max_capped_at_500(self):
        self.assertEqual(sub_index("pm2_5", 1000), 500.0)

    def test_pm25_none_returns_none(self):
        self.assertIsNone(sub_index("pm2_5", None))

    def test_pm25_negative_returns_none(self):
        self.assertIsNone(sub_index("pm2_5", -1.0))

    def test_pm25_zero_negative_edge(self):
        # Exactly 0 is valid; -0.001 is not
        self.assertIsNotNone(sub_index("pm2_5", 0.0))
        self.assertIsNone(sub_index("pm2_5", -0.001))

    # ── PM10 ───────────────────────────────────────────────
    def test_pm10_good(self):
        result = sub_index("pm10", 25)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 50)

    def test_pm10_satisfactory(self):
        result = sub_index("pm10", 75)
        self.assertGreater(result, 50)
        self.assertLessEqual(result, 100)

    # ── CO (mg/m³) ─────────────────────────────────────────
    def test_co_good(self):
        result = sub_index("co", 0.5)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 50)

    def test_co_moderate(self):
        result = sub_index("co", 5.0)
        self.assertGreater(result, 100)
        self.assertLessEqual(result, 200)

    def test_co_poor(self):
        result = sub_index("co", 13.0)
        self.assertGreater(result, 200)
        self.assertLessEqual(result, 300)

    # ── NO2 ────────────────────────────────────────────────
    def test_no2_good(self):
        self.assertLessEqual(sub_index("no2", 20), 50)

    def test_no2_poor(self):
        result = sub_index("no2", 230)
        self.assertGreater(result, 200)
        self.assertLessEqual(result, 300)

    # ── O3 ─────────────────────────────────────────────────
    def test_o3_good(self):
        self.assertLessEqual(sub_index("o3", 25), 50)

    def test_o3_moderate(self):
        result = sub_index("o3", 130)
        self.assertGreater(result, 100)
        self.assertLessEqual(result, 200)

    # ── SO2 ────────────────────────────────────────────────
    def test_so2_satisfactory(self):
        result = sub_index("so2", 60)
        self.assertGreater(result, 50)
        self.assertLessEqual(result, 100)

    # ── Unknown pollutant ──────────────────────────────────
    def test_unknown_pollutant_returns_none(self):
        self.assertIsNone(sub_index("mystery_gas", 100))

    def test_empty_pollutant_returns_none(self):
        self.assertIsNone(sub_index("", 50))


class TestCalculateAQI(unittest.TestCase):
    """calculate_aqi() — overall AQI from measurement dict."""

    def _good_measurements(self):
        return {"pm2_5": 10, "pm10": 20, "no2": 10, "o3": 20, "co": 0.3, "so2": 10}

    def test_all_good_gives_good_category(self):
        result = calculate_aqi(self._good_measurements())
        self.assertEqual(result["category"], "Good")
        self.assertLessEqual(result["aqi"], 50)

    def test_dominant_pollutant_is_highest_sub_index(self):
        m = {"pm2_5": 200, "pm10": 10, "no2": 10, "o3": 10, "co": 0.1, "so2": 10}
        result = calculate_aqi(m)
        self.assertEqual(result["dominant_pollutant"], "pm2_5")

    def test_severe_aqi_from_high_pm10(self):
        m = {"pm10": 500}
        result = calculate_aqi(m)
        self.assertGreaterEqual(result["aqi"], 400)

    def test_empty_dict_returns_unknown(self):
        result = calculate_aqi({})
        self.assertIsNone(result["aqi"])
        self.assertEqual(result["category"], "Unknown")

    def test_all_none_returns_unknown(self):
        m = {k: None for k in ("pm2_5", "pm10", "no2", "o3", "co", "so2")}
        result = calculate_aqi(m)
        self.assertIsNone(result["aqi"])

    def test_partial_data_uses_available_pollutants(self):
        result = calculate_aqi({"pm2_5": 50})
        self.assertIsNotNone(result["aqi"])
        self.assertIn("pm2_5", result["sub_indices"])

    def test_sub_indices_dict_returned(self):
        result = calculate_aqi({"pm2_5": 50, "pm10": 80})
        self.assertIn("pm2_5", result["sub_indices"])
        self.assertIn("pm10",  result["sub_indices"])

    def test_color_is_hex_string(self):
        result = calculate_aqi({"pm2_5": 10})
        self.assertTrue(result["color"].startswith("#"))
        self.assertEqual(len(result["color"]), 7)

    def test_aqi_is_integer(self):
        result = calculate_aqi(self._good_measurements())
        self.assertIsInstance(result["aqi"], int)

    def test_negative_concentration_ignored(self):
        # Negative values treated as unavailable → result driven by other pollutants
        result = calculate_aqi({"pm2_5": -5, "pm10": 30})
        self.assertIn("pm10",  result["sub_indices"])
        self.assertNotIn("pm2_5", result["sub_indices"])


class TestGetCategory(unittest.TestCase):
    """_get_category() — boundary conditions for all 6 bands."""

    def test_all_category_boundaries(self):
        for lo, hi, expected_cat, expected_color in _CATEGORIES:
            with self.subTest(aqi=lo):
                cat, color = _get_category(lo)
                self.assertEqual(cat,   expected_cat)
                self.assertEqual(color, expected_color)
            with self.subTest(aqi=hi):
                cat, color = _get_category(hi)
                self.assertEqual(cat,   expected_cat)
                self.assertEqual(color, expected_color)

    def test_above_500_returns_severe(self):
        cat, _ = _get_category(999)
        self.assertEqual(cat, "Severe")


class TestGetRecommendation(unittest.TestCase):
    """get_recommendation() — all categories and fallback."""

    KNOWN: typing.ClassVar[list[str]] = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]

    def test_all_known_categories_have_required_keys(self):
        for cat in self.KNOWN:
            with self.subTest(category=cat):
                rec = get_recommendation(cat)
                self.assertIn("headline",    rec)
                self.assertIn("detail",      rec)
                self.assertIn("precautions", rec)
                self.assertIsInstance(rec["precautions"], list)

    def test_all_known_categories_have_non_empty_precautions(self):
        for cat in self.KNOWN:
            with self.subTest(category=cat):
                rec = get_recommendation(cat)
                self.assertGreater(len(rec["precautions"]), 0)

    def test_severe_has_at_least_four_precautions(self):
        rec = get_recommendation("Severe")
        self.assertGreaterEqual(len(rec["precautions"]), 4)

    def test_good_headline_mentions_good(self):
        rec = get_recommendation("Good")
        self.assertIn("good", rec["headline"].lower())

    def test_unknown_category_returns_fallback(self):
        rec = get_recommendation("QuantumSmog")
        self.assertIn("headline",    rec)
        self.assertIn("precautions", rec)

    def test_empty_string_returns_fallback(self):
        rec = get_recommendation("")
        self.assertIn("headline", rec)
        self.assertIn("precautions", rec)


class TestGetAgeAndKidsGuidance(unittest.TestCase):
    """get_age_and_kids_guidance() — all categories, tiers, and 0–4 safety rules."""

    KNOWN: typing.ClassVar[list[str]] = [
        "Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe",
    ]
    TIERS: typing.ClassVar[list[str]] = [
        "overall", "infants_toddlers", "kids_school", "teens", "seniors", "asthmatic",
    ]

    def test_all_categories_and_tiers_non_empty(self):
        for cat in self.KNOWN:
            guidance = get_age_and_kids_guidance(cat)
            for tier in self.TIERS:
                with self.subTest(category=cat, tier=tier):
                    self.assertIn(tier, guidance)
                    self.assertIsInstance(guidance[tier], list)
                    self.assertGreater(len(guidance[tier]), 0)
                    for step in guidance[tier]:
                        self.assertIsInstance(step, str)
                        self.assertTrue(step.strip())

    def test_infants_toddlers_no_mask_policy(self):
        for cat in self.KNOWN:
            guidance = get_age_and_kids_guidance(cat)
            combined = " ".join(guidance["infants_toddlers"]).lower()
            with self.subTest(category=cat):
                self.assertNotIn("mask", combined)
                self.assertNotIn("n95", combined)

    def test_unknown_category_returns_empty_tiers(self):
        guidance = get_age_and_kids_guidance("UnknownBand")
        for tier in self.TIERS:
            self.assertEqual(guidance[tier], [])


class TestInterpretVentilation(unittest.TestCase):
    """interpret_ventilation() — VC math, thresholds, compass headings, None safety."""

    def test_none_inputs_return_none(self):
        self.assertIsNone(interpret_ventilation(None, 90.0, 500.0))
        self.assertIsNone(interpret_ventilation(3.0, None, 500.0))
        self.assertIsNone(interpret_ventilation(3.0, 90.0, None))

    def test_negative_inputs_return_none(self):
        self.assertIsNone(interpret_ventilation(-1.0, 90.0, 500.0))
        self.assertIsNone(interpret_ventilation(3.0, 90.0, -10.0))

    def test_high_trapping_risk_below_3000(self):
        res = interpret_ventilation(1.0, 0.0, 2999.0)
        self.assertIsNotNone(res)
        self.assertEqual(res["ventilation_coeff"], 2999)
        self.assertEqual(res["dispersion_tier"], "High Trapping Risk")
        self.assertEqual(res["dispersion_color"], "#dc2626")

    def test_moderate_dispersion_at_3000_and_5999(self):
        low = interpret_ventilation(3.0, 90.0, 1000.0)
        high = interpret_ventilation(1.0, 90.0, 5999.0)
        self.assertEqual(low["ventilation_coeff"], 3000)
        self.assertEqual(low["dispersion_tier"], "Moderate Dispersion")
        self.assertEqual(low["dispersion_color"], "#ca8a04")
        self.assertEqual(high["dispersion_tier"], "Moderate Dispersion")

    def test_good_dispersion_at_6000_plus(self):
        res = interpret_ventilation(4.0, 180.0, 1500.0)
        self.assertEqual(res["ventilation_coeff"], 6000)
        self.assertEqual(res["dispersion_tier"], "Good Dispersion")
        self.assertEqual(res["dispersion_color"], "#16a34a")

    def test_compass_directions(self):
        expected = [
            (0.0, "N"), (45.0, "NE"), (90.0, "E"), (135.0, "SE"),
            (180.0, "S"), (225.0, "SW"), (270.0, "W"), (315.0, "NW"), (359.0, "N"),
        ]
        for deg, compass in expected:
            with self.subTest(deg=deg):
                res = interpret_ventilation(2.0, deg, 1000.0)
                self.assertEqual(res["wind_direction_compass"], compass)


class TestBuildAQIComparison(unittest.TestCase):
    """build_aqi_comparison() — 3-standard scales, categories, open-ended bounds."""

    def test_returns_all_three_standards_and_scales(self):
        cpcb = {"aqi": 220, "category": "Poor", "color": "#ff7c00"}
        comp = build_aqi_comparison(cpcb, us_aqi=165.0, european_aqi=72.0)
        self.assertEqual(comp["cpcb"]["score"], 220)
        self.assertEqual(comp["cpcb"]["scale"], "0–500")
        self.assertEqual(comp["us_epa"]["score"], 165)
        self.assertEqual(comp["us_epa"]["category"], "Unhealthy")
        self.assertEqual(comp["us_epa"]["scale"], "0–500+")
        self.assertEqual(comp["eu_eea"]["score"], 72)
        self.assertEqual(comp["eu_eea"]["category"], "Poor")
        self.assertEqual(comp["eu_eea"]["scale"], "0–100+")
        self.assertTrue(comp["note"])

    def test_open_ended_upper_categories_above_1000(self):
        cpcb = {"aqi": 500, "category": "Severe", "color": "#7030a0"}
        comp = build_aqi_comparison(cpcb, us_aqi=1200.0, european_aqi=1100.0)
        self.assertEqual(comp["us_epa"]["category"], "Hazardous")
        self.assertEqual(comp["eu_eea"]["category"], "Extremely Poor")

    def test_none_external_scores_handled_gracefully(self):
        cpcb = {"aqi": 80, "category": "Satisfactory", "color": "#92d050"}
        comp = build_aqi_comparison(cpcb, us_aqi=None, european_aqi=None)
        self.assertIsNone(comp["us_epa"]["score"])
        self.assertEqual(comp["us_epa"]["category"], "Data unavailable")
        self.assertIsNone(comp["eu_eea"]["score"])
        self.assertEqual(comp["eu_eea"]["category"], "Data unavailable")


if __name__ == "__main__":
    unittest.main()
