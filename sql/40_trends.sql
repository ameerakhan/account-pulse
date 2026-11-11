-- Month-end trend series for the trend charts. The as-of row is excluded so a
-- partial month never looks like a sudden drop.

CREATE TABLE hub_trend AS
SELECT
    h.hub_name,
    s.snap_date,
    s.fiscal_year,
    round(avg(s.ehi), 2) AS avg_ehi,
    count(*)             AS accounts
FROM account_snapshots AS s
JOIN raw.accounts AS a USING (account_id)
JOIN raw.hubs     AS h USING (hub_id)
WHERE NOT s.is_current
GROUP BY ALL;

CREATE TABLE programme_trend AS
SELECT
    h.hub_name,
    p.programme_name,
    s.snap_date,
    s.fiscal_year,
    round(avg(s.ehi), 2) AS avg_ehi,
    count(*)             AS accounts
FROM account_snapshots AS s
JOIN raw.accounts   AS a USING (account_id)
JOIN raw.hubs       AS h USING (hub_id)
JOIN raw.programmes AS p USING (programme_id)
WHERE NOT s.is_current
GROUP BY ALL;
