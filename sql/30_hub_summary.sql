-- One row per hub: portfolio size, average EHI and share on track, now and
-- last month. Feeds the KPI cards and the hub ranking.

CREATE TABLE hub_summary AS
WITH monthly AS (
    SELECT
        a.hub_id,
        s.snap_date,
        count(*)                                   AS accounts,
        avg(s.ehi)                                 AS avg_ehi,
        avg(CASE WHEN s.ehi >= ${on_track} THEN 1.0 ELSE 0.0 END) AS share_on_track
    FROM account_snapshots AS s
    JOIN raw.accounts AS a USING (account_id)
    GROUP BY a.hub_id, s.snap_date
),
ranked AS (
    SELECT *, row_number() OVER (PARTITION BY hub_id ORDER BY snap_date DESC) AS rn
    FROM monthly
)
SELECT
    h.hub_name,
    h.region,
    cur.accounts,
    round(cur.avg_ehi, 1)                                   AS avg_ehi,
    round(100 * cur.share_on_track, 1)                      AS pct_on_track,
    round(cur.avg_ehi - prev.avg_ehi, 1)                    AS delta_avg_ehi,
    round(100 * (cur.share_on_track - prev.share_on_track), 1) AS delta_pct_on_track
FROM ranked AS cur
JOIN ranked AS prev ON prev.hub_id = cur.hub_id AND prev.rn = 2
JOIN raw.hubs AS h ON h.hub_id = cur.hub_id
WHERE cur.rn = 1;
