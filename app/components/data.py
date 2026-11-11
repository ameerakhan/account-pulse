"""Page-facing data access: one shared store per process, warmed at start-up."""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from pulse import freshness
from pulse.queries import ALL_PAGES, BUNDLES
from pulse.warehouse import SharedStore, duckdb_store


@st.cache_resource(show_spinner=False)
def store() -> SharedStore:
    s = duckdb_store()
    s.warm(ALL_PAGES)  # first visitor doesn't pay cold start; nobody queues behind them
    return s


def load(page: str) -> dict[str, pd.DataFrame]:
    """Fetch a page's bundle in parallel, drawing a heartbeat while it is in flight.

    Streamlit only notices a queued rerun (a nav click, a filter change) when
    the script writes an element. A loader that blocks silently starves
    navigation; a heartbeat line gives the runner a chance to react.
    """
    fut = store().warm(BUNDLES[page])
    if fut.done():
        return fut.result()
    beat = st.empty()
    started = time.monotonic()
    while not fut.done():
        beat.caption(f"Loading… {time.monotonic() - started:0.1f}s")
        time.sleep(0.1)
    beat.empty()
    return fut.result()


@st.cache_data(ttl=60, show_spinner=False)
def freshness_banner() -> tuple[bool, str]:
    f = freshness.check()
    return f.ok, f.summary()


def header(title: str, subtitle: str) -> None:
    st.title(title)
    st.caption(subtitle)
    ok, text = freshness_banner()
    (st.caption if ok else st.info)(f"🕒 {text}")
