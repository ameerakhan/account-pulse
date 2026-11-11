"""Single source of truth for scoring rules, paths and runtime settings.

The SQL layer reads these values through small reference tables and template
parameters (see ``pulse.materialize``), and the pure-Python reference scorer in
``pulse.scoring`` reads them directly, so the two can never drift apart.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("PULSE_DATA_DIR", ROOT / "data"))
RAW_DB = DATA_DIR / "raw.duckdb"
MARTS_DB = DATA_DIR / "marts.duckdb"
SQL_DIR = ROOT / "sql"

# Fiscal year starts on 1 July: FY27 runs 1 Jul 2026 - 30 Jun 2027.
FISCAL_YEAR_START_MONTH = 7

ACTIVITY_TYPES = (
    "Meeting",
    "Workshop",
    "Site visit",
    "Proposal",
    "Event",
    "Review",
)

SENIORITY_LEVELS = ("Executive", "Senior", "Working")
SENIOR_LEVELS = ("Executive", "Senior")


@dataclass(frozen=True)
class ScoringRules:
    """Weights and thresholds for the Engagement Health Index (EHI, 0-100)."""

    weights: dict[str, float] = field(
        default_factory=lambda: {
            "recency": 0.25,
            "frequency": 0.25,
            "breadth": 0.15,
            "depth": 0.15,
            "attainment": 0.20,
        }
    )
    # Activities expected in a trailing 90 days, by account tier.
    expected_90d: dict[str, int] = field(default_factory=lambda: {"Strategic": 12, "Core": 6, "Emerging": 3})
    recency_decay_days: float = 60.0  # e-folding time of the recency decay
    on_track: float = 70.0
    watch: float = 50.0

    def __post_init__(self) -> None:
        total = round(sum(self.weights.values()), 9)
        if total != 1.0:
            raise ValueError(f"EHI weights must sum to 1.0, got {total}")
        if not self.watch < self.on_track:
            raise ValueError("watch threshold must be below on_track threshold")


RULES = ScoringRules()

# Runtime knobs for the shared data layer.
CACHE_TTL_SECONDS = int(os.environ.get("PULSE_CACHE_TTL", "3600"))
FETCH_WORKERS = int(os.environ.get("PULSE_FETCH_WORKERS", "8"))
# Artificial per-statement latency, used to imitate a remote warehouse in demos.
SIMULATED_LATENCY_S = float(os.environ.get("PULSE_SIM_LATENCY", "0"))
