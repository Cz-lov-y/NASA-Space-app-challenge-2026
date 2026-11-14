"""Deterministic synthetic cases, not NASA observations."""

import json
import math
import unittest

import numpy as np
import pandas as pd

from src.statistics import (adjust_p_values, analyze_region, analyze_timeseries,
                            estimate_trend, linear_regression, mann_kendall, theil_sen)


def series(values, start=2000):
    return pd.DataFrame({"date": pd.date_range(f"{start}-01-01", periods=len(values), freq="YS"),
                         "value": values})


def region(green=None, water=None, water_start=2000):
    if green is None:
        green = 0.2 + np.arange(16) * 0.01
    if water is None:
        water = 30 - np.arange(16) * 0.5
    frames = []
    for variable, values, start, unit in [("NDVI", green, 2000, "1"),
                                          ("soil_moisture", water, water_start, "kg m-2")]:
        frame = series(values, start)
        frame = frame.assign(variable=variable, unit=unit, source="SYNTHETIC_TEST_ONLY", region_id="demo")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


class TrendTests(unittest.TestCase):
    def test_alpha_range_is_consistent_across_public_entry_points(self):
        from src.divergence import detect_divergence
        x, y = np.arange(10), np.arange(10)
        calls = [lambda a: linear_regression(x, y, a), lambda a: theil_sen(x, y, a),
                 lambda a: mann_kendall(y, a), lambda a: analyze_timeseries(series(y), frequency="annual", alpha=a),
                 lambda a: analyze_region(region(), frequency="annual", alpha=a),
                 lambda a: detect_divergence({}, alpha=a)]
        for call in calls:
            for alpha in (0, -0.1, 0.5, 1, np.nan, np.inf):
                with self.subTest(alpha=alpha, call=call), self.assertRaisesRegex(ValueError, "0 and 0.5"):
                    call(alpha)
            call(0.499)

    def test_known_line_and_time_origin(self):
        x = np.array([2000, 2001, 2003, 2007, 2010])
        y = 4 + 2 * (x - 2000)
        for function in (linear_regression, theil_sen):
            fit = function(x, y)
            self.assertAlmostEqual(fit["slope"], 2)
            self.assertAlmostEqual(fit["intercept"], 4)
            self.assertEqual(fit["time_origin"], 2000)
            self.assertAlmostEqual(fit["confidence_interval"][0], 2)
            self.assertAlmostEqual(fit["confidence_interval"][1], 2)

    def test_ols_hand_calculation(self):
        fit = linear_regression([0, 1, 2, 3, 4], [1, 2, 1, 4, 2])
        self.assertAlmostEqual(fit["slope"], 0.4)
        self.assertAlmostEqual(fit["intercept"], 1.2)
        self.assertAlmostEqual(fit["standard_error"], np.sqrt(4.4 / 3 / 10))
        self.assertLess(fit["confidence_interval"][0], 0)
        self.assertGreater(fit["confidence_interval"][1], 0)

    def test_theil_sen_resists_outlier(self):
        x = np.arange(15)
        y = 2.0 * x
        y[-1] += 1000
        self.assertEqual(theil_sen(x, y)["slope"], 2)
        self.assertGreater(linear_regression(x, y)["slope"], 20)

    def test_mk_known_monotonic(self):
        result = mann_kendall(range(10))
        self.assertEqual(result["s"], 45)
        self.assertAlmostEqual(result["variance"], 125)
        self.assertAlmostEqual(result["z"], 44 / np.sqrt(125))
        self.assertAlmostEqual(result["p_value"], math.erfc(44 / np.sqrt(250)), places=14)
        self.assertEqual(result["direction"], "increasing")
        self.assertEqual(mann_kendall(range(10, 0, -1))["direction"], "decreasing")

    def test_mk_tie_correction(self):
        result = mann_kendall([1, 1, 2, 2, 3])
        self.assertEqual(result["s"], 8)
        self.assertAlmostEqual(result["variance"], 44 / 3)
        self.assertAlmostEqual(result["z"], 7 / np.sqrt(44 / 3))

    def test_constant_series(self):
        result = analyze_timeseries(series([3] * 12), frequency="annual")
        self.assertEqual(result["mann_kendall"]["p_value"], 1)
        self.assertEqual(result["linear_regression"]["p_value"], 1)
        self.assertEqual(result["theil_sen"]["confidence_interval"], [0, 0])
        json.dumps(result, allow_nan=False)

    def test_near_constant_methods_share_numerical_tolerance(self):
        for y in ([5.0, 5.000000000000001, 5.0], 5 + np.arange(16) * np.spacing(5.0)):
            with self.subTest(length=len(y)):
                x = np.arange(len(y))
                for function in (linear_regression, theil_sen):
                    result = function(x, y)
                    self.assertEqual(result["slope"], 0)
                    self.assertEqual(result["confidence_interval"], [0, 0])
                self.assertEqual(linear_regression(x, y)["p_value"], 1)
                self.assertEqual(mann_kendall(y)["p_value"], 1)
                self.assertEqual(mann_kendall(y)["s"], 0)

    def test_small_unit_trend_is_not_flattened(self):
        x = np.arange(16)
        y = 1e-20 * (x + 1)
        for function in (linear_regression, theil_sen):
            self.assertAlmostEqual(function(x, y)["slope"] / 1e-20, 1)
        self.assertLess(mann_kendall(y)["p_value"], 0.05)
        result = analyze_timeseries(series(y), frequency="annual")
        self.assertTrue(result["reliable"])
        self.assertEqual(result["autocorrelation"]["status"], "zero_residual_variance")

    def test_bh_reference_and_missing(self):
        np.testing.assert_allclose(adjust_p_values([0.01, 0.04, 0.03, 0.002]), [0.02, 0.04, 0.04, 0.008])
        self.assertEqual(adjust_p_values([None, 0.01]), [None, 0.02])
        self.assertEqual(adjust_p_values([]), [])
        with self.assertRaises(ValueError):
            adjust_p_values([1.1])

    def test_unsorted_input_preserves_result(self):
        frame = series(np.arange(12))
        result = analyze_timeseries(frame.sample(frac=1, random_state=5), frequency="annual")
        self.assertEqual(result["theil_sen"]["slope"], 1)

    def test_nonuniform_time_uses_actual_years(self):
        frame = series(np.arange(12) * 3).drop(index=[2, 3])
        result = analyze_timeseries(frame, frequency="annual")
        self.assertEqual(result["theil_sen"]["slope"], 3)
        self.assertEqual(result["data_quality"]["excluded_years"], [2002, 2003])

    def test_complete_months_remove_repeat_seasonality(self):
        dates = pd.date_range("2000-01-01", periods=12 * 12, freq="MS")
        frame = pd.DataFrame({"date": dates, "value": 10 * np.sin(2 * np.pi * (dates.month - 1) / 12) + 2 * (dates.year - 2000)})
        result = analyze_timeseries(frame)
        self.assertAlmostEqual(result["theil_sen"]["slope"], 2)
        self.assertEqual(result["data_quality"]["n_years"], 12)

    def test_incomplete_year_excluded_and_optional_threshold_flagged(self):
        dates = pd.date_range("2000-01-01", periods=120, freq="MS")
        frame = pd.DataFrame({"date": dates, "value": np.arange(120)}).drop(index=0)
        result = analyze_timeseries(frame)
        self.assertEqual(result["data_quality"]["raw_excluded_years"], [2000])
        self.assertEqual(result["data_quality"]["excluded_years"], [])
        relaxed = analyze_timeseries(frame, min_months_per_year=10)
        self.assertIn("incomplete_seasonal_coverage", relaxed["reliability_reasons"])

    def test_missing_and_infinity_are_not_imputed(self):
        values = np.arange(12, dtype=float)
        values[[2, 4, 6]] = [np.nan, np.inf, -np.inf]
        result = analyze_timeseries(series(values), frequency="annual")
        self.assertEqual(result["data_quality"]["valid_observations"], 9)
        self.assertEqual(result["data_quality"]["missing_fraction"], 0.25)
        self.assertIn("excess_missing_observations", result["reliability_reasons"])
        self.assertEqual(result["theil_sen"]["slope"], 1)

    def test_partial_boundary_year_does_not_fail_clean_analysis_window(self):
        for partial_year in (2010, 2020):
            with self.subTest(partial_year=partial_year):
                dates = pd.date_range("2010-01-01", "2020-12-01", freq="MS")
                frame = pd.DataFrame({"date": dates, "value": dates.year - 2010})
                frame = frame[(dates.year != partial_year) | (dates.month == 1)]
                result = analyze_timeseries(frame, max_missing_fraction=0.05)
                quality = result["data_quality"]
                self.assertEqual(quality["missing_fraction"], 0)
                self.assertAlmostEqual(quality["raw_missing_fraction"], 11 / 132)
                self.assertEqual(quality["raw_expected_observations"], 132)
                self.assertEqual(quality["expected_observations"], 120)
                self.assertEqual(quality["analyzed_valid_observations"], 120)
                self.assertEqual(quality["excluded_years"], [])
                self.assertEqual(quality["raw_excluded_years"], [partial_year])
                self.assertEqual(quality["missing_analysis_years"], [])
                self.assertEqual(quality["analysis_period"]["start"], "2011-01-01" if partial_year == 2010 else "2010-01-01")
                self.assertNotIn("excess_missing_observations", result["reliability_reasons"])
                self.assertTrue(result["reliable"])

    def test_excluded_interior_year_remains_an_analysis_gap(self):
        dates = pd.date_range("2010-01-01", "2020-12-01", freq="MS")
        frame = pd.DataFrame({"date": dates, "value": dates.year - 2010})
        frame = frame[(dates.year != 2015) | (dates.month == 1)]
        result = analyze_timeseries(frame, max_missing_fraction=0.05)
        quality = result["data_quality"]
        self.assertEqual(quality["expected_observations"], 132)
        self.assertEqual(quality["analyzed_valid_observations"], 120)
        self.assertAlmostEqual(quality["missing_fraction"], 12 / 132)
        self.assertAlmostEqual(quality["raw_missing_fraction"], 11 / 132)
        self.assertEqual(quality["excluded_years"], [2015])
        self.assertEqual(quality["missing_analysis_years"], [2015])
        self.assertIn("excess_missing_observations", result["reliability_reasons"])

    def test_relaxed_month_threshold_counts_actual_contributing_months(self):
        dates = pd.date_range("2010-01-01", periods=120, freq="MS")
        frame = pd.DataFrame({"date": dates, "value": dates.year - 2010}).iloc[1:]
        result = analyze_timeseries(frame, min_months_per_year=11, max_missing_fraction=0.005)
        quality = result["data_quality"]
        self.assertEqual(quality["expected_observations"], 120)
        self.assertEqual(quality["analyzed_valid_observations"], 119)
        self.assertAlmostEqual(quality["missing_fraction"], 1 / 120)
        self.assertIn("excess_missing_observations", result["reliability_reasons"])

    def test_empty_and_insufficient_are_structured(self):
        for frame in (series([]), series([1, 2, 3]), series([np.nan] * 10)):
            result = analyze_timeseries(frame, frequency="annual")
            self.assertEqual(result["status"], "insufficient_data")
            self.assertIsNone(result["mann_kendall"])
            if result["data_quality"]["n_years"] == 0:
                self.assertIsNone(result["data_quality"]["missing_fraction"])
                self.assertEqual(result["data_quality"]["expected_observations"], 0)
                self.assertNotIn("excess_missing_observations", result["reliability_reasons"])
            json.dumps(result, allow_nan=False)

    def test_bad_dates_values_duplicates_and_parameters_rejected(self):
        bad_frames = [pd.DataFrame({"date": [2000, 2001, 2002], "value": [1, 2, 3]}),
                      pd.DataFrame({"date": ["bad"], "value": [1]}),
                      series(["not-a-number"]), pd.concat([series([1]), series([2])])]
        for frame in bad_frames:
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                analyze_timeseries(frame, frequency="annual")
        for kwargs in ({"alpha": 0}, {"alpha": 0.9}, {"min_years": 4}, {"frequency": "daily"},
                       {"min_months_per_year": 13}, {"max_missing_fraction": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                analyze_timeseries(series(range(10)), **kwargs)

    def test_low_level_nonfinite_duplicate_and_short_rejected(self):
        for function in (linear_regression, theil_sen):
            for x, y in [([1, 1, 2], [1, 2, 3]), ([1, 2, 3], [1, np.nan, 3]), ([1, 2], [1, 2])]:
                with self.assertRaises(ValueError):
                    function(x, y)

    def test_correlated_residuals_flagged(self):
        x = np.arange(40)
        result = analyze_timeseries(series(0.5 * x + np.sin(x / 4)), frequency="annual")
        self.assertTrue(result["autocorrelation"]["flagged"])
        self.assertFalse(result["reliable"])

    def test_unassessable_autocorrelation_flagged(self):
        frame = pd.DataFrame({"date": [f"{2000 + 2*i}-01-01" for i in range(10)],
                              "value": np.arange(10) + np.sin(np.arange(10))})
        result = analyze_timeseries(frame, frequency="annual", max_missing_fraction=1)
        self.assertEqual(result["autocorrelation"]["status"], "not_assessable")
        self.assertFalse(result["reliable"])

    def test_endpoint_driven_direction_sensitivity(self):
        result = analyze_timeseries(series([0, 0, 0, 0, 0, 1, 1, 1]), frequency="annual")
        self.assertFalse(result["sensitivity"]["direction_stable"])
        self.assertFalse(result["reliable"])


class RegionTests(unittest.TestCase):
    def test_supported_divergence_and_contract(self):
        result = analyze_region(region(), frequency="annual")
        self.assertTrue(result["divergence_detected"])
        self.assertEqual(result["divergence"]["category"], "Supported Signal")
        for key in ["region", "observation_period", "variables", "trend_slopes", "confidence_intervals",
                    "p_values", "data_quality", "divergence_detected", "limitations"]:
            self.assertIn(key, result)
        json.dumps(result, allow_nan=False)

    def test_same_direction_and_constant_not_divergence(self):
        for water in (np.arange(16), [5] * 16):
            result = analyze_region(region(water=water), frequency="annual")
            self.assertEqual(result["divergence"]["category"], "No Detected Divergence")
            self.assertFalse(result["divergence_detected"])

    def test_missing_indicator_is_uncertain(self):
        frame = region().query("variable == 'NDVI'")
        result = analyze_region(frame, frequency="annual")
        self.assertEqual(result["divergence"]["category"], "Uncertain Signal")

    def test_common_period_not_independent_periods(self):
        result = analyze_region(region(water_start=2004), frequency="annual")
        self.assertEqual(result["observation_period"]["years"], list(range(2004, 2016)))
        self.assertEqual(result["data_quality"]["by_variable"]["NDVI"]["alignment_excluded_years"], list(range(2000, 2004)))
        self.assertTrue(result["divergence_detected"])

    def test_annual_alignment_recomputes_missingness(self):
        frame = region(water_start=2004)
        frame.loc[(frame.variable == "NDVI") & (frame.date.dt.year < 2004), "value"] = np.nan
        result = analyze_region(frame, frequency="annual", max_missing_fraction=0.05)
        quality = result["data_quality"]["by_variable"]["NDVI"]
        self.assertEqual(quality["raw_missing_fraction"], 0.25)
        self.assertEqual(quality["missing_fraction"], 0)
        self.assertEqual(quality["expected_observations"], 12)
        self.assertEqual(quality["analyzed_valid_observations"], 12)
        self.assertEqual(quality["excluded_years"], [])
        self.assertEqual(quality["raw_excluded_years"], list(range(2000, 2004)))
        self.assertTrue(result["divergence_detected"])

    def test_monthly_alignment_filters_seasonal_coverage_flags(self):
        from examples.demo import make_synthetic_data
        frame = make_synthetic_data()
        # NDVI's incomplete year passes the relaxed threshold but is outside
        # moisture coverage, so it must not lower reliability after alignment.
        remove = ((frame.variable == "NDVI") & (frame.date == "2000-01-01")) | (
            (frame.variable == "soil_moisture") & (frame.date.dt.year == 2000))
        result = analyze_region(frame.loc[~remove], min_months_per_year=11, max_missing_fraction=0)
        quality = result["data_quality"]["by_variable"]["NDVI"]
        self.assertEqual(quality["incomplete_retained_years"], [])
        self.assertEqual(quality["raw_incomplete_retained_years"], [2000])
        self.assertEqual(quality["alignment_excluded_years"], [2000])
        self.assertEqual(quality["missing_fraction"], 0)
        self.assertEqual(quality["analyzed_valid_observations"], 15 * 12)
        self.assertTrue(result["divergence_detected"])

    def test_no_overlap_is_uncertain_and_json_serializable(self):
        result = analyze_region(region(water_start=2050), frequency="annual")
        self.assertEqual(result["observation_period"]["years"], [])
        self.assertEqual(result["divergence"]["category"], "Uncertain Signal")
        json.dumps(result, allow_nan=False)

    def test_weak_opposing_trends_uncertain(self):
        # Alternating fluctuations with a small net trend have wide slope intervals.
        x = np.arange(16)
        green = x * 0.001 + (-1.0) ** x
        result = analyze_region(region(green=green, water=-green), frequency="annual")
        self.assertEqual(result["divergence"]["category"], "Uncertain Signal")

    def test_autocorrelation_blocks_supported(self):
        x = np.arange(40)
        result = analyze_region(region(green=x + np.sin(x / 4), water=-x - np.sin(x / 4)), frequency="annual")
        self.assertFalse(result["divergence_detected"])
        self.assertEqual(result["divergence"]["category"], "Uncertain Signal")

    def test_conflicting_vegetation_indicators_uncertain(self):
        frame = region()
        evi = frame.query("variable == 'NDVI'").assign(variable="EVI")
        evi["value"] *= -1
        result = analyze_region(pd.concat([frame, evi]), frequency="annual")
        self.assertEqual(result["divergence"]["category"], "Uncertain Signal")
        self.assertIn("vegetation_indicators_disagree", result["divergence"]["reasons"])

    def test_metadata_and_multiple_regions_rejected(self):
        for column in ("unit", "source", "region_id"):
            frame = region()
            frame.loc[0, column] = "different"
            with self.subTest(column=column), self.assertRaises(ValueError):
                analyze_region(frame, frequency="annual")
        with self.assertRaises(ValueError):
            analyze_region(region().drop(columns="unit"), frequency="annual")

    def test_case_insensitive_and_configurable_variable_names(self):
        frame = region().replace({"variable": {"NDVI": "ndvi", "soil_moisture": "RootMoist"}})
        result = analyze_region(frame, frequency="annual", soil_moisture_variable="rootmoist")
        self.assertTrue(result["divergence_detected"])

    def test_default_indicator_matching_handles_all_cases(self):
        from src.divergence import detect_divergence
        for green_name, water_name in [("ndvi", "soil_moisture"), ("NDVI", "SOIL_MOISTURE"),
                                       ("nDvI", "Soil_Moisture"), ("evi", "soil_moisture")]:
            with self.subTest(green_name=green_name, water_name=water_name):
                frame = region().replace({"variable": {"NDVI": green_name, "soil_moisture": water_name}})
                result = analyze_region(frame, frequency="annual")
                self.assertTrue(result["divergence_detected"])
                self.assertIn(green_name, result["analysis"])
                direct = detect_divergence(result["analysis"])
                self.assertEqual(direct["category"], "Supported Signal")
                self.assertEqual(direct["pairs"][0]["vegetation"], green_name)
        missing = detect_divergence({})
        self.assertEqual(missing["category"], "Uncertain Signal")

    def test_direct_detector_rejects_ambiguous_case_aliases(self):
        from src.divergence import detect_divergence
        results = analyze_region(region(), frequency="annual")["analysis"]
        results["ndvi"] = results["NDVI"]
        with self.assertRaisesRegex(ValueError, "case-insensitively"):
            detect_divergence(results)

    def test_numerical_noise_does_not_create_divergence(self):
        x = np.arange(16)
        result = analyze_region(region(green=5 + x * np.spacing(5.0),
                                       water=5 - x * np.spacing(5.0)), frequency="annual")
        self.assertFalse(result["divergence_detected"])
        self.assertEqual(result["divergence"]["category"], "No Detected Divergence")
        for value in result["analysis"].values():
            self.assertEqual(value["adjusted_p_value"], 1)
            self.assertEqual(value["autocorrelation"]["status"], "zero_residual_variance")

    def test_nullable_missing_values(self):
        frame = region()
        frame["value"] = frame.value.astype("Float64")
        frame.loc[0, "value"] = pd.NA
        result = analyze_region(frame, frequency="annual")
        self.assertEqual(result["data_quality"]["by_variable"]["NDVI"]["valid_observations"], 15)
        json.dumps(result, allow_nan=False)

    def test_existing_import_and_flat_contract(self):
        from src.divergence import analyze_region as existing_entry
        result = existing_entry(region(), frequency="annual")
        self.assertIsInstance(result["trend_slopes"]["NDVI"], float)
        self.assertIsInstance(result["confidence_intervals"]["NDVI"], list)
        self.assertIsInstance(result["p_values"]["NDVI"], float)
        self.assertTrue(result["data_quality"]["synthetic_demo"])
        self.assertFalse(result["data_quality"]["qa_reviewed"])
        self.assertIn("trends", result)
        self.assertEqual(result["divergence_status"], "supported_signal")
        one = existing_entry(region().query("variable == 'NDVI'"), frequency="annual")
        self.assertIsNone(one["divergence_detected"])

    def test_legacy_estimate_trend(self):
        frame = region().query("variable == 'NDVI'").iloc[:4]
        result = estimate_trend(frame)
        self.assertGreater(result["slope_per_year"], 0)
        self.assertEqual(result["n_observations"], 4)
        self.assertEqual(result["inference_status"], "exploratory_only")
        self.assertEqual(estimate_trend(frame.iloc[:2])["status"], "insufficient_data")
        with self.assertRaises(ValueError):
            estimate_trend(region())

    def test_input_frame_not_mutated(self):
        frame = region()
        frame.loc[0, "value"] = np.inf
        original = frame.copy(deep=True)
        analyze_region(frame, frequency="annual")
        pd.testing.assert_frame_equal(frame, original)

    def test_regional_counts_distinguish_rows_from_annual_values(self):
        from examples.demo import make_synthetic_data
        result = analyze_region(make_synthetic_data())
        self.assertEqual(result["data_quality"]["n_raw_rows"], 384)
        self.assertNotIn("n_observations", result["data_quality"])
        for trend in result["trends"].values():
            self.assertEqual(trend["n_observations"], 16)

    def test_mixed_sources_are_explicitly_marked_synthetic(self):
        frame = region()
        frame.loc[frame.variable == "NDVI", "source"] = "NASA_PRODUCT_LABEL"
        frame.loc[frame.variable == "soil_moisture", "source"] = "synthetic_demo"
        result = analyze_region(frame, frequency="annual")
        self.assertTrue(result["data_quality"]["synthetic_demo"])
        self.assertTrue(any("If any source label contains SYNTHETIC" in note
                            and "mixtures of real and synthetic" in note for note in result["limitations"]))
        frame["source"] = "NASA_PRODUCT_LABEL"
        self.assertFalse(analyze_region(frame, frequency="annual")["data_quality"]["synthetic_demo"])


class EstimateTrendTests(unittest.TestCase):
    def test_nonfinite_values_match_explicitly_filtered_fit(self):
        for nullable in (False, True):
            with self.subTest(nullable=nullable):
                frame = region().query("variable == 'NDVI'").copy()
                if nullable:
                    frame["value"] = frame.value.astype("Float64")
                frame.loc[[0, 3, 7], "value"] = [pd.NA if nullable else np.nan, np.inf, -np.inf]
                frame = frame.sample(frac=1, random_state=19)
                original = frame.copy(deep=True)
                finite = np.isfinite(frame.value.to_numpy(dtype=float, na_value=np.nan))
                result = estimate_trend(frame)
                expected = estimate_trend(frame.loc[finite])
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["n_observations"], 13)
                self.assertEqual(result["data_quality"]["n_raw_rows"], 16)
                self.assertEqual(result["data_quality"]["dropped_observations"], 3)
                self.assertAlmostEqual(result["data_quality"]["nonfinite_fraction"], 3 / 16)
                for field in ("slope_per_year", "theil_sen_slope_per_year", "p_value", "kendall_p_value"):
                    self.assertEqual(result[field], expected[field])
                json.dumps(result, allow_nan=False)
                pd.testing.assert_frame_equal(frame, original)

    def test_dropping_missing_values_preserves_elapsed_time(self):
        frame = region().query("variable == 'NDVI'").iloc[:5].copy()
        frame["date"] = pd.to_datetime(["2000-01-01", "2001-01-01", "2003-01-01", "2007-01-01", "2010-01-01"])
        elapsed = (frame.date - frame.date.min()).dt.total_seconds() / (365.25 * 86400)
        frame["value"] = 4 + 2 * elapsed
        frame.loc[frame.index[1], "value"] = np.nan
        result = estimate_trend(frame)
        self.assertAlmostEqual(result["slope_per_year"], 2)
        self.assertAlmostEqual(result["theil_sen_slope_per_year"], 2)

    def test_insufficient_finite_observations_return_null_estimates(self):
        for values in ([], [1, 2], [np.nan] * 5, [1, np.nan, 2, np.inf, -np.inf]):
            with self.subTest(values=values):
                frame = region().query("variable == 'NDVI'").iloc[:len(values)].copy()
                frame["value"] = values
                result = estimate_trend(frame)
                self.assertEqual(result["status"], "insufficient_data")
                self.assertEqual(result["inference_status"], "insufficient_data")
                self.assertEqual(result["n_observations"], int(np.isfinite(values).sum()))
                for key in ("slope_per_year", "theil_sen_slope_per_year", "p_value", "kendall_p_value", "slope_95ci"):
                    self.assertIsNone(result[key])
                json.dumps(result, allow_nan=False)

    def test_malformed_input_still_raises_even_on_missing_rows(self):
        template = region().query("variable == 'NDVI'").iloc[:5].copy()
        for column, value in (("date", "bad-date"), ("value", "not-a-number"), ("unit", "different-unit")):
            with self.subTest(column=column):
                frame = template.copy()
                frame[column] = frame[column].astype(object)
                frame.loc[frame.index[0], column] = value
                with self.assertRaises(ValueError):
                    estimate_trend(frame)
        duplicate = template.iloc[[0]].copy()
        duplicate["value"] = np.nan
        with self.assertRaisesRegex(ValueError, "timestamps must be unique"):
            estimate_trend(pd.concat([template, duplicate]))
        with self.assertRaises(ValueError):
            estimate_trend(template.drop(columns="unit"))


if __name__ == "__main__":
    unittest.main()
