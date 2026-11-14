"""EarthRisk — Green Mirage: Member D's Streamlit dashboard.

The B → A → C interfaces are called directly. The bundled observations are
synthetic; the interface must never present them as real NASA findings.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.divergence import analyze_region
from src.nasa_data import get_timeseries
from src.policy_agent import investigate_policy
from src.ui.plots import comparison_figure, trend_figure
from src.ui.presentation import (
    confidence_interval, indicator_label, is_synthetic, number, p_value,
    research_items, research_title, safe_http_url, screening_summary,
)


st.set_page_config(
    page_title="EarthRisk | Green Mirage",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
    .block-container {max-width:1320px;padding-top:1.8rem;}
    h1,h2,h3 {letter-spacing:-.025em;}
    div[data-testid="stMetric"] {
      background:#f0f7f3;border:1px solid #d8e8df;
      border-radius:12px;padding:15px 17px;
    }
    div[data-testid="stMetricLabel"] {color:#486457;}
    [data-testid="stSidebar"] {border-right:1px solid #d7e5dd;}
    .eyebrow {font-size:.75rem;font-weight:800;letter-spacing:.17em;
              color:#26856b;text-transform:uppercase;}
    .hero-subtitle {font-size:1.08rem;color:#537165;margin-top:-5px;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300, show_spinner=False)
def load_indicator(region_id: str, variable: str) -> pd.DataFrame:
    """Get B's normalized observations, never silently fill missing values."""
    return get_timeseries(region_id, variable)


def describe_trend(analysis: dict, variable: str) -> None:
    """Render exactly A's numerical results and their original units."""
    trend = (analysis.get("trends") or {}).get(variable) or {}
    slopes = analysis.get("trend_slopes") or {}
    cis = analysis.get("confidence_intervals") or {}
    ps = analysis.get("p_values") or {}
    unit = str(trend.get("unit", "unit not provided"))
    slope = trend.get("slope_per_year", slopes.get(variable))
    ci = trend.get("slope_95ci", cis.get(variable))
    p = trend.get("p_value", ps.get(variable))
    st.metric(indicator_label(variable), f"{number(slope)} {unit}/year")
    st.caption(f"95% slope CI: {confidence_interval(ci)} {unit}/year")
    st.caption(f"Unadjusted regression p-value: {p_value(p)}")


def render_research_group(report: dict, key: str, label: str) -> None:
    """Render C's records without promoting unverified text to fact."""
    st.markdown(f"#### {label}")
    items = research_items(report, key)
    if not items:
        st.caption("No evidence records supplied for this category.")
        return
    for index, record in enumerate(items, start=1):
        with st.container(border=True):
            st.write(research_title(record, f"{label} #{index}"))
            summary = next(
                (record[k] for k in ("summary", "description", "finding", "rationale", "claim")
                 if isinstance(record.get(k), str) and record[k].strip()), None
            )
            if summary:
                st.write(summary)
            st.caption(f"Record verification: {record.get('verification_status', 'unspecified')}")
            for field, label_text in (
                ("jurisdiction", "Jurisdiction"),
                ("effective_date", "Effective date"),
                ("source_type", "Evidence type"),
                ("retrieved_at", "Retrieved"),
            ):
                if record.get(field):
                    st.caption(f"{label_text}: {record[field]}")
            link = next(
                (url for field in ("official_url", "source_url", "url", "doi_url")
                 if (url := safe_http_url(record.get(field)))), None
            )
            if link:
                st.link_button("Open original source", link)
            with st.expander("Record details"):
                st.json(record)


def render_map_if_available(frame: pd.DataFrame) -> None:
    """Show an actual map only when B supplies coordinate columns."""
    if {"latitude", "longitude"}.issubset(frame.columns):
        coords = frame[["latitude", "longitude"]].rename(
            columns={"latitude": "lat", "longitude": "lon"}
        )
    elif {"lat", "lon"}.issubset(frame.columns):
        coords = frame[["lat", "lon"]]
    else:
        st.caption(
            "Region map will appear when Member B supplies georeferenced data. "
            "No fictional coordinates are displayed."
        )
        return
    coords = coords.copy()
    coords["lat"] = pd.to_numeric(coords["lat"], errors="coerce")
    coords["lon"] = pd.to_numeric(coords["lon"], errors="coerce")
    coords = coords.dropna().drop_duplicates()
    coords = coords.loc[
        coords["lat"].between(-90, 90) & coords["lon"].between(-180, 180)
    ]
    if coords.empty:
        st.info("No valid coordinates were supplied for mapping.")
    else:
        st.map(coords)


# ---- Header and controls -----------------------------------------------------
st.markdown(
    '<div class="eyebrow">NASA Space Apps Challenge 2026 · Earth observations</div>',
    unsafe_allow_html=True,
)
st.title("EarthRisk: The Green Mirage")
st.markdown(
    '<div class="hero-subtitle">When landscapes look greener, are they also getting drier?</div>',
    unsafe_allow_html=True,
)
st.caption(
    "Explore environmental indicators, screen for opposing long-term trends, "
    "and examine traceable policy research."
)

st.sidebar.title("Explore a region")
region = st.sidebar.text_input(
    "Region ID", value="demo-region",
    help="The scaffold supports demo-region; Member B will supply real region IDs.",
).strip()
selected = st.sidebar.multiselect(
    "Environmental indicators",
    ["ndvi", "soil_moisture"],
    default=["ndvi", "soil_moisture"],
    format_func=indicator_label,
)
st.sidebar.caption(
    "NDVI measures vegetation greenness. Soil moisture measures soil water "
    "content. Both indicators are needed for the Green Mirage screen."
)
if st.sidebar.button("Refresh observations"):
    load_indicator.clear()
    st.rerun()
if not region:
    st.info("Enter a region ID to get started.")
    st.stop()
if not selected:
    st.info("Choose at least one environmental indicator.")
    st.stop()

frames = []
for indicator in selected:
    try:
        frames.append(load_indicator(region, indicator))
    except (ValueError, FileNotFoundError, KeyError, OSError) as exc:
        st.warning(f"Indicator unavailable — {indicator_label(indicator)}: {exc}")
if not frames:
    st.error("No observations available for this region. Try demo-region.")
    st.stop()

observations = pd.concat(frames, ignore_index=True)
observations["date"] = pd.to_datetime(observations["date"])
first = observations["date"].min().date()
last = observations["date"].max().date()
window = st.sidebar.date_input(
    "Observation window", value=(first, last),
    min_value=first, max_value=last,
)
if not isinstance(window, (tuple, list)) or len(window) != 2:
    st.info("Choose a start date and an end date.")
    st.stop()
start_date, end_date = window
if start_date > end_date:
    st.error("The start date must precede the end date.")
    st.stop()
observations = observations.loc[
    observations["date"].dt.date.between(start_date, end_date)
].copy()
if observations.empty or (observations.groupby("variable").size() < 3).any():
    st.warning(
        "At least three observations per indicator are required for trend "
        "estimation. Choose a wider observation window."
    )
    st.stop()

try:
    analysis = analyze_region(observations)
except (TypeError, ValueError, KeyError) as exc:
    st.error(f"The scientific analysis could not run: {exc}")
    st.stop()

synthetic = is_synthetic(observations, analysis)
quality = analysis.get("data_quality") or {}
sources = quality.get("sources") or sorted(observations["source"].astype(str).unique())
if synthetic:
    st.error(
        "SYNTHETIC DEMONSTRATION DATA — NOT NASA OBSERVATIONS. "
        "All figures are illustrative, not environmental findings."
    )
elif not quality.get("qa_reviewed"):
    st.warning(
        "These observations have not been marked QA-reviewed. Confirm their "
        "NASA provenance, coverage and quality filters before interpretation."
    )

indicator_dates = [
    set(pd.to_datetime(group["date"]).dt.normalize())
    for _, group in observations.groupby("variable")
]
if len(indicator_dates) > 1 and any(
    dates != indicator_dates[0] for dates in indicator_dates[1:]
):
    st.warning(
        "Indicators do not share identical observation dates. Confirm "
        "temporal alignment before interpreting opposing trends."
    )
st.caption(
    f"**Region:** {region} · **Period:** {start_date} to {end_date} "
    f"· **Sources:** {', '.join(map(str, sources))}"
)

# ---- Screening and metrics ---------------------------------------------------
status, headline, explanation = screening_summary(analysis)
with st.container(border=True):
    st.subheader(headline)
    if status == "candidate":
        st.warning(explanation)
    else:
        st.info(explanation)
    st.caption(
        "Opposing slopes alone cannot establish causality, ecological damage, "
        "or policy failure. All numerical values come from Member A's analysis."
    )

st.markdown("### Indicator trends")
variables = analysis.get("variables") or [str(v) for v in observations["variable"].unique()]
columns = st.columns(len(variables))
for column, indicator in zip(columns, variables):
    with column:
        describe_trend(analysis, indicator)

st.divider()
tab_trends, tab_methods, tab_policy, tab_data = st.tabs(
    ["Environmental trends", "Scientific audit", "Policy & action", "Observations & export"]
)

with tab_trends:
    st.markdown("### Original observations")
    plotted_variables = observations["variable"].astype(str).drop_duplicates().tolist()
    plot_columns = st.columns(min(len(plotted_variables), 2))
    for column, indicator in zip(plot_columns, plotted_variables):
        subset = observations.loc[observations["variable"] == indicator]
        if not subset.empty:
            with column:
                st.plotly_chart(
                    trend_figure(subset),
                    width="stretch",
                    key=f"timeseries_{indicator}",
                )
    if observations["variable"].nunique() > 1:
        st.markdown("### Standardized comparison")
        st.plotly_chart(comparison_figure(observations), width="stretch")
        st.caption(
            "Each indicator is centered on its own mean and divided by its "
            "standard deviation (z-score). This compares shapes across units; "
            "it is NOT a physical risk index."
        )
    st.markdown("### Geographic context")
    render_map_if_available(observations)

with tab_methods:
    st.markdown("### Reproducibility and uncertainty")
    science_rows = []
    for variable, result in (analysis.get("trends") or {}).items():
        science_rows.append({
            "Indicator": indicator_label(variable),
            "Observations": result.get("n_observations"),
            "Slope / year": number(result.get("slope_per_year")),
            "Unit": result.get("unit", "not provided"),
            "95% slope CI": confidence_interval(result.get("slope_95ci")),
            "Raw p-value": p_value(result.get("p_value")),
            "Theil–Sen / year": number(result.get("theil_sen_slope_per_year")),
            "Kendall tau": number(result.get("kendall_tau")),
        })
    if science_rows:
        st.dataframe(pd.DataFrame(science_rows), width="stretch", hide_index=True)
    q1, q2, q3 = st.columns(3)
    q1.metric("Observation records", str(len(observations)))
    q2.metric("Data QA reviewed", "Yes" if quality.get("qa_reviewed") else "No")
    q3.metric("Demo-only", "Yes" if synthetic else "No")
    st.markdown("#### Limitations")
    for limitation in analysis.get("limitations") or ["No limitations supplied."]:
        st.write(f"• {limitation}")
    st.caption(
        "Unadjusted regressions may require corrections for seasonality, "
        "autocorrelation, spatial dependence, and multiple comparisons."
    )
    with st.expander("Full statistical response"):
        st.json(analysis)
    st.download_button(
        "Export analysis (JSON)",
        data=json.dumps(analysis, indent=2, default=str),
        file_name="earthrisk_analysis.json",
        mime="application/json",
    )

with tab_policy:
    st.markdown("### Investigate this region")
    st.write(
        "Member C's research agent will examine government policies, scientific "
        "studies, evidence gaps and conservation options, with original sources."
    )
    if synthetic:
        st.info(
            "This fictional region can exercise the agent interface, but cannot "
            "support a genuine jurisdictional or environmental assessment."
        )
    signature = json.dumps({
        "region": region,
        "window": [str(start_date), str(end_date)],
        "slopes": analysis.get("trend_slopes"),
        "sources": list(map(str, sources)),
    }, sort_keys=True, default=str)
    if st.button("Investigate This Region", type="primary", key="investigate"):
        try:
            with st.spinner("Running the research interface..."):
                report = investigate_policy(analysis)
            st.session_state["earthrisk_research"] = {
                "signature": signature, "report": report,
            }
        except (TypeError, ValueError, KeyError, OSError) as exc:
            st.error(f"Research unavailable: {exc}")
    stored = st.session_state.get("earthrisk_research")
    if stored and stored.get("signature") == signature:
        report = stored["report"]
        verification = str(report.get("verification_status", "unspecified"))
        if verification == "not_started":
            st.warning(
                "Policy research is not yet implemented. No government "
                "policy or scientific source has been verified."
            )
        else:
            st.info(
                f"Agent report status: {verification}. Verify original sources "
                "and record-level statuses before acting on any suggestion."
            )
        render_research_group(report, "policies", "Government policies")
        render_research_group(report, "scientific_studies", "Scientific studies")
        render_research_group(report, "potential_policy_gaps", "Potential policy or evidence gaps")
        render_research_group(report, "conservation_options", "Conservation options")
        render_research_group(report, "citations", "Sources and citations")
        for limitation in report.get("limitations", []):
            st.caption(f"Research limitation: {limitation}")
        st.download_button(
            "Export research brief (JSON)",
            data=json.dumps(report, indent=2, default=str),
            file_name="earthrisk_research_brief.json",
            mime="application/json",
        )

with tab_data:
    st.markdown("### Observations used in this screening")
    st.dataframe(
        observations.sort_values(["variable", "date"]),
        width="stretch", hide_index=True,
    )
    st.caption("Rows retain source names and units, limited to the selected period.")
    st.download_button(
        "Download displayed observations (CSV)",
        data=observations.to_csv(index=False).encode("utf-8"),
        file_name="earthrisk_observations.csv",
        mime="text/csv",
    )

st.divider()
st.caption(
    "EarthRisk · NASA Space Apps Challenge 2026 · Science first, provenance always. "
    "This dashboard does not provide environmental or government policy determinations."
)
