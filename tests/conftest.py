from __future__ import annotations

from pathlib import Path

import pytest

from pulse import materialize, synth


@pytest.fixture(scope="session")
def built(tmp_path_factory) -> tuple[Path, Path, dict]:
    """A small, fully built dataset shared by the whole test session."""
    d = tmp_path_factory.mktemp("pulse")
    raw, marts = d / "raw.duckdb", d / "marts.duckdb"
    tables = synth.generate(synth.SynthSpec(seed=11, n_accounts=80))
    synth.write_raw(tables, raw)
    materialize.build(raw, marts)
    return raw, marts, tables
