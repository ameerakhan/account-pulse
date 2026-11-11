"""Pure-Python reference implementation of the Engagement Health Index.

The production score is computed in SQL (``sql/10_account_snapshots.sql``).
This module re-implements the same definition in plain Python, row by row, so
the test-suite can check the SQL against an independent, readable version of
the rules. If you change one, the tests make you change the other.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from . import config


@dataclass(frozen=True)
class Activity:
    activity_date: date
    activity_type: str
    seniority: str


@dataclass(frozen=True)
class Components:
    recency: float
    frequency: float
    breadth: float
    depth: float
    attainment: float

    def ehi(self, rules: config.ScoringRules = config.RULES) -> float:
        w = rules.weights
        total = sum(w[name] * getattr(self, name) for name in w)
        return round(total, 1)


def fiscal_year_start(d: date) -> date:
    m = config.FISCAL_YEAR_START_MONTH
    return date(d.year if d.month >= m else d.year - 1, m, 1)


def fiscal_year_label(d: date) -> str:
    return f"FY{(fiscal_year_start(d).year + 1) % 100:02d}"


def status(ehi: float, rules: config.ScoringRules = config.RULES) -> str:
    if ehi >= rules.on_track:
        return "On track"
    if ehi >= rules.watch:
        return "Watch"
    return "At risk"


def components(
    activities: Iterable[Activity],
    snap_date: date,
    tier: str,
    target_activities: int | None,
    rules: config.ScoringRules = config.RULES,
) -> Components:
    window = [a for a in activities if snap_date - timedelta(days=365) < a.activity_date <= snap_date]
    last_90 = [a for a in window if a.activity_date > snap_date - timedelta(days=90)]
    last_180 = [a for a in window if a.activity_date > snap_date - timedelta(days=180)]
    fy_start = fiscal_year_start(snap_date)
    fytd = [a for a in window if a.activity_date >= fy_start]

    if window:
        days_since = (snap_date - max(a.activity_date for a in window)).days
        recency = 100.0 * math.exp(-days_since / rules.recency_decay_days)
    else:
        recency = 0.0

    frequency = min(100.0, 100.0 * len(last_90) / rules.expected_90d[tier])
    breadth = 100.0 * len({a.activity_type for a in last_180}) / len(config.ACTIVITY_TYPES)
    depth = (
        100.0 * sum(a.seniority in config.SENIOR_LEVELS for a in last_180) / len(last_180)
        if last_180
        else 0.0
    )
    if not target_activities:
        attainment = 0.0
    else:
        elapsed = max(1, (snap_date - fy_start).days + 1)
        prorated = target_activities * elapsed / 365.0
        attainment = min(100.0, 100.0 * len(fytd) / prorated)

    return Components(recency, frequency, breadth, depth, attainment)
