"""Member D's display-contract tests; no Streamlit server is required."""
import pandas as pd
import pytest

from src.ui.plots import comparison_figure, trend_figure
from src.ui.presentation import (
    confidence_interval,
    is_synthetic,
    number,
    p_value,
    research_items,
    research_title,
    safe_http_url,
    screening_summary,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.to_datetime(["2020-01-01", "2021-01-01", "2022-01-01"]),
        "variable": ["ndvi"] * 3,
        "value": [0.2, 0.3, 0.4],
        "unit": ["index"] * 3,
        "source": ["SYNTHETIC_DEMO_NOT_NASA"] * 3,
    })


def test_screening_distinguishes_candidate_from_confirmation():
    status, headline, body = screening_summary({"divergence_detected": True})
    assert status == "candidate"
    assert "Candidate" in headline
    assert "NOT" in body


@pytest.mark.parametrize("flag, expected", [
    (None, "incomplete"),
    (False, "not_detected"),
])
def test_screening_other_states(flag, expected):
    assert screening_summary({"divergence_detected": flag})[0] == expected


def test_synthetic_source_flag_does_not_depend_only_on_analysis():
    assert is_synthetic(_frame(), {"data_quality": {}})
    real = _frame().assign(source="MOD13A3.061")
    assert not is_synthetic(real, {"data_quality": {}})
    assert is_synthetic(real, {"data_quality": {"synthetic_demo": True}})


def test_numbers_and_ci_handle_missing_or_nonfinite():
    assert number(None) == "N/A"
    assert number(float("nan")) == "N/A"
    assert confidence_interval([0.1, 0.2]) == "[+0.100, +0.200]"
    assert p_value(0.00001) == "< 0.001"
    assert p_value(-1) == "N/A"


@pytest.mark.parametrize("bad", [
    "javascript:alert(1)", "file:///etc/passwd", "https://user:pass@example.com",
    "https://example.com/a b", None,
])
def test_unsafe_external_links_are_not_rendered(bad):
    assert safe_http_url(bad) is None


def test_valid_source_and_future_agent_schema():
    assert safe_http_url("https://www.nasa.gov/") == "https://www.nasa.gov/"
    report = {"policies": [{"title": "Water plan"}, "Possible funding programme", None]}
    assert len(research_items(report, "policies")) == 2
    assert research_title({"name": "Agency recommendation"}) == "Agency recommendation"


def test_trend_and_comparison_charts_use_own_units():
    frame = _frame()
    fig = trend_figure(frame)
    assert fig.layout.yaxis.title.text.endswith("(index)")
    assert len(fig.data) == 1
    combined = pd.concat([
        frame,
        frame.assign(variable="soil_moisture", value=[20, 18, 15], unit="kg/m2"),
    ])
    comparison = comparison_figure(combined)
    assert len(comparison.data) == 2
    assert "standard score" in comparison.layout.yaxis.title.text


def test_empty_plot_is_rejected():
    with pytest.raises(ValueError):
        trend_figure(_frame().iloc[:0])


def test_comparison_preserves_missing_values_without_zero_imputation():
    frame = _frame().assign(value=[1.0, float('nan'), 3.0])
    values = list(comparison_figure(frame).data[0].y)
    assert values[0] == -1.0 and pd.isna(values[1]) and values[2] == 1.0
