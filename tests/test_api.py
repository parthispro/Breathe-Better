"""
Integration tests for api.py using unittest.mock.

Run:
    python3 -m pytest tests/test_api.py -v --cov=api --cov-report=term-missing
"""

import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import ConnectionError, RequestException, Timeout

from api import APIError, geocode, get_air_quality


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        from requests.exceptions import HTTPError
        mock.raise_for_status.side_effect = HTTPError(response=mock)
    return mock


def _standard_air_quality_payload() -> dict:
    return {
        "current": {
            "pm2_5":             55.2,
            "pm10":              90.5,
            "nitrogen_dioxide":  35.0,
            "ozone":             80.0,
            "carbon_monoxide":   400.0,   # µg/m³ — expect division by 1000
            "sulphur_dioxide":   20.0,
            "time":              "2024-01-15T14:00",
        },
        "hourly": {
            "time":               ["2024-01-15T00:00"] * 24,
            "pm2_5":              [50.0] * 24,
            "pm10":               [80.0] * 24,
            "nitrogen_dioxide":   [30.0] * 24,
            "ozone":              [75.0] * 24,
            "carbon_monoxide":    [400.0] * 24,
            "sulphur_dioxide":    [15.0] * 24,
        },
    }


# ---------------------------------------------------------------------------
# Geocode tests
# ---------------------------------------------------------------------------
class TestGeocode(unittest.TestCase):

    @patch("api.requests.get")
    def test_returns_structured_results(self, mock_get):
        mock_get.return_value = _mock_response({
            "results": [
                {
                    "name": "Delhi", "country": "India", "admin1": "Delhi",
                    "latitude": 28.65, "longitude": 77.23,
                }
            ]
        })
        result = geocode("Delhi")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"],      "Delhi")
        self.assertEqual(result[0]["country"],   "India")
        self.assertEqual(result[0]["latitude"],  28.65)
        self.assertEqual(result[0]["longitude"], 77.23)

    @patch("api.requests.get")
    def test_multiple_results_returned(self, mock_get):
        mock_get.return_value = _mock_response({
            "results": [
                {"name": "London", "country": "UK", "admin1": "England",
                 "latitude": 51.5, "longitude": -0.12},
                {"name": "London", "country": "Canada", "admin1": "Ontario",
                 "latitude": 42.98, "longitude": -81.24},
            ]
        })
        result = geocode("London")
        self.assertEqual(len(result), 2)

    @patch("api.requests.get")
    def test_empty_results_key_returns_empty_list(self, mock_get):
        mock_get.return_value = _mock_response({})
        result = geocode("xyznonexistent")
        self.assertEqual(result, [])

    @patch("api.requests.get")
    def test_null_results_key_returns_empty_list(self, mock_get):
        mock_get.return_value = _mock_response({"results": None})
        result = geocode("xyznonexistent")
        self.assertEqual(result, [])

    @patch("api.requests.get")
    def test_filters_entries_with_missing_latitude(self, mock_get):
        mock_get.return_value = _mock_response({
            "results": [
                {"name": "CityA", "latitude": None,  "longitude": 10.0},
                {"name": "CityB", "latitude": 10.0,  "longitude": 20.0},
                {"name": "CityC", "latitude": 15.0,  "longitude": None},
            ]
        })
        result = geocode("City")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "CityB")

    @patch("api.requests.get")
    def test_timeout_raises_api_error(self, mock_get):
        mock_get.side_effect = Timeout()
        with self.assertRaises(APIError) as ctx:
            geocode("Delhi")
        self.assertIn("timed out", str(ctx.exception).lower())

    @patch("api.requests.get")
    def test_connection_error_raises_api_error(self, mock_get):
        mock_get.side_effect = ConnectionError("No route to host")
        with self.assertRaises(APIError):
            geocode("Mumbai")

    @patch("api.requests.get")
    def test_generic_request_exception_raises_api_error(self, mock_get):
        mock_get.side_effect = RequestException("Something broke")
        with self.assertRaises(APIError):
            geocode("Chennai")

    @patch("api.requests.get")
    def test_correct_query_params_sent(self, mock_get):
        mock_get.return_value = _mock_response({"results": []})
        geocode("Kolkata")
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})
        self.assertEqual(params["name"], "Kolkata")
        self.assertEqual(params["language"], "en")


# ---------------------------------------------------------------------------
# get_air_quality tests
# ---------------------------------------------------------------------------
class TestGetAirQuality(unittest.TestCase):

    @patch("api.requests.get")
    def test_parses_current_values(self, mock_get):
        mock_get.return_value = _mock_response(_standard_air_quality_payload())
        result = get_air_quality(28.65, 77.23)
        self.assertAlmostEqual(result["current"]["pm2_5"], 55.2)
        self.assertAlmostEqual(result["current"]["pm10"],  90.5)
        self.assertAlmostEqual(result["current"]["no2"],   35.0)
        self.assertAlmostEqual(result["current"]["o3"],    80.0)
        self.assertAlmostEqual(result["current"]["so2"],   20.0)

    @patch("api.requests.get")
    def test_co_converted_from_ug_to_mg(self, mock_get):
        mock_get.return_value = _mock_response(_standard_air_quality_payload())
        result = get_air_quality(28.65, 77.23)
        # 400 µg/m³ ÷ 1000 = 0.4 mg/m³
        self.assertAlmostEqual(result["current"]["co"], 0.4, places=4)

    @patch("api.requests.get")
    def test_hourly_co_also_converted(self, mock_get):
        mock_get.return_value = _mock_response(_standard_air_quality_payload())
        result = get_air_quality(28.65, 77.23)
        for co_val in result["hourly"]["co"]:
            if co_val is not None:
                self.assertAlmostEqual(co_val, 0.4, places=4)

    @patch("api.requests.get")
    def test_hourly_trimmed_to_last_24(self, mock_get):
        payload = _standard_air_quality_payload()
        # Provide 48 hourly entries
        for key in payload["hourly"]:
            payload["hourly"][key] = payload["hourly"][key] * 2
        mock_get.return_value = _mock_response(payload)
        result = get_air_quality(28.65, 77.23)
        for key in ("time", "pm2_5", "pm10", "no2", "o3", "co", "so2"):
            self.assertLessEqual(len(result["hourly"][key]), 24, msg=f"key={key}")

    @patch("api.requests.get")
    def test_timestamp_returned(self, mock_get):
        mock_get.return_value = _mock_response(_standard_air_quality_payload())
        result = get_air_quality(28.65, 77.23)
        self.assertEqual(result["timestamp"], "2024-01-15T14:00")

    @patch("api.requests.get")
    def test_timeout_raises_api_error(self, mock_get):
        mock_get.side_effect = Timeout()
        with self.assertRaises(APIError) as ctx:
            get_air_quality(28.65, 77.23)
        self.assertIn("timed out", str(ctx.exception).lower())

    @patch("api.requests.get")
    def test_request_exception_raises_api_error(self, mock_get):
        mock_get.side_effect = RequestException("Connection refused")
        with self.assertRaises(APIError):
            get_air_quality(0.0, 0.0)

    @patch("api.requests.get")
    def test_none_values_in_current_returned_as_none(self, mock_get):
        payload = {
            "current": {
                "pm2_5": None, "pm10": 90.5,
                "nitrogen_dioxide": None, "ozone": None,
                "carbon_monoxide": None, "sulphur_dioxide": None,
                "time": "2024-01-15T14:00",
            },
            "hourly": {k: [] for k in
                       ("time", "pm2_5", "pm10", "nitrogen_dioxide",
                        "ozone", "carbon_monoxide", "sulphur_dioxide")},
        }
        mock_get.return_value = _mock_response(payload)
        result = get_air_quality(0.0, 0.0)
        self.assertIsNone(result["current"]["pm2_5"])
        self.assertIsNone(result["current"]["co"])
        self.assertAlmostEqual(result["current"]["pm10"], 90.5)

    @patch("api.requests.get")
    def test_missing_current_key_handled_gracefully(self, mock_get):
        mock_get.return_value = _mock_response({
            "hourly": {k: [] for k in
                       ("time", "pm2_5", "pm10", "nitrogen_dioxide",
                        "ozone", "carbon_monoxide", "sulphur_dioxide")},
        })
        # Should not raise; current values will be None
        result = get_air_quality(0.0, 0.0)
        self.assertIsNone(result["current"]["pm2_5"])

    @patch("api.requests.get")
    def test_correct_coordinates_sent(self, mock_get):
        mock_get.return_value = _mock_response(_standard_air_quality_payload())
        get_air_quality(28.6500, 77.2300)
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})
        self.assertAlmostEqual(float(params["latitude"]),  28.65, places=2)
        self.assertAlmostEqual(float(params["longitude"]), 77.23, places=2)


if __name__ == "__main__":
    unittest.main()
