-- Activity grain for the drill-down table: the last 180 days only, already
-- joined to its dimensions so the app never joins at request time.

CREATE TABLE activity_detail AS
SELECT
    x.activity_id,
    x.activity_date,
    x.activity_type,
    x.seniority,
    a.account_name,
    a.tier,
    h.hub_name,
    s.sector_name,
    o.owner_name
FROM raw.activities AS x
JOIN raw.accounts AS a USING (account_id)
JOIN raw.hubs     AS h USING (hub_id)
JOIN raw.sectors  AS s USING (sector_id)
JOIN raw.owners   AS o ON o.owner_id = x.owner_id
WHERE x.activity_date > (SELECT max(activity_date) FROM raw.activities) - 180;
