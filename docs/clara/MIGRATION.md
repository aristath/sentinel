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

## Rollback

If something goes wrong before step 10:
```bash
sudo systemctl stop sentinel.service
cp ~/sentinel/data/backups/sentinel-before-cntryofrisk-migration-<TIMESTAMP>.db ~/sentinel/data/sentinel.db
cd ~/sentinel && git checkout <previous-commit-sha> && uv sync
sudo systemctl start sentinel.service
```
The old Clara docs at `~/.clara/raw/sentinel/*.md` were not edited by step 9 unless the `scp` succeeded; if needed, restore from this repo's git history at the previous commit.
