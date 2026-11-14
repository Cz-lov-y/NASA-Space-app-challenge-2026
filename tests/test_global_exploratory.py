"""Protect the boundary between global descriptive trends and regional detection."""
import json
import unittest

import numpy as np
import pandas as pd

from examples.demo import make_synthetic_data
from src.global_exploratory import analyze_global_exploratory
from src.statistics import analyze_region


def global_data():
    frame = make_synthetic_data().assign(region_id="whole_earth")
    frame["variable"] = frame.variable.replace({"soil_moisture": "soil_water_0_10cm"})
    frame["quality_flag"] = "coverage_review_required"
    frame["valid_area_fraction"] = np.where(frame.variable == "NDVI", 0.17, 0.26)
    return frame


class GlobalExploratoryTests(unittest.TestCase):
    def test_opposite_significant_trends_never_become_a_green_mirage(self):
        frame = global_data()
        original = frame.copy(deep=True)
        raw = analyze_region(frame, soil_moisture_variable="soil_water_0_10cm")
        self.assertEqual(raw["divergence"]["category"], "Supported Signal")
        result = analyze_global_exploratory(frame)
        self.assertEqual(result["scope"], "global_exploratory")
        self.assertIsNone(result["divergence_detected"])
        self.assertEqual(result["divergence_status"], "not_assessed")
        self.assertEqual(result["divergence"]["category"], "Not assessed")
        self.assertEqual(result["divergence"]["pairs"], [])
        self.assertNotIn("Supported Signal", json.dumps(result))
        self.assertFalse(result["global_exploratory"]["green_mirage_assessed"])
        self.assertFalse(result["global_exploratory"]["quality_flags_applied"])
        self.assertEqual(result["trend_slopes"], raw["trend_slopes"])
        self.assertEqual(result["p_values"], raw["p_values"])
        self.assertTrue(result["data_quality"]["synthetic_demo"])
        self.assertEqual(result["global_exploratory"]["coverage_by_variable"]["NDVI"]["quality_flag_counts"], {"coverage_review_required": 192})
        json.dumps(result, allow_nan=False)
        pd.testing.assert_frame_equal(frame, original)

    def test_coverage_is_reported_without_implicitly_discarding_flags(self):
        frame = global_data()
        frame.loc[0, "quality_flag"] = "missing"
        frame.loc[0, "valid_area_fraction"] = np.nan
        result = analyze_global_exploratory(frame)
        summary = result["global_exploratory"]["coverage_by_variable"]["NDVI"]
        self.assertEqual(summary["quality_flag_counts"]["missing"], 1)
        self.assertEqual(summary["valid_area_fraction"]["unreported_count"], 1)
        self.assertEqual(summary["finite_value_rows"], 192)
        self.assertEqual(result["analysis"]["NDVI"]["data_quality"]["valid_observations"], 192)

    def test_missing_optional_coverage_and_nonoverlap_are_not_fabricated(self):
        frame = global_data().drop(columns=["quality_flag", "valid_area_fraction"])
        frame.loc[frame.variable == "soil_water_0_10cm", "date"] += pd.DateOffset(years=40)
        result = analyze_global_exploratory(frame)
        self.assertEqual(result["observation_period"]["years"], [])
        self.assertEqual(result["divergence_status"], "not_assessed")
        self.assertIsNone(result["global_exploratory"]["coverage_by_variable"]["NDVI"]["valid_area_fraction"])
        self.assertFalse(result["global_exploratory"]["coverage_by_variable"]["NDVI"]["quality_flag_column_present"])
        json.dumps(result, allow_nan=False)

    def test_regional_or_mixed_regions_are_rejected(self):
        for bad in (global_data().assign(region_id="central_us_sample"),
                    pd.concat([global_data(), global_data().iloc[:1].assign(region_id="other")]),
                    global_data().iloc[:0], global_data().drop(columns="region_id")):
            with self.subTest(rows=len(bad)), self.assertRaises(ValueError):
                analyze_global_exploratory(bad)

    def test_invalid_coverage_rejected(self):
        for value in (-0.01, 1.01, np.inf, "bad"):
            frame = global_data()
            frame["valid_area_fraction"] = frame["valid_area_fraction"].astype(object)
            frame.loc[0, "valid_area_fraction"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze_global_exploratory(frame)

    def test_soil_alias_is_configurable(self):
        frame = global_data().replace({"variable": {"soil_water_0_10cm": "soil_water_0_100cm"}})
        result = analyze_global_exploratory(frame, soil_moisture_variable="soil_water_0_100cm")
        self.assertIn("soil_water_0_100cm", result["variables"])
        self.assertEqual(result["divergence_status"], "not_assessed")


if __name__ == "__main__":
    unittest.main()
