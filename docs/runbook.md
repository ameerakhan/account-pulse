# Refresh runbook

Three steps. Order matters: build only after the source has landed.

## 1. Check the source is current

```bash
python -m pulse.cli freshness
```

It prints the data's as-of date and when the marts were built. It exits **1**
if raw data has been reloaded since the last build, or if the newest activity
is more than 7 days old. If the source itself is old, rebuilding won't help:
fix the upstream load first.

## 2. Build

```bash
python -m pulse.cli build
```

Prints the row count per mart. A failure names the SQL file that broke, and
the live marts are left exactly as they were. Nothing half-updates.

## 3. Nothing else

The app versions its cache on the marts file, so the next page load picks up
the new build. **No restart is needed.**

## After a refresh, spot-check

- [ ] The banner on Home shows today's build time
- [ ] "Average EHI" delta is not exactly `+0.0` (exactly zero usually means the
      previous month didn't build)
- [ ] The Hub Lens heatmap has no empty cells for hubs and sectors that have accounts
- [ ] One account you know: its score on Portfolio matches its component
      breakdown and its recent activity on Hub Lens

## Scheduling

Run steps 1–2 from any scheduler (cron, Airflow, a Databricks job, GitHub
Actions). Because `freshness` and `build` both return non-zero on failure, the
scheduler's own alerting is enough. A failed build reaches you as an alert, not
as a stale number someone spots in a meeting.

## Rollback

Keep the previous `marts.duckdb` (the build replaces it atomically, so
copying it before step 2 is a complete backup). To roll back, copy it back.
The app picks it up on the next load.
