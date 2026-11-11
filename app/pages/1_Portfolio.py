"""Portfolio: every account, filterable, with a component breakdown and export."""

import pandas as pd
import streamlit as st

import components  # noqa: F401

st.set_page_config(page_title="Portfolio · Account Pulse", page_icon="📈", layout="wide")

from components import filters  # noqa: E402
from components.data import header, load  # noqa: E402
from components.perf import fragment  # noqa: E402
from pulse.exports import to_excel_bytes  # noqa: E402

header("Portfolio", "Every account's score, its components, and how it has moved")

scores = load("portfolio")["account_scores"]
chosen = filters.sidebar_filters(scores)
view = filters.apply(scores, chosen)

if view.empty:
    st.warning("No accounts match these filters. Use **Reset filters** in the sidebar.")
    st.stop()

k1, k2, k3 = st.columns(3)
k1.metric("Accounts in view", f"{len(view):,}")
k2.metric("Average EHI", f"{view['ehi'].mean():.1f}", f"{view['delta_fytd'].mean():+.1f} since FY start")
k3.metric("% on track", f"{(view['status'] == 'On track').mean():.0%}")

COLUMNS = [
    "account_name",
    "hub_name",
    "sector_name",
    "tier",
    "owner_name",
    "status",
    "ehi",
    "delta_month",
    "delta_fytd",
    "last_activity",
    "n_90d",
]


@fragment
def account_table(view: pd.DataFrame) -> None:
    c1, c2 = st.columns([2, 3])
    status = c1.segmented_control(
        "Status", ["On track", "Watch", "At risk"], selection_mode="multi", key="status_pick"
    )
    search = c2.text_input("Search accounts", placeholder="Type part of a name…")
    table = view
    if status:
        table = table[table["status"].isin(status)]
    if search:
        table = table[table["account_name"].str.contains(search, case=False, regex=False)]

    event = st.dataframe(
        table[COLUMNS],
        hide_index=True,
        use_container_width=True,
        height=420,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "account_name": "Account",
            "hub_name": "Hub",
            "sector_name": "Sector",
            "tier": "Tier",
            "owner_name": "Owner",
            "status": "Status",
            "ehi": st.column_config.ProgressColumn("EHI", min_value=0, max_value=100, format="%.1f"),
            "delta_month": st.column_config.NumberColumn("Δ month", format="%+.1f"),
            "delta_fytd": st.column_config.NumberColumn("Δ FYTD", format="%+.1f"),
            "last_activity": st.column_config.DateColumn("Last activity", format="DD MMM YYYY"),
            "n_90d": st.column_config.NumberColumn("Activities (90d)"),
        },
    )

    rows = event.selection.rows if event and event.selection else []
    if rows:
        acc = table.iloc[rows[0]]
        st.markdown(f"#### {acc['account_name']} · {acc['ehi']:.1f} ({acc['status']})")
        comp = pd.DataFrame(
            {
                "Component": ["Recency", "Frequency", "Breadth", "Depth", "Attainment"],
                "Score": [acc[c] for c in ["recency", "frequency", "breadth", "depth", "attainment"]],
            }
        )
        st.bar_chart(comp, x="Component", y="Score", horizontal=True, height=220)
    else:
        st.caption("Select a row to see what is driving that account's score.")

    st.download_button(
        "Download as Excel",
        data=to_excel_bytes({"Accounts": table[COLUMNS]}, notes=filters.describe(chosen)),
        file_name="account_pulse_portfolio.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


account_table(view)
