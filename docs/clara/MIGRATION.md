# Manual deployment checklist

This document lists the steps you (the user) need to do manually on the live device (`192.168.1.229`) after merging the "auto-fill geography/industry from Tradernet + retire allocation targets" change. None of this is automated — the dev box never touches the live deployment.

## Summary of what changed

- `geography` and `industry` on `securities` rows are now populated by the `sync:metadata` job from Tradernet's `attributes.CntryOfRisk` (ISO-2 country of risk) and `sector_code` (TRBC industry name). They are no longer accepted by the API and no longer editable in the web UI.
- ETFs (`instr_kind_c == 7`) get **blank** `geography` and `industry` so they fall out of Clara's macro-bucket grouping.
- The `allocation_targets` feature is gone end-to-end: table dropped, DB methods removed, endpoints removed, planner's diversification scorer removed, web UI editor + radar wrapper removed. `RadarChart.jsx` is kept as a reusable primitive but has no current consumer.
- The orphan `aggregates.py` + `aggregate:compute` job are deleted.
- `Portfolio.get_allocations()` and the `allocations` field on `GET /api/portfolio` are deleted.
- The `diversification_impact_pct` setting is removed.

Clara's task contract (`GET /api/securities` returning `{symbol, name, geography, industry}` + `POST /api/securities/preference`) is preserved — Clara's task files need **no edits**.

## Steps to deploy on the live device

> **WARNING:** All of the following touch the live device. Do these by hand; do not let an agent automate them.

1. **Snapshot the live DB first** (always cheap insurance):
   ```bash
   ssh aristath@192.168.1.229
   cp ~/sentinel/data/sentinel.db ~/sentinel/data/backups/sentinel-before-cntryofrisk-migration-$(date +%Y%m%d-%H%M%S).db
   ```

2. **Stop the service**:
   ```bash
   sudo systemctl stop sentinel.service
   ```

3. **Pull and install the new code**:
   ```bash
   cd ~/sentinel
   git pull
   uv sync
   ```

4. **Drop the `allocation_targets` table from the live DB.** The schema migration in the new code is `CREATE TABLE IF NOT EXISTS`, so the old table won't be removed automatically. Run:
   ```bash
   sqlite3 ~/sentinel/data/sentinel.db "DROP TABLE IF EXISTS allocation_targets;"
   ```

5. **Optional pre-sync wipe** (recommended — guarantees a clean first sync):
   ```bash
   sqlite3 ~/sentinel/data/sentinel.db "UPDATE securities SET geography='', industry='';"
   ```

6. **Start the service**:
   ```bash
   sudo systemctl start sentinel.service
   sudo systemctl status sentinel.service
   ```

7. **Trigger the metadata sync once manually** (the regular job will also fire on its schedule):
   ```bash
   curl -X POST http://localhost:8000/api/jobs/sync:metadata/run
   ```
   Wait ~6–8 minutes for completion (one `getAllSecurities` filter call per ticker, paced at 6s/iter to stay under Tradernet's sustained rate limit; back-off on 429 adds another 60s if hit).

8. **Spot-check the result**:
   ```bash
   sqlite3 ~/sentinel/data/sentinel.db "SELECT symbol, geography, industry FROM securities WHERE active=1 ORDER BY symbol LIMIT 20;"
   ```
   Expect ISO-2 country codes (e.g. `US`, `GR`, `CN`, `DE`) for stocks and blanks for ETFs (`VWCE.EU`, `VUAA.EU`, `WSML.EU`, `SXR8.EU`, `AETF.GR`).

9. **Copy the updated Clara API docs** from this repo to the live Clara workspace:
   ```bash
   scp docs/clara/sentinel/securities.md aristath@192.168.1.229:~/.clara/raw/sentinel/securities.md
   scp docs/clara/sentinel/portfolio.md  aristath@192.168.1.229:~/.clara/raw/sentinel/portfolio.md
   ssh aristath@192.168.1.229 'rm -f ~/.clara/raw/sentinel/allocation.md'
   ```

10. **No Clara task edits are required.** The `~/.clara/tasks/*.md` files consume the preserved contract and will keep working. The next `refresh-securities-universe` idle tick (within ~8 h) will repopulate `securities-universe.json` and `macro-buckets.json` with the new shapes.

11. **Sanity check the new bucket cardinality** (after step 10's refresh runs):
    ```bash
    ssh aristath@192.168.1.229 'jq length ~/.clara/users/ari/scratchpad/tasks/macro-buckets.json'
    ```
    Expect roughly 25–50 buckets (was probably <15 with the coarse manual labels). ETFs and unclassified Kazakh rows will be absent.

---

# Second batch — composition + benchmarks + planner blend refactor

This second section covers the 6 commits that landed after the geography/industry migration (range `36808f7e..HEAD`).

## Summary of what changed (second batch)

- **Benchmarks** (`benchmarks` + `benchmark_prices` tables) — new market-indices store, fully separate from `securities`/`prices`. Populated by the new `sync:benchmarks` job (daily). Auto-discovers any new `.IDX` entry Tradernet exposes.
- **`instr_kind_c`** is now a first-class column on `securities`. The migration auto-backfills it from `quote_data.kind` so existing rows light up immediately. Persisted on every `sync:metadata` run going forward.
- **Composition module** + `GET /api/portfolio/composition` endpoint — local replacement for the (now-broken) Freedom24 PRAAMS surface. Returns country/continent/industry/currency/asset-class breakdowns + risk-return metrics + benchmarks beta table.
- **Planner blend refactor** — `calculate_ideal_portfolio` now produces one unified score per security: `0.8 × clara_share + 0.2 × algo_share`. The "Clara sleeve / baseline sleeve" sleeve-split is gone; the global `clara_preferences_updated_at` setting and the read-time `effective_user_multiplier` fade are gone. Replaced by a daily `decay:user_multipliers` job that physically nudges each row's stored slider toward 0.5 by `value = 0.5 + (value − 0.5) × 0.9` after 7 days of no human touch.
- **Web UI** — composition card now renders bipolar deviation-from-ideal radars (country + industry, current vs post-plan), risk/return card switched from radar to a stack of deviation bars, SecurityAllocationCard gained an ideal-marker + sort/show toggles.

Clara's task contract is unchanged (`GET /api/securities` still returns `user_multiplier`, `geography`, `industry`). The deleted `effective_user_multiplier` field was internal-only — Clara doesn't consume it.

## Steps to deploy (second batch)

1. **Snapshot the live DB**:
   ```bash
   ssh aristath@192.168.1.229
   cp ~/sentinel/data/sentinel.db ~/sentinel/data/backups/sentinel-before-composition-migration-$(date +%Y%m%d-%H%M%S).db
   ```

2. **Stop the service**:
   ```bash
   sudo systemctl stop sentinel.service
   ```

3. **Pull and install**:
   ```bash
   cd ~/sentinel && git pull && uv sync
   ```

4. **Drop now-obsolete settings** (the planner no longer reads them; leaving them in is harmless but noisy):
   ```bash
   sqlite3 ~/sentinel/data/sentinel.db "DELETE FROM settings WHERE key IN ('clara_preference_weekly_fade', 'clara_preferences_updated_at');"
   ```

5. **Start the service**:
   ```bash
   sudo systemctl start sentinel.service
   ```
   On startup the schema migration auto-runs and creates `benchmarks` + `benchmark_prices` tables, adds the `instr_kind_c` column, and backfills it from `quote_data.kind`.

6. **Trigger the benchmarks sync once manually** (the daily job will also fire on its schedule, but the initial roster + 5-year price history takes ~5 min and is nicer to do hands-on):
   ```bash
   curl -X POST http://localhost:8000/api/jobs/sync:benchmarks/run
   ```
   Expect ~51 indices to land and roughly half to get prices (Tradernet has price history for most US/EU indices; some FORTS and TABADUL entries may be price-less).

7. **Spot-check the new tables and column**:
   ```bash
   sqlite3 ~/sentinel/data/sentinel.db "SELECT COUNT(*) FROM benchmarks; SELECT COUNT(*) FROM benchmark_prices; SELECT instr_kind_c, COUNT(*) FROM securities WHERE active=1 GROUP BY instr_kind_c;"
   ```
   Expect ~50 benchmarks, some thousands of benchmark prices, and `instr_kind_c` distribution roughly 1=stocks, 7=ETFs, 10=DRs.

8. **Verify the new composition endpoint**:
   ```bash
   curl -s http://localhost:8000/api/portfolio/composition | jq '.metrics, .composition.by_country, (.benchmarks | length)'
   ```

9. **No Clara task edits required.** The `~/.clara/tasks/*.md` files consume `user_multiplier` (still present) and `geography`/`industry` (still present). The internal-only `effective_user_multiplier` and `clara_freshness` fields don't appear in any Clara contract.

## Rollback (second batch)

Same shape as the first batch — restore the snapshot from step 1, `git checkout` the previous SHA, `uv sync`, restart. The new `benchmarks` + `benchmark_prices` tables are independent of any other state and can be left in place after rollback (they're just unused storage).

---

# First batch rollback (still applies)

## Rollback

If something goes wrong before step 10:
```bash
sudo systemctl stop sentinel.service
cp ~/sentinel/data/backups/sentinel-before-cntryofrisk-migration-<TIMESTAMP>.db ~/sentinel/data/sentinel.db
cd ~/sentinel && git checkout <previous-commit-sha> && uv sync
sudo systemctl start sentinel.service
```
The old Clara docs at `~/.clara/raw/sentinel/*.md` were not edited by step 9 unless the `scp` succeeded; if needed, restore from this repo's git history at the previous commit.
