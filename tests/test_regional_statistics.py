"""Batch-family and missing-data tests; generated values are synthetic only."""
import json

import pandas as pd
import pytest

from src.regional_statistics import REQUIRED_COLUMNS, build_regional_screening
from src.statistics import adjust_p_values, analyze_region


def sample(region_id="test", years=22):
    dates = pd.date_range("2003-01-01", periods=years * 12, freq="MS")
    year = (dates.year - 2003).to_numpy()
    return pd.concat([
        pd.DataFrame(dict(date=dates, value=0.2 + year * .01, unit="1", variable="ndvi", source="SYNTHETIC_TEST_ONLY", region_id=region_id)),
        pd.DataFrame(dict(date=dates, value=100 - year * 2., unit="kg m-2", variable="soil_water_0_100cm", source="SYNTHETIC_TEST_ONLY", region_id=region_id)),
    ], ignore_index=True)


def feature(region_id, **props):
    return dict(type="Feature", geometry={"type": "Point", "coordinates": [0, 5]},
                properties=dict(region_id=region_id, bbox=[-5, 0, 5, 10], centroid=[0, 5], **props))


def test_batch_preserves_regional_result_and_applies_declared_family():
    data = pd.concat([sample("a"), sample("b")], ignore_index=True)
    before = data.copy(deep=True)
    report = build_regional_screening(data, [feature("a"), feature("b")])
    assert report["multiple_testing"]["family_size"] == 4
    raw = []
    for record in report["regions"]:
        expected = analyze_region(data[data.region_id == record["region_id"]], vegetation_variables=("ndvi",), soil_moisture_variable="soil_water_0_100cm")
        assert record["analysis"] == expected
        assert record["status"] == "eligible"
        assert record["screening"]["classification"] == "supported_signal"
        assert record["screening"]["synthetic_demo"]
        assert not record["screening"]["qa_reviewed"]
        assert record["geometry"] == feature("a")["geometry"]
        for variable in report["primary_variables"]:
            raw.append(expected["analysis"][variable]["mann_kendall"]["p_value"])
    actual = [r["screening"]["adjusted_p_values"][v] for r in report["regions"] for v in report["primary_variables"]]
    assert actual == adjust_p_values(raw)
    pd.testing.assert_frame_equal(data, before)
    json.dumps(report, allow_nan=False)


def test_independent_known_slopes_complete_years_and_extension_excluded():
    data = sample(years=23)
    report = build_regional_screening(data)
    record = report["regions"][0]
    assert record["analysis"]["observation_period"]["years"] == list(range(2003, 2025))
    assert record["analysis"]["trend_slopes"]["ndvi"] == pytest.approx(.01)
    assert record["analysis"]["trend_slopes"]["soil_water_0_100cm"] == pytest.approx(-2)


def test_missing_unsupported_and_insufficient_stay_distinct():
    partial = sample("pending").query("variable != 'ndvi'")
    short = sample("short", years=7)
    result = build_regional_screening(pd.concat([partial, short]), [feature("pending"), feature("ocean", data_status="unsupported_gldas"), feature("short")])
    assert [r["status"] for r in result["regions"]] == ["pending", "unsupported", "insufficient"]
    assert result["multiple_testing"]["family_size"] == 0
    assert all(r["screening"]["category"] is None for r in result["regions"])
    assert result["regions"][0]["analysis"] is None


def test_low_coverage_rejects_complete_year_without_imputation():
    data = sample()
    data["quality_flag"] = "coverage_review_required"
    data.loc[0, "quality_flag"] = "low_coverage"
    data.loc[1, "value"] = float("nan")
    result = build_regional_screening(data)["regions"][0]
    assert result["screening"]["qa_rejected_rows"] == 1
    assert 2003 not in result["analysis"]["observation_period"]["years"]
    assert len(result["analysis"]["observation_period"]["years"]) == 21
    assert data.loc[0, "value"] == .2


def test_family_includes_nonopposing_and_unreliable_regions():
    data = sample("a")
    other = sample("b")
    other.loc[other.variable == "soil_water_0_100cm", "value"] *= -1
    result = build_regional_screening(pd.concat([data, other]))
    assert result["multiple_testing"]["family_size"] == 4
    assert result["regions"][1]["screening"]["classification"] == "no_detected_divergence"


def test_empty_frame_retains_all_catalog_cells_as_pending():
    result = build_regional_screening(pd.DataFrame(columns=REQUIRED_COLUMNS), [feature("a"), feature("b")])
    assert len(result["regions"]) == 2
    assert result["multiple_testing"]["family_size"] == 0
    json.dumps(result, allow_nan=False)


def test_bad_dates_units_duplicates_and_catalog_mismatch_rejected():
    data = sample()
    with pytest.raises(ValueError, match="duplicate"):
        build_regional_screening(pd.concat([data, data.iloc[:1]]))
    for column, value, match in [("date", "nonsense", "dates"), ("value", "oops", "numeric"), ("unit", "m3 m-3", "expected unit")]:
        invalid = data.copy()
        invalid[column] = invalid[column].astype(object)
        invalid.loc[0, column] = value
        with pytest.raises(ValueError, match=match):
            build_regional_screening(invalid)
    with pytest.raises(ValueError, match="absent"):
        build_regional_screening(data, [feature("different")])
    with pytest.raises(ValueError, match="unique"):
        build_regional_screening(data, [feature("test"), feature("test")])


def test_gldas_only_diagnostic_is_real_analysis_without_paired_classification():
    data = sample().query("variable == 'soil_water_0_100cm'").copy()
    before = data.copy(deep=True)
    result = build_regional_screening(data)
    record = result['regions'][0]
    assert record['status'] == 'pending'
    assert record['analysis'] is None
    assert record['screening']['classification'] == 'pending'
    assert record['screening']['category'] is None
    assert result['multiple_testing']['family_size'] == 0
    available = record['available_indicator_analysis']
    assert available['variables'] == ['soil_water_0_100cm']
    assert available['trend_slopes']['soil_water_0_100cm'] == pytest.approx(-2)
    assert available['observation_period']['years'] == list(range(2003, 2025))
    assert available['divergence_detected'] is None
    assert not available['data_quality']['qa_reviewed']
    assert 'not been adjusted across regions' in available['limitations'][0]
    pd.testing.assert_frame_equal(data, before)
    json.dumps(result, allow_nan=False)


def test_available_diagnostic_respects_qa_missing_months_and_unsupported():
    data = sample().query("variable == 'soil_water_0_100cm'").copy()
    data['quality_flag'] = 'coverage_review_required'
    data.loc[data.index[0], 'quality_flag'] = 'low_coverage'
    record = build_regional_screening(data)['regions'][0]
    assert 2003 not in record['available_indicator_analysis']['observation_period']['years']
    unsupported = build_regional_screening(data, [feature('test', data_status='unsupported_gldas')])['regions'][0]
    assert unsupported['available_indicator_analysis'] is None
    paired = build_regional_screening(sample())['regions'][0]
    assert paired['available_indicator_analysis'] is None


def test_unreceived_export_placeholder_is_pending_not_insufficient():
    data = sample()
    data['quality_flag'] = 'coverage_review_required'
    placeholder = data.variable.eq('ndvi')
    data.loc[placeholder, 'value'] = float('nan')
    data.loc[placeholder, 'quality_flag'] = 'pending_export'
    result = build_regional_screening(data)
    record = result['regions'][0]
    assert record['status'] == 'pending'
    assert record['analysis'] is None
    assert record['available_indicator_analysis']['variables'] == ['soil_water_0_100cm']
    assert result['multiple_testing']['family_size'] == 0
    # An actual supplied export with no valid pixels is an insufficient record.
    data.loc[placeholder, 'quality_flag'] = 'no_valid_pixels'
    record = build_regional_screening(data)['regions'][0]
    assert record['status'] == 'insufficient'
    assert record['analysis'] is not None
