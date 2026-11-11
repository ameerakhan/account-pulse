"""Hub lens: where engagement is strong or slipping, by hub and sector."""

import pandas as pd
import streamlit as st

import components  # noqa: F401

st.set_page_config(page_title="Hub Lens · Account Pulse", page_icon="📈", layout="wide")

from components import charts  # noqa: E402
from components.data import header, load  # noqa: E402
from components.perf import fragment  # noqa: E402

header("Hub Lens", "Hub-by-sector view of engagement health, and the activity behind it")

d = load("hub_lens")
hubs, heat, activity = d["hub_summary"], d["heatmap"], d["activity_detail"]

cols = st.columns(len(hubs))
for col, row in zip(cols, hubs.itertuples(index=False), strict=True):
    col.metric(row.hub_name, f"{row.avg_ehi:.1f}", f"{row.delta_avg_ehi:+.1f}")


@fragment
def heatmap_section() -> None:
    st.subheader("Hub × sector")
    mode = st.radio(
        "Show", ["Average EHI", "Change since FY start"], horizontal=True, label_visibility="collapsed"
    )
    value = "avg_ehi" if mode == "Average EHI" else "delta_fytd"
    st.altair_chart(charts.heatmap(heat, value=value), use_container_width=True)


@fragment
def activity_section(activity: pd.DataFrame) -> None:
    st.subheader("Activity, last 180 days")
    c1, c2, c3, c4 = st.columns(4)
    hub = c1.multiselect("Hub", sorted(activity["hub_name"].unique()), placeholder="All")
    kind = c2.multiselect("Type", sorted(activity["activity_type"].unique()), placeholder="All")
    level = c3.multiselect("Seniority", ["Executive", "Senior", "Working"], placeholder="All")
    search = c4.text_input("Account contains")

    mask = pd.Series(True, index=activity.index)
    if hub:
        mask &= activity["hub_name"].isin(hub)
    if kind:
        mask &= activity["activity_type"].isin(kind)
    if level:
        mask &= activity["seniority"].isin(level)
    if search:
        mask &= activity["account_name"].str.contains(search, case=False, regex=False)
    view = activity[mask]

    st.caption(f"{len(view):,} activities")
    st.dataframe(
        view.drop(columns=["activity_id"]),
        hide_index=True,
        use_container_width=True,
        height=360,
        column_config={
            "activity_date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
            "activity_type": "Type",
            "seniority": "Seniority",
            "account_name": "Account",
            "tier": "Tier",
            "hub_name": "Hub",
            "sector_name": "Sector",
            "owner_name": "Owner",
        },
    )


heatmap_section()
activity_section(activity)
