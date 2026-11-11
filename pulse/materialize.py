"""Build the marts database from raw, atomically.

``CREATE OR REPLACE`` in place has an ugly failure mode: when one statement
fails, the previous table survives and the app keeps serving stale numbers
with no visible error. This module avoids that by building every mart into a
fresh staging file, validating it, and only then swapping it over the live
file with ``os.replace`` (atomic on POSIX). A failed build leaves the live
marts exactly as they were and raises.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from string import Template

import duckdb

from . import config

MARTS = (
    "account_snapshots",
    "account_scores",
    "hub_summary",
    "hub_trend",
    "programme_trend",
    "hub_sector_heatmap",
    "activity_detail",
)


class ValidationError(RuntimeError):
    """A mart was built but failed a sanity check; the swap was aborted."""


@dataclass(frozen=True)
class BuildResult:
    path: Path
    seconds: float
    row_counts: dict[str, int]


def template_params(rules: config.ScoringRules = config.RULES) -> dict[str, str]:
    w = rules.weights
    return {
        "fy_start_month": str(config.FISCAL_YEAR_START_MONTH),
        "recency_decay_days": repr(float(rules.recency_decay_days)),
        "senior_levels": ", ".join(f"'{s}'" for s in config.SENIOR_LEVELS),
        "w_recency": repr(w["recency"]),
        "w_frequency": repr(w["frequency"]),
        "w_breadth": repr(w["breadth"]),
        "w_depth": repr(w["depth"]),
        "w_attainment": repr(w["attainment"]),
        "on_track": repr(float(rules.on_track)),
        "watch": repr(float(rules.watch)),
    }


def render_sql(path: Path, params: dict[str, str]) -> str:
    # substitute() (not safe_substitute) so a typo in a placeholder fails loudly.
    return Template(path.read_text()).substitute(params)


def _create_reference_tables(con: duckdb.DuckDBPyConnection, rules: config.ScoringRules) -> None:
    con.execute("CREATE TABLE ref_tiers (tier VARCHAR PRIMARY KEY, expected_90d INTEGER)")
    con.executemany("INSERT INTO ref_tiers VALUES (?, ?)", list(rules.expected_90d.items()))
    con.execute("CREATE TABLE ref_activity_types (activity_type VARCHAR PRIMARY KEY)")
    con.executemany("INSERT INTO ref_activity_types VALUES (?)", [(t,) for t in config.ACTIVITY_TYPES])


def _validate(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in MARTS:
        (n,) = con.execute(f"SELECT count(*) FROM {table}").fetchone()
        if n == 0:
            raise ValidationError(f"{table} is empty")
        counts[table] = n

    (bad,) = con.execute(
        "SELECT count(*) FROM account_snapshots WHERE ehi IS NULL OR ehi < 0 OR ehi > 100"
    ).fetchone()
    if bad:
        raise ValidationError(f"{bad} snapshot rows have an EHI outside 0-100")

    (dupes,) = con.execute("SELECT count(*) - count(DISTINCT account_id) FROM account_scores").fetchone()
    if dupes:
        raise ValidationError(f"account_scores has {dupes} duplicate accounts")

    (raw_accounts,) = con.execute(
        "SELECT count(*) FROM raw.accounts WHERE onboarded_date <= (SELECT max(activity_date) FROM raw.activities)"
    ).fetchone()
    if counts["account_scores"] != raw_accounts:
        raise ValidationError(f"account_scores has {counts['account_scores']} rows, expected {raw_accounts}")
    return counts


def build(
    raw_path: Path | None = None,
    marts_path: Path | None = None,
    rules: config.ScoringRules = config.RULES,
    sql_dir: Path | None = None,
) -> BuildResult:
    raw_path = Path(raw_path or config.RAW_DB)
    marts_path = Path(marts_path or config.MARTS_DB)
    sql_dir = Path(sql_dir or config.SQL_DIR)
    if not raw_path.exists():
        raise FileNotFoundError(f"raw database not found at {raw_path}; run `make data` first")

    staging = marts_path.with_suffix(".staging.duckdb")
    staging.unlink(missing_ok=True)
    params = template_params(rules)
    t0 = time.perf_counter()

    try:
        with duckdb.connect(str(staging)) as con:
            con.execute(f"ATTACH '{raw_path}' AS raw (READ_ONLY)")
            _create_reference_tables(con, rules)

            built_at = datetime.now(UTC).replace(tzinfo=None)
            for sql_file in sorted(sql_dir.glob("*.sql")):
                try:
                    con.execute(render_sql(sql_file, params))
                except duckdb.Error as exc:
                    raise RuntimeError(f"{sql_file.name} failed: {exc}") from exc

            counts = _validate(con)

            con.execute(
                """
                CREATE TABLE refresh_log AS
                SELECT
                    CAST(? AS TIMESTAMP) AS built_at,
                    (SELECT max(activity_date) FROM raw.activities) AS data_as_of,
                    (SELECT max(loaded_at) FROM raw._load_log)      AS raw_loaded_at
                """,
                [built_at],
            )
            con.execute("DETACH raw")
    except BaseException:
        staging.unlink(missing_ok=True)
        raise

    os.replace(staging, marts_path)
    return BuildResult(marts_path, time.perf_counter() - t0, counts)
