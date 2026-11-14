"""Plotly chart factory for the Streamlit frontend (Member D)."""
import plotly.express as px


def trend_figure(frame, title: str):
    unit = str(frame["unit"].iloc[0])
    figure = px.line(frame.sort_values("date"), x="date", y="value", markers=True, title=title)
    figure.update_layout(xaxis_title="Date", yaxis_title=unit)
    return figure
