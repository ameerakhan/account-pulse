-- Current score per account with its dimensions, last month's score, and the
-- score at the fiscal-year baseline (the last month-end before FY start).

CREATE TABLE account_scores AS
WITH cur AS (
    SELECT * FROM account_snapshots WHERE is_current
),
prev AS (
    SELECT account_id, ehi AS ehi_prev_month
    FROM account_snapshots
    WHERE snap_date = (
        SELECT max(snap_date) FROM account_snapshots
        WHERE snap_date < date_trunc('month', (SELECT max(snap_date) FROM account_snapshots))
    )
),
fy AS (
    SELECT CASE WHEN month(max(snap_date)) >= ${fy_start_month}
                THEN make_date(year(max(snap_date)), ${fy_start_month}, 1)
                ELSE make_date(year(max(snap_date)) - 1, ${fy_start_month}, 1)
           END AS fy_start
    FROM account_snapshots
),
baseline AS (
    SELECT account_id, ehi AS ehi_fy_baseline
    FROM account_snapshots
    WHERE snap_date = (
        SELECT max(snap_date) FROM account_snapshots, fy WHERE snap_date < fy.fy_start
    )
)
SELECT
    a.account_id,
    a.account_name,
    a.tier,
    h.hub_name,
    h.region,
    s.sector_name,
    p.programme_name,
    o.owner_name,
    cur.snap_date AS as_of,
    cur.fiscal_year,
    cur.last_activity,
    cur.n_90d,
    cur.n_fytd,
    round(cur.recency, 1)    AS recency,
    round(cur.frequency, 1)  AS frequency,
    round(cur.breadth, 1)    AS breadth,
    round(cur.depth, 1)      AS depth,
    round(cur.attainment, 1) AS attainment,
    cur.ehi,
    prev.ehi_prev_month,
    round(cur.ehi - prev.ehi_prev_month, 1) AS delta_month,
    baseline.ehi_fy_baseline,
    round(cur.ehi - baseline.ehi_fy_baseline, 1) AS delta_fytd,
    CASE WHEN cur.ehi >= ${on_track} THEN 'On track'
         WHEN cur.ehi >= ${watch}    THEN 'Watch'
         ELSE 'At risk'
    END AS status
FROM cur
JOIN raw.accounts   AS a USING (account_id)
JOIN raw.hubs       AS h USING (hub_id)
JOIN raw.sectors    AS s USING (sector_id)
JOIN raw.programmes AS p USING (programme_id)
JOIN raw.owners     AS o ON o.owner_id = a.owner_id
LEFT JOIN prev     USING (account_id)
LEFT JOIN baseline USING (account_id);
