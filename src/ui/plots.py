"""Reusable scientific plots; they display observations, not claims of causality."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.ui.presentation import indicator_label

COLORS = {
    "ndvi": "#24956D",
    "soil_moisture": "#4683CE",
}
DEFAULT_COLOR = "#7D6FB3"


def _polish(fig: go.Figure, y_title: str, height: int = 330) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#203A32"),
        margin=dict(l=5, r=10, t=25, b=10),
        xaxis=dict(title="Observation date", showgrid=False, tickformat="%Y"),
        yaxis=dict(title=y_title, gridcolor="rgba(45,92,76,0.12)", zeroline=False),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.14, x=0),
    )
    return fig


def trend_figure(frame: pd.DataFrame, title: str | None = None) -> go.Figure:
    """Plot the observed, unmodified values of a single variable."""
    if frame.empty:
        raise ValueError("Cannot plot an empty timeseries")
    sorted_frame = frame.sort_values("date")
    variable = str(sorted_frame["variable"].iloc[0])
    unit = str(sorted_frame["unit"].iloc[0])
    label = title or indicator_label(variable)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=sorted_frame["date"],
            y=sorted_frame["value"],
            name=label,
            mode="lines+markers",
            line=dict(color=COLORS.get(variable, DEFAULT_COLOR), width=3),
            marker=dict(size=6),
            hovertemplate="Value: %{y:.4g}<extra></extra>",
        )
    )
    return _polish(fig, f"{indicator_label(variable)} ({unit})")


def comparison_figure(frame: pd.DataFrame) -> go.Figure:
    """Compare within-variable standard scores, not a physical risk index.

    Series are centered by their own means and divided by their own
    population standard deviations. Flat series are shown at zero.
    """
    if frame.empty:
        raise ValueError("Cannot compare an empty timeseries")
    fig = go.Figure()
    for variable, group in frame.groupby("variable", sort=True):
        observations = group.sort_values("date")
        y = observations["value"].astype(float).to_numpy()
        valid = np.isfinite(y)
        z = np.full(len(y), np.nan)
        if valid.any():
            std = float(np.std(y[valid]))
            z[valid] = (y[valid] - float(np.mean(y[valid]))) / std if std > 0 else 0.0
        fig.add_trace(
            go.Scatter(
                x=observations["date"],
                y=z,
                mode="lines+markers",
                name=indicator_label(str(variable)),
                line=dict(color=COLORS.get(str(variable), DEFAULT_COLOR), width=3),
                marker=dict(size=5),
                hovertemplate="Standardized value: %{y:.2f}<extra></extra>",
            )
        )
    return _polish(fig, "Within-indicator standard score (z)", height=380)
