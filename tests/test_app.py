"""Smoke-test every page headlessly against a real built dataset."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "app"
PAGES = ["Home.py", "pages/1_Portfolio.py", "pages/2_Hub_Lens.py", "pages/3_Trends.py"]


@pytest.fixture(autouse=True)
def point_at_test_data(built, monkeypatch):
    raw, marts, _ = built
    from pulse import config

    monkeypatch.setattr(config, "RAW_DB", raw)
    monkeypatch.setattr(config, "MARTS_DB", marts)


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exceptions(page):
    at = AppTest.from_file(str(APP / page), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    assert at.title


def test_portfolio_filters_and_empty_state():
    at = AppTest.from_file(str(APP / "pages/1_Portfolio.py"), default_timeout=60)
    at.run()
    hub = at.sidebar.multiselect[0]
    first = hub.options[0]
    hub.select(first).run()
    assert not at.exception
    accounts = at.metric[0].value
    assert int(accounts.replace(",", "")) > 0
