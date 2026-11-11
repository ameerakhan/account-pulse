import os
from pathlib import Path

import duckdb
import pytest

from pulse import materialize


def test_all_marts_built_and_logged(built):
    _, marts, _ = built
    with duckdb.connect(str(marts), read_only=True) as con:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        assert set(materialize.MARTS) <= tables
        built_at, as_of, loaded = con.execute("SELECT * FROM refresh_log").fetchone()
    assert built_at is not None and as_of is not None and loaded is not None


def test_status_matches_thresholds(built):
    _, marts, _ = built
    with duckdb.connect(str(marts), read_only=True) as con:
        bad = con.execute("""
            SELECT count(*) FROM account_scores
            WHERE (status = 'On track' AND ehi < 70)
               OR (status = 'Watch' AND (ehi < 50 OR ehi >= 70))
               OR (status = 'At risk' AND ehi >= 50)
        """).fetchone()[0]
    assert bad == 0


def test_failed_build_leaves_live_marts_untouched(built, tmp_path):
    raw, marts, _ = built
    live = tmp_path / "marts.duckdb"
    live.write_bytes(marts.read_bytes())
    before = (live.stat().st_mtime_ns, live.read_bytes())

    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    for f in sorted(Path(materialize.__file__).parent.parent.joinpath("sql").glob("*.sql")):
        (sql_dir / f.name).write_text(f.read_text())
    (sql_dir / "99_broken.sql").write_text("CREATE TABLE oops AS SELECT no_such_column FROM account_scores;")

    with pytest.raises(RuntimeError, match="99_broken.sql"):
        materialize.build(raw, live, sql_dir=sql_dir)

    assert (live.stat().st_mtime_ns, live.read_bytes()) == before
    assert not live.with_suffix(".staging.duckdb").exists()


def test_validation_failure_aborts_swap(built, tmp_path):
    raw, _, _ = built
    live = tmp_path / "marts.duckdb"
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    src = Path(materialize.__file__).parent.parent / "sql"
    for f in sorted(src.glob("*.sql")):
        text = f.read_text()
        if f.name.startswith("60_"):
            text = text.replace("- 180;", "+ 1;")  # produces an empty mart
        (sql_dir / f.name).write_text(text)

    with pytest.raises(materialize.ValidationError, match="activity_detail is empty"):
        materialize.build(raw, live, sql_dir=sql_dir)
    assert not live.exists()


def test_missing_placeholder_fails_loudly(tmp_path):
    f = tmp_path / "x.sql"
    f.write_text("SELECT ${not_a_param}")
    with pytest.raises(KeyError):
        materialize.render_sql(f, materialize.template_params())


def test_build_is_atomic_replace(built, tmp_path, monkeypatch):
    raw, _, _ = built
    calls = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: (calls.append((a, b)), real(a, b)))
    out = tmp_path / "m.duckdb"
    materialize.build(raw, out)
    assert len(calls) == 1 and Path(calls[0][1]) == out
