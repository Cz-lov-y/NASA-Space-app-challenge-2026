"""EarthRisk MVP dashboard. All bundled observations are SYNTHETIC examples."""
import pandas as pd
import streamlit as st

from src.divergence import analyze_region
from src.nasa_data import get_timeseries
from src.policy_agent import investigate_policy
from src.ui.plots import trend_figure

st.set_page_config(page_title="EarthRisk — Green Mirage", layout="wide")
st.title("EarthRisk — Green Mirage")
st.caption("Environmental trends → scientific screening → evidence-backed action")
st.warning(
    "SYNTHETIC DEMONSTRATION ONLY. This is NOT live NASA data and does not "
    "represent a verified environmental finding or government policy assessment."
)

region = st.selectbox("Region", ["demo-region"], index=0)
selected = st.multiselect("Indicators", ["ndvi", "soil_moisture"], default=["ndvi", "soil_moisture"])
if not selected:
    st.info("Select at least one indicator.")
    st.stop()

frames = [get_timeseries(region, variable) for variable in selected]
data = pd.concat(frames, ignore_index=True)

for variable, frame in zip(selected, frames):
    st.plotly_chart(trend_figure(frame, f"{variable.replace('_', ' ').title()} — demo"),
                    use_container_width=True)

try:
    analysis = analyze_region(data)
except ValueError as exc:
    st.error(f"Analysis error: {exc}")
    st.stop()

st.subheader("Statistical screening")
st.json(analysis)
if analysis["divergence_detected"]:
    st.info("Candidate opposing trends in SYNTHETIC data. Not a verified Green Mirage.")
elif analysis["divergence_detected"] is None:
    st.info("Select both indicators to perform divergence screening.")

if st.button("Investigate This Region", type="primary"):
    report = investigate_policy(analysis)
    st.subheader("Environmental Action Brief")
    st.warning("Agent retrieval is not yet implemented; there are no verified sources.")
    st.json(report)
