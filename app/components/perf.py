"""Small compatibility shims for Streamlit performance features."""

from __future__ import annotations

import streamlit as st


def fragment(func=None, **kwargs):
    """`st.fragment` when available, otherwise a transparent no-op decorator.

    A fragment reruns on its own when a widget inside it changes, so moving one
    filter redraws one table instead of the whole page.
    """
    impl = getattr(st, "fragment", None)
    if impl is None:
        return func if func is not None else (lambda f: f)
    return impl(func, **kwargs) if func is not None else impl(**kwargs)


def rerun_app() -> None:
    """Full-page rerun, for controls that change what every section shows."""
    try:
        st.rerun(scope="app")
    except TypeError:  # older Streamlit without scope=
        st.rerun()
