"""Account Pulse - home: the portfolio at a glance."""

import streamlit as st

import components  # noqa: F401  (sets up import path)

st.set_page_config(page_title="Account Pulse", page_icon="📈", layout="wide")

from components import charts  # noqa: E402
from components.data import header, load  # noqa: E402

header("Account Pulse", "Engagement health across the account portfolio · synthetic demo data")

d = load("home")
scores, hubs, mix = d["account_scores"], d["hub_summary"], d["status_mix"]

n = len(scores)
avg_now = scores["ehi"].mean()
avg_prev = scores["ehi_prev_month"].mean()
on_track = (scores["status"] == "On track").mean() * 100
on_track_prev = (scores["ehi_prev_month"] >= 70).mean() * 100
at_risk = int((scores["status"] == "At risk").sum())
at_risk_prev = int((scores["ehi_prev_month"] < 50).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Accounts", f"{n:,}")
c2.metric("Average EHI", f"{avg_now:.1f}", f"{avg_now - avg_prev:+.1f} vs last month")
c3.metric("% on track", f"{on_track:.1f}%", f"{on_track - on_track_prev:+.1f} pp")
c4.metric("At risk", f"{at_risk}", f"{at_risk - at_risk_prev:+d}", delta_color="inverse")

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("Status mix by hub")
    st.altair_chart(charts.status_bars(mix), use_container_width=True)
with right:
    st.subheader("Hub ranking")
    st.dataframe(
        hubs[["hub_name", "accounts", "avg_ehi", "delta_avg_ehi", "pct_on_track"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "hub_name": "Hub",
            "accounts": st.column_config.NumberColumn("Accounts"),
            "avg_ehi": st.column_config.ProgressColumn("Avg EHI", min_value=0, max_value=100, format="%.1f"),
            "delta_avg_ehi": st.column_config.NumberColumn("Δ month", format="%+.1f"),
            "pct_on_track": st.column_config.NumberColumn("% on track", format="%.0f%%"),
        },
    )

st.subheader("Biggest movers this month")
movers_cols = ["account_name", "hub_name", "tier", "ehi", "delta_month", "status"]
cfg = {
    "account_name": "Account",
    "hub_name": "Hub",
    "tier": "Tier",
    "ehi": st.column_config.NumberColumn("EHI", format="%.1f"),
    "delta_month": st.column_config.NumberColumn("Δ month", format="%+.1f"),
    "status": "Status",
}
m1, m2 = st.columns(2, gap="large")
with m1:
    st.caption("Largest declines")
    st.dataframe(
        scores.nsmallest(8, "delta_month")[movers_cols],
        hide_index=True,
        use_container_width=True,
        column_config=cfg,
    )
with m2:
    st.caption("Largest gains")
    st.dataframe(
        scores.nlargest(8, "delta_month")[movers_cols],
        hide_index=True,
        use_container_width=True,
        column_config=cfg,
    )

with st.expander("How the Engagement Health Index is calculated"):
    from pulse.config import RULES

    w = RULES.weights
    st.markdown(
        f"""
The **EHI** (0–100) is a weighted blend of five components, each scaled 0–100:

| Component | Weight | Measures |
|---|---|---|
| Recency | {w["recency"]:.0%} | Exponential decay since the last activity |
| Frequency | {w["frequency"]:.0%} | Activities in the last 90 days vs the tier's expectation |
| Breadth | {w["breadth"]:.0%} | Distinct activity types in the last 180 days |
| Depth | {w["depth"]:.0%} | Share of last-180-day activity with senior contacts |
| Attainment | {w["attainment"]:.0%} | Fiscal-year-to-date activity vs the prorated plan target |

**On track** ≥ {RULES.on_track:.0f} · **Watch** ≥ {RULES.watch:.0f} · **At risk** below that.
The definition lives once in SQL and is cross-checked against a pure-Python reference in the test-suite.
"""
    )
