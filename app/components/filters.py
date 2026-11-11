"""Sidebar filters whose option lists are derived once per data version."""

from __future__ import annotations

import pandas as pd
import streamlit as st

FILTER_COLUMNS = {
    "hub_name": "Hub",
    "sector_name": "Sector",
    "tier": "Tier",
    "owner_name": "Owner",
}


@st.cache_data(show_spinner=False)
def _options(df: pd.DataFrame, column: str) -> list[str]:
    return sorted(df[column].dropna().unique().tolist())


def sidebar_filters(df: pd.DataFrame, columns=tuple(FILTER_COLUMNS)) -> dict[str, list[str]]:
    st.sidebar.header("Filters")
    chosen: dict[str, list[str]] = {}
    for col in columns:
        if col not in df.columns:
            continue
        chosen[col] = st.sidebar.multiselect(
            FILTER_COLUMNS[col], _options(df[[col]], col), key=f"f_{col}", placeholder="All"
        )
    if st.sidebar.button("Reset filters", use_container_width=True):
        for col in columns:
            st.session_state.pop(f"f_{col}", None)
        st.rerun()
    return chosen


def apply(df: pd.DataFrame, chosen: dict[str, list[str]]) -> pd.DataFrame:
    """Boolean-mask filtering; with Copy-on-Write no defensive .copy() is needed."""
    mask = pd.Series(True, index=df.index)
    for col, values in chosen.items():
        if values and col in df.columns:
            mask &= df[col].isin(values)
    return df[mask]


def describe(chosen: dict[str, list[str]]) -> dict[str, str]:
    return {FILTER_COLUMNS.get(k, k): ", ".join(v) or "All" for k, v in chosen.items()}
