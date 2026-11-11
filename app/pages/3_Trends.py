"""Trends: month-end engagement health by hub and by programme."""

from datetime import timedelta

import streamlit as st

import components  # noqa: F401

st.set_page_config(page_title="Trends · Account Pulse", page_icon="📈", layout="wide")

from components import charts  # noqa: E402
from components.data import header, load  # noqa: E402
from pulse.scoring import fiscal_year_label, fiscal_year_start  # noqa: E402

header("Trends", "Month-end average EHI. The dashed rule marks the start of the fiscal year.")

d = load("trends")
as_of = d["refresh_log"]["data_as_of"].iloc[0]
as_of = as_of.date() if hasattr(as_of, "date") else as_of
fy_baseline = fiscal_year_start(as_of) - timedelta(days=1)

hubs = sorted(d["hub_trend"]["hub_name"].unique())
pick = st.selectbox("Focus on a hub", ["All hubs", *hubs])
focus = [] if pick == "All hubs" else [pick]

st.subheader("By hub")
st.altair_chart(
    charts.trend_lines(d["hub_trend"], "hub_name", fy_baseline, highlight=focus),
    use_container_width=True,
)

st.subheader("By programme")
if focus:
    prog = d["programme_trend"]
    prog = prog[prog["hub_name"].isin(focus)]
    st.altair_chart(charts.trend_lines(prog, "programme_name", fy_baseline), use_container_width=True)
else:
    st.caption("Pick a hub above to see its programmes.")

st.caption(
    f"{fiscal_year_label(as_of)} began {fiscal_year_start(as_of):%d %b %Y}. "
    "Hover a line for its change since the baseline. The current partial month is excluded."
)
