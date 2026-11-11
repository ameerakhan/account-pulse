-- Hub x sector grid: current average EHI and the change since the FY baseline.

CREATE TABLE hub_sector_heatmap AS
SELECT
    hub_name,
    sector_name,
    count(*)                         AS accounts,
    round(avg(ehi), 1)               AS avg_ehi,
    round(avg(delta_fytd), 1)        AS delta_fytd,
    round(100 * avg(CASE WHEN status = 'On track' THEN 1.0 ELSE 0.0 END), 1) AS pct_on_track
FROM account_scores
GROUP BY hub_name, sector_name;
