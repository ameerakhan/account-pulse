"""The SQL score must equal the independent Python reference, account by account."""

from datetime import date

import duckdb
import pytest

from pulse import config, scoring


def _reference_scores(tables, snap_date):
    acts = tables["activities"]
    targets = tables["plan_targets"].set_index(["account_id", "fiscal_year"])["target_activities"]
    fy = scoring.fiscal_year_label(snap_date)
    out = {}
    for acc in tables["accounts"].itertuples(index=False):
        if acc.onboarded_date > snap_date:
            continue
        rows = acts[acts.account_id == acc.account_id]
        activities = [
            scoring.Activity(r.activity_date, r.activity_type, r.seniority)
            for r in rows.itertuples(index=False)
        ]
        comp = scoring.components(activities, snap_date, acc.tier, targets.get((acc.account_id, fy)))
        out[acc.account_id] = comp.ehi()
    return out


def test_sql_matches_python_reference_at_every_snapshot(built):
    _, marts, tables = built
    with duckdb.connect(str(marts), read_only=True) as con:
        snaps = con.execute("SELECT account_id, snap_date, ehi FROM account_snapshots").df()
    dates = sorted(snaps["snap_date"].dt.date.unique())
    # The as-of date, a FY boundary month and an early month.
    for d in {dates[-1], dates[0], next(x for x in dates if x.month == 7)}:
        expected = _reference_scores(tables, d)
        got = snaps[snaps["snap_date"].dt.date == d].set_index("account_id")["ehi"].to_dict()
        assert got.keys() == expected.keys()
        diffs = {k: (got[k], expected[k]) for k in got if abs(got[k] - expected[k]) > 0.051}
        assert not diffs, f"{d}: {list(diffs.items())[:5]}"


def test_components_edge_cases():
    snap = date(2026, 10, 31)
    empty = scoring.components([], snap, "Core", 24)
    assert empty == scoring.Components(0.0, 0.0, 0.0, 0.0, 0.0)
    assert empty.ehi() == 0.0

    one_today = [scoring.Activity(snap, "Meeting", "Executive")]
    c = scoring.components(one_today, snap, "Emerging", None)
    assert c.recency == pytest.approx(100.0)
    assert c.depth == 100.0
    assert c.attainment == 0.0  # no target -> no credit
    assert c.breadth == pytest.approx(100 / len(config.ACTIVITY_TYPES))


@pytest.mark.parametrize(
    ("d", "label", "start"),
    [
        (date(2026, 6, 30), "FY26", date(2025, 7, 1)),
        (date(2026, 7, 1), "FY27", date(2026, 7, 1)),
        (date(2027, 1, 15), "FY27", date(2026, 7, 1)),
    ],
)
def test_fiscal_year(d, label, start):
    assert scoring.fiscal_year_label(d) == label
    assert scoring.fiscal_year_start(d) == start


@pytest.mark.parametrize(
    ("ehi", "status"), [(70, "On track"), (69.9, "Watch"), (50, "Watch"), (49.9, "At risk")]
)
def test_status_thresholds(ehi, status):
    assert scoring.status(ehi) == status


def test_rules_reject_bad_weights():
    with pytest.raises(ValueError, match="sum to 1.0"):
        config.ScoringRules(
            weights={"recency": 0.5, "frequency": 0.4, "breadth": 0, "depth": 0, "attainment": 0}
        )
