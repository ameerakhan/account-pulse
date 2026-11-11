# Architecture notes

## Layers

| Layer | Lives in | Responsibility |
|---|---|---|
| Source | `data/raw.duckdb` | Raw tables, plus a `_load_log` of when each table landed |
| Marts | `data/marts.duckdb` | Analysis-ready tables, plus a `refresh_log` |
| Library | `pulse/` | Building, scoring, freshness, data access. Never imports Streamlit |
| App | `app/` | Presentation only. Asks the library for named bundles |

Keeping Streamlit out of `pulse/` means the core logic is tested without a UI.
The same library could also back a scheduled job or an API.

## Marts

| Table | Grain | Used by |
|---|---|---|
| `account_snapshots` | account × month-end (+ as-of date) | every other mart |
| `account_scores` | account (current) | Home, Portfolio |
| `hub_summary` | hub | Home, Hub Lens |
| `hub_trend` / `programme_trend` | hub or programme × month-end | Trends |
| `hub_sector_heatmap` | hub × sector | Hub Lens |
| `activity_detail` | activity, last 180 days, pre-joined | Hub Lens |

The trend tables exclude the current partial month, so a half-finished month
never reads as a sudden drop.

The fiscal-year baseline is the last month-end before 1 July. "Change since FY
start" is measured against it.

## Why a staging file, not CREATE OR REPLACE

| | In-place replace | Staging + swap |
|---|---|---|
| A statement fails mid-build | earlier tables are new, later ones are old: a silently mixed state | live file untouched, build raises |
| A mart comes out empty or out of range | served to users | caught by validation, swap aborted |
| Readers during the build | may see partially rebuilt tables | see the old file until one atomic rename |

## SharedStore design

```
bundle(["a","b","c"])          caller thread
   ├─ claim a  → owner  → submit execute(a) to fetch pool
   ├─ claim b  → in flight elsewhere → reuse that Future
   └─ claim c  → cached & fresh      → done Future
   wait on all three Futures
```

- Claims happen in the caller's thread, so a fetch worker only ever runs a
  query. It never blocks waiting on someone else's.
- `warm()` runs bundles on a separate orchestration pool. Sharing one pool
  between bundles and their fetches can deadlock under load, and a regression
  test covers that case.
- The cache key is the statement name plus the data version, `(mtime_ns, inode)`
  of the marts file. A one-hour TTL is a backstop.
- Shared frames are read-only by convention. pandas 3 Copy-on-Write makes
  accidental mutation through derived frames impossible.

### Security note

Sharing data across sessions is safe here because no statement depends on who
is asking. If row-level access is ever added, the user's scope must become
part of the SQL and the cache key. Filtering in page code is not enough,
otherwise one user's rows could be served to another.
