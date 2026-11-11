"""Altair charts with a consistent, restrained look."""

from __future__ import annotations

from datetime import date

import altair as alt
import pandas as pd

STATUS_COLORS = {"On track": "#2E7D5B", "Watch": "#C98A1B", "At risk": "#B83A3A"}
SERIES_COLORS = ["#1F5FAE", "#D9822B", "#2E8B6E", "#8E5BB5", "#C2445A", "#5C6B7A"]


def trend_lines(
    df: pd.DataFrame,
    series: str,
    fy_baseline: date | None,
    highlight: list[str] | None = None,
    height: int = 340,
) -> alt.Chart:
    """One line per series, labelled at its end, with a dashed FY baseline rule.

    The tooltip carries the change since the fiscal-year baseline so the chart
    doesn't need a number on every point.
    """
    data = df.copy()
    data["snap_date"] = pd.to_datetime(data["snap_date"])
    if fy_baseline is not None:
        base = (
            data[data["snap_date"] <= pd.Timestamp(fy_baseline)]
            .sort_values("snap_date")
            .groupby(series)["avg_ehi"]
            .last()
            .rename("baseline")
        )
        data = data.join(base, on=series)
        data["since_fy"] = (data["avg_ehi"] - data["baseline"]).round(1)
    else:
        data["since_fy"] = float("nan")

    highlighted = set(highlight or [])
    data["emph"] = data[series].isin(highlighted) if highlighted else True

    names = sorted(data[series].unique())
    color = alt.Color(
        f"{series}:N",
        scale=alt.Scale(domain=names, range=(SERIES_COLORS * 4)[: len(names)]),
        legend=None,
    )
    opacity = alt.condition("datum.emph", alt.value(1.0), alt.value(0.18))
    base_chart = alt.Chart(data).encode(
        x=alt.X("snap_date:T", title=None, axis=alt.Axis(format="%b %y", grid=False)),
        y=alt.Y("avg_ehi:Q", title="Average EHI", scale=alt.Scale(zero=False)),
        color=color,
        opacity=opacity,
    )
    lines = base_chart.mark_line(strokeWidth=2.2)
    hover = base_chart.mark_circle(size=80).encode(
        opacity=alt.value(0),
        tooltip=[
            alt.Tooltip(f"{series}:N", title=series.replace("_", " ").title()),
            alt.Tooltip("snap_date:T", title="Month end", format="%d %b %Y"),
            alt.Tooltip("avg_ehi:Q", title="Average EHI", format=".1f"),
            alt.Tooltip("since_fy:Q", title="Change since FY start (pts)", format="+.1f"),
        ],
    )
    last = data.sort_values("snap_date").groupby(series).tail(1)
    labels = (
        alt.Chart(last)
        .mark_text(align="left", dx=6, fontSize=11)
        .encode(
            x="snap_date:T",
            y="avg_ehi:Q",
            text=f"{series}:N",
            color=color,
            opacity=alt.condition("datum.emph", alt.value(1.0), alt.value(0.3)),
        )
    )
    layers = [lines, hover, labels]
    if fy_baseline is not None:
        rule = (
            alt.Chart(pd.DataFrame({"d": [pd.Timestamp(fy_baseline)]}))
            .mark_rule(strokeDash=[4, 4], color="#8A93A6")
            .encode(x="d:T")
        )
        layers.insert(0, rule)
    return alt.layer(*layers).properties(height=height).configure_view(strokeWidth=0)


def heatmap(df: pd.DataFrame, value: str = "avg_ehi", height: int = 320) -> alt.Chart:
    base = alt.Chart(df).encode(
        x=alt.X("sector_name:N", title=None, axis=alt.Axis(labelAngle=-30)),
        y=alt.Y("hub_name:N", title=None),
    )
    cells = base.mark_rect(cornerRadius=2).encode(
        color=alt.Color(
            f"{value}:Q",
            scale=alt.Scale(scheme="blues")
            if value == "avg_ehi"
            else alt.Scale(scheme="redblue", domainMid=0),
            title="Avg EHI" if value == "avg_ehi" else "Δ since FY start",
        ),
        tooltip=[
            alt.Tooltip("hub_name:N", title="Hub"),
            alt.Tooltip("sector_name:N", title="Sector"),
            alt.Tooltip("accounts:Q", title="Accounts"),
            alt.Tooltip("avg_ehi:Q", title="Avg EHI", format=".1f"),
            alt.Tooltip("delta_fytd:Q", title="Δ since FY start", format="+.1f"),
            alt.Tooltip("pct_on_track:Q", title="% on track", format=".0f"),
        ],
    )
    text = base.mark_text(fontSize=11).encode(
        text=alt.Text(f"{value}:Q", format=".0f" if value == "avg_ehi" else "+.1f"),
        color=alt.value("#111A2B"),
    )
    return (cells + text).properties(height=height).configure_view(strokeWidth=0)


def status_bars(df: pd.DataFrame, height: int = 300) -> alt.Chart:
    order = list(STATUS_COLORS)
    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            y=alt.Y("hub_name:N", title=None, axis=alt.Axis(labelOverlap=False)),
            x=alt.X("sum(accounts):Q", title="Accounts", stack="normalize", axis=alt.Axis(format="%")),
            color=alt.Color(
                "status:N",
                scale=alt.Scale(domain=order, range=list(STATUS_COLORS.values())),
                legend=alt.Legend(orient="top", title=None),
            ),
            order=alt.Order("status_rank:Q"),
            tooltip=["hub_name", "status", "accounts"],
        )
        .transform_calculate(status_rank=f"indexof({order}, datum.status)")
        .properties(height=height)
        .configure_view(strokeWidth=0)
    )
