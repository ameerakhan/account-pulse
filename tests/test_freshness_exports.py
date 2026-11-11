import io
from datetime import date

import pandas as pd

from pulse import freshness, synth
from pulse.exports import to_excel_bytes


def test_fresh_after_build(built):
    raw, marts, _ = built
    f = freshness.check(raw, marts, today=date(2026, 11, 2))
    assert f.built_at is not None
    assert not f.marts_behind_raw
    assert f.ok


def test_detects_raw_reload_after_build(built, tmp_path):
    raw, marts, tables = built
    import shutil

    raw2 = tmp_path / "raw.duckdb"
    shutil.copy(raw, raw2)
    synth.write_raw({"hubs": tables["hubs"]}, raw2)  # a newer load lands
    f = freshness.check(raw2, marts, today=date(2026, 11, 2))
    assert f.marts_behind_raw and not f.ok
    assert "rebuild needed" in f.summary()


def test_stale_source_is_not_ok(built):
    raw, marts, _ = built
    assert not freshness.check(raw, marts, today=date(2027, 1, 1)).ok


def test_missing_marts(tmp_path):
    f = freshness.check(tmp_path / "r.duckdb", tmp_path / "m.duckdb")
    assert not f.ok and "never been built" in f.summary()


def test_excel_export_round_trip():
    df = pd.DataFrame({"account": ["A", "B"], "ehi": [71.2, 48.0]})
    data = to_excel_bytes({"Accounts": df}, notes={"Hub": "All"})
    back = pd.read_excel(io.BytesIO(data), sheet_name=None)
    assert back["Accounts"].equals(df)
    assert back["About"].iloc[0].tolist() == ["Hub", "All"]
