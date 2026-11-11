"""Every statement the app runs, in one place, grouped by the page that renders it.

Keeping statements here (rather than inline in page code) means the app can
warm every page at start-up, and it makes unused queries easy to spot.
"""

from __future__ import annotations

STATEMENTS: dict[str, str] = {
    "refresh_log": "SELECT * FROM refresh_log",
    "account_scores": "SELECT * FROM account_scores ORDER BY ehi DESC",
    "hub_summary": "SELECT * FROM hub_summary ORDER BY avg_ehi DESC",
    "hub_trend": "SELECT * FROM hub_trend ORDER BY hub_name, snap_date",
    "programme_trend": "SELECT * FROM programme_trend ORDER BY hub_name, programme_name, snap_date",
    "heatmap": "SELECT * FROM hub_sector_heatmap",
    "activity_detail": "SELECT * FROM activity_detail ORDER BY activity_date DESC",
    "status_mix": """
        SELECT hub_name, status, count(*) AS accounts
        FROM account_scores GROUP BY ALL
    """,
}

BUNDLES: dict[str, tuple[str, ...]] = {
    "home": ("refresh_log", "account_scores", "hub_summary", "status_mix"),
    "portfolio": ("refresh_log", "account_scores"),
    "hub_lens": ("refresh_log", "hub_summary", "heatmap", "activity_detail"),
    "trends": ("refresh_log", "hub_trend", "programme_trend"),
}

ALL_PAGES: tuple[str, ...] = tuple(dict.fromkeys(n for b in BUNDLES.values() for n in b))
