-- Engagement Health Index per account, at every month-end in the last two
-- years plus the as-of date. Every other mart derives from this table, so the
-- score is defined exactly once.
--
-- Dollar-brace template parameters are filled from pulse/config.py.

CREATE TABLE account_snapshots AS
WITH params AS (
    SELECT max(activity_date) AS as_of FROM raw.activities
),
snap_dates AS (
    SELECT CAST(last_day(CAST(m AS DATE)) AS DATE) AS snap_date
    FROM params,
         generate_series(
             date_trunc('month', as_of) - INTERVAL 24 MONTH,
             date_trunc('month', as_of) - INTERVAL 1 MONTH,
             INTERVAL 1 MONTH
         ) AS g(m)
    UNION
    SELECT as_of FROM params
),
grid AS (
    SELECT
        a.account_id,
        a.tier,
        s.snap_date,
        CASE WHEN month(s.snap_date) >= ${fy_start_month}
             THEN make_date(year(s.snap_date), ${fy_start_month}, 1)
             ELSE make_date(year(s.snap_date) - 1, ${fy_start_month}, 1)
        END AS fy_start
    FROM raw.accounts AS a
    CROSS JOIN snap_dates AS s
    WHERE a.onboarded_date <= s.snap_date
),
activity_windows AS (
    SELECT
        g.account_id,
        g.snap_date,
        max(x.activity_date) AS last_activity,
        count(x.activity_id) FILTER (WHERE x.activity_date > g.snap_date - 90)  AS n_90d,
        count(x.activity_id) FILTER (WHERE x.activity_date > g.snap_date - 180) AS n_180d,
        count(DISTINCT x.activity_type) FILTER (WHERE x.activity_date > g.snap_date - 180) AS types_180d,
        count(x.activity_id) FILTER (
            WHERE x.activity_date > g.snap_date - 180
              AND x.seniority IN (${senior_levels})
        ) AS senior_180d,
        count(x.activity_id) FILTER (WHERE x.activity_date >= g.fy_start) AS n_fytd
    FROM grid AS g
    LEFT JOIN raw.activities AS x
           ON x.account_id = g.account_id
          AND x.activity_date <= g.snap_date
          AND x.activity_date > g.snap_date - 365
    GROUP BY g.account_id, g.snap_date
),
components AS (
    SELECT
        g.account_id,
        g.snap_date,
        'FY' || lpad(CAST((year(g.fy_start) + 1) % 100 AS VARCHAR), 2, '0') AS fiscal_year,
        w.last_activity,
        w.n_90d,
        w.n_fytd,
        CASE WHEN w.last_activity IS NULL THEN 0.0
             ELSE 100.0 * exp(-(g.snap_date - w.last_activity) / ${recency_decay_days})
        END AS recency,
        least(100.0, 100.0 * w.n_90d / t.expected_90d) AS frequency,
        100.0 * w.types_180d / (SELECT count(*) FROM ref_activity_types) AS breadth,
        CASE WHEN w.n_180d = 0 THEN 0.0 ELSE 100.0 * w.senior_180d / w.n_180d END AS depth,
        CASE WHEN coalesce(p.target_activities, 0) = 0 THEN 0.0
             ELSE least(
                 100.0,
                 100.0 * w.n_fytd
                 / (p.target_activities * greatest(1, g.snap_date - g.fy_start + 1) / 365.0)
             )
        END AS attainment
    FROM grid AS g
    JOIN activity_windows AS w USING (account_id, snap_date)
    JOIN ref_tiers AS t ON t.tier = g.tier
    LEFT JOIN raw.plan_targets AS p
           ON p.account_id = g.account_id
          AND p.fiscal_year = 'FY' || lpad(CAST((year(g.fy_start) + 1) % 100 AS VARCHAR), 2, '0')
)
SELECT
    *,
    round(
          ${w_recency}    * recency
        + ${w_frequency}  * frequency
        + ${w_breadth}    * breadth
        + ${w_depth}      * depth
        + ${w_attainment} * attainment,
        1
    ) AS ehi,
    snap_date = (SELECT as_of FROM params) AS is_current
FROM components;
