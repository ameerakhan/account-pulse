"""Is what the app shows current? Answers it from data, not from a hard-coded label."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

from . import config


@dataclass(frozen=True)
class Freshness:
    built_at: datetime | None
    data_as_of: date | None
    raw_loaded_at: datetime | None
    marts_behind_raw: bool
    source_age_days: int | None

    @property
    def ok(self) -> bool:
        return (
            self.built_at is not None
            and not self.marts_behind_raw
            and self.source_age_days is not None
            and self.source_age_days <= 7
        )

    def summary(self) -> str:
        if self.built_at is None:
            return "Marts have never been built."
        parts = [f"Data to {self.data_as_of:%d %b %Y}", f"built {self.built_at:%d %b %H:%M} UTC"]
        if self.marts_behind_raw:
            parts.append("raw data has been reloaded since; rebuild needed")
        if self.source_age_days is not None and self.source_age_days > 7:
            parts.append(f"source data is {self.source_age_days} days old")
        return " · ".join(parts)


def check(
    raw_path: Path | None = None,
    marts_path: Path | None = None,
    today: date | None = None,
) -> Freshness:
    raw_path = Path(raw_path or config.RAW_DB)
    marts_path = Path(marts_path or config.MARTS_DB)
    today = today or datetime.now(UTC).date()

    if not marts_path.exists():
        return Freshness(None, None, None, True, None)

    with duckdb.connect(str(marts_path), read_only=True) as con:
        built_at, data_as_of, built_from = con.execute(
            "SELECT built_at, data_as_of, raw_loaded_at FROM refresh_log"
        ).fetchone()

    latest_raw = built_from
    if raw_path.exists():
        with duckdb.connect(str(raw_path), read_only=True) as con:
            (latest_raw,) = con.execute("SELECT max(loaded_at) FROM _load_log").fetchone()

    return Freshness(
        built_at=built_at,
        data_as_of=data_as_of,
        raw_loaded_at=latest_raw,
        marts_behind_raw=latest_raw is not None and built_from is not None and latest_raw > built_from,
        source_age_days=(today - data_as_of).days if data_as_of else None,
    )
