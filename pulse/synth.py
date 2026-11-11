"""Deterministic synthetic data for a fictional account-management team.

Nothing here is real: hubs, sectors, programmes, accounts and people are all
generated from a seeded RNG. Each account gets a latent engagement propensity
that drifts over time, so some accounts improve, some decline, and the
dashboards have genuine movement to show.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import duckdb
import numpy as np
import pandas as pd

from . import config

HUBS = [
    ("H01", "Northgate", "North"),
    ("H02", "Riverside", "Central"),
    ("H03", "Harbourview", "Coastal"),
    ("H04", "Highfield", "Central"),
    ("H05", "Westmoor", "West"),
    ("H06", "Eastbrook", "East"),
]

SECTORS = [
    "Advanced Manufacturing",
    "Energy & Utilities",
    "Health & Life Sciences",
    "Digital & Software",
    "Financial Services",
    "Transport & Logistics",
    "Public Sector",
    "Creative Industries",
]

PROGRAMME_THEMES = [
    "Skills Accelerator",
    "Innovation Partnerships",
    "Net Zero Pathways",
    "Data Futures",
    "Talent Pipeline",
    "Applied Research",
]

_ADJ = [
    "Bright",
    "Silver",
    "Northern",
    "Blue",
    "Granite",
    "Summit",
    "Clear",
    "Copper",
    "Evergreen",
    "Iron",
    "Lumen",
    "Maple",
    "Nova",
    "Oak",
    "Pioneer",
    "Quartz",
    "Red",
    "Solid",
    "True",
    "Vertex",
    "Willow",
    "Zenith",
    "Amber",
    "Cobalt",
]
_NOUN = [
    "Harbor",
    "Ridge",
    "Field",
    "Bridge",
    "Peak",
    "Stone",
    "River",
    "Forge",
    "Valley",
    "Point",
    "Grove",
    "Crest",
    "Works",
    "Gate",
    "Lane",
    "Path",
]
_SUFFIX = [
    "Analytics",
    "Engineering",
    "Systems",
    "Health",
    "Logistics",
    "Energy",
    "Labs",
    "Partners",
    "Group",
    "Technologies",
    "Studios",
    "Holdings",
]
_FIRST = [
    "Alex",
    "Sam",
    "Jordan",
    "Priya",
    "Tomas",
    "Leila",
    "Owen",
    "Mei",
    "Ravi",
    "Hannah",
    "Kofi",
    "Isla",
    "Mateo",
    "Zara",
    "Ethan",
    "Nadia",
    "Lucas",
    "Amara",
    "Finn",
    "Yusuf",
    "Elena",
    "Kai",
    "Sofia",
    "Daniel",
    "Aisha",
]
_LAST = [
    "Hart",
    "Okafor",
    "Lindqvist",
    "Patel",
    "Moreno",
    "Fraser",
    "Nakamura",
    "Byrne",
    "Haddad",
    "Kowalski",
    "Mensah",
    "Douglas",
    "Varga",
    "Reyes",
    "Quinn",
]

TIERS = ("Strategic", "Core", "Emerging")
TIER_P = (0.15, 0.45, 0.40)
TIER_RATE = {"Strategic": 4.2, "Core": 2.1, "Emerging": 1.0}  # activities / month


@dataclass(frozen=True)
class SynthSpec:
    seed: int = 7
    n_accounts: int = 420
    n_owners: int = 24
    months: int = 30
    as_of: date = date(2026, 10, 31)


def _fiscal_year(d: date) -> int:
    return d.year + 1 if d.month >= config.FISCAL_YEAR_START_MONTH else d.year


def generate(spec: SynthSpec | None = None) -> dict[str, pd.DataFrame]:
    spec = spec or SynthSpec()
    rng = np.random.default_rng(spec.seed)
    start = (pd.Timestamp(spec.as_of) - pd.DateOffset(months=spec.months)).date()

    hubs = pd.DataFrame(HUBS, columns=["hub_id", "hub_name", "region"])
    sectors = pd.DataFrame(
        {"sector_id": [f"S{i + 1:02d}" for i in range(len(SECTORS))], "sector_name": SECTORS}
    )

    prog_rows = []
    for h_i, (hub_id, hub_name, _) in enumerate(HUBS):
        themes = rng.choice(PROGRAMME_THEMES, size=3, replace=False)
        for j, theme in enumerate(themes):
            prog_rows.append((f"P{h_i + 1}{j + 1}", f"{hub_name} {theme}", hub_id))
    programmes = pd.DataFrame(prog_rows, columns=["programme_id", "programme_name", "hub_id"])

    owner_names = set()
    while len(owner_names) < spec.n_owners:
        owner_names.add(f"{rng.choice(_FIRST)} {rng.choice(_LAST)}")
    owners = pd.DataFrame(
        {
            "owner_id": [f"O{i + 1:03d}" for i in range(spec.n_owners)],
            "owner_name": sorted(owner_names),
            "hub_id": [HUBS[i % len(HUBS)][0] for i in range(spec.n_owners)],
        }
    )

    names: set[str] = set()
    while len(names) < spec.n_accounts:
        names.add(f"{rng.choice(_ADJ)} {rng.choice(_NOUN)} {rng.choice(_SUFFIX)}")
    names_list = sorted(names)
    rng.shuffle(names_list)

    acc_rows = []
    for i, name in enumerate(names_list):
        hub_id = HUBS[rng.integers(len(HUBS))][0]
        progs = programmes.loc[programmes.hub_id == hub_id, "programme_id"].to_numpy()
        hub_owners = owners.loc[owners.hub_id == hub_id, "owner_id"].to_numpy()
        onboard_offset = int(rng.integers(0, spec.months * 30))
        # Most accounts predate the window; a tail onboard during it.
        onboarded = start + timedelta(days=onboard_offset) if rng.random() < 0.2 else start
        acc_rows.append(
            (
                f"A{i + 1:04d}",
                name,
                sectors.sector_id.iloc[rng.integers(len(sectors))],
                hub_id,
                rng.choice(progs),
                rng.choice(hub_owners),
                rng.choice(TIERS, p=TIER_P),
                onboarded,
            )
        )
    accounts = pd.DataFrame(
        acc_rows,
        columns=[
            "account_id",
            "account_name",
            "sector_id",
            "hub_id",
            "programme_id",
            "owner_id",
            "tier",
            "onboarded_date",
        ],
    )

    # Activities: a monthly Poisson process whose rate drifts per account.
    act_rows = []
    month_starts = pd.date_range(start, spec.as_of, freq="MS")
    type_p = np.array([0.34, 0.14, 0.10, 0.12, 0.18, 0.12])
    for acc in accounts.itertuples(index=False):
        base = TIER_RATE[acc.tier] * rng.lognormal(0, 0.35)
        drift = rng.normal(0, 0.035)  # monthly multiplicative trend
        senior_bias = rng.beta(2, 3)
        for m_i, ms in enumerate(month_starts):
            if ms.date() < acc.onboarded_date - timedelta(days=31):
                continue
            rate = max(0.0, base * float(np.exp(drift * m_i)) * rng.lognormal(0, 0.25))
            n = rng.poisson(rate)
            days_in_month = ms.days_in_month
            for _ in range(n):
                d = (ms + pd.Timedelta(days=int(rng.integers(days_in_month)))).date()
                if d > spec.as_of or d < acc.onboarded_date:
                    continue
                r = rng.random()
                seniority = (
                    "Executive" if r < senior_bias * 0.35 else "Senior" if r < senior_bias else "Working"
                )
                act_rows.append(
                    (acc.account_id, d, rng.choice(config.ACTIVITY_TYPES, p=type_p), seniority, acc.owner_id)
                )
    activities = pd.DataFrame(
        act_rows, columns=["account_id", "activity_date", "activity_type", "seniority", "owner_id"]
    ).sort_values(["activity_date", "account_id"], kind="stable", ignore_index=True)
    activities.insert(0, "activity_id", [f"X{i + 1:06d}" for i in range(len(activities))])

    fys = range(_fiscal_year(start), _fiscal_year(spec.as_of) + 1)
    expected_year = {t: v * 4 for t, v in config.RULES.expected_90d.items()}
    targets = pd.DataFrame(
        [
            (acc.account_id, f"FY{fy % 100:02d}", int(round(expected_year[acc.tier] * rng.uniform(0.8, 1.2))))
            for acc in accounts.itertuples(index=False)
            for fy in fys
        ],
        columns=["account_id", "fiscal_year", "target_activities"],
    )

    return {
        "hubs": hubs,
        "sectors": sectors,
        "programmes": programmes,
        "owners": owners,
        "accounts": accounts,
        "activities": activities,
        "plan_targets": targets,
    }


def write_raw(tables: dict[str, pd.DataFrame], path=None) -> None:
    """Write generated tables into the raw database with a load log."""
    path = path or config.RAW_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    loaded_at = datetime.now(UTC).replace(tzinfo=None)
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS _load_log (table_name VARCHAR, loaded_at TIMESTAMP, row_count BIGINT)"
        )
        for name, df in tables.items():
            con.register("_df", df)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _df")
            con.unregister("_df")
            con.execute("INSERT INTO _load_log VALUES (?, ?, ?)", [name, loaded_at, len(df)])
