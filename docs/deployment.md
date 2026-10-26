# Deployment and recovery

The production target is `aristath@clara.local`. Sentinel runs inside the
target's `clara` toolbox container and is managed by a user systemd service on
the host.

## Production contract

| Item | Value |
|---|---|
| Branch | `main` |
| Repository | `/var/home/aristath/sentinel` |
| Container | `clara` |
| Service | `sentinel.service` |
| Bind address | `0.0.0.0` |
| HTTP port | `8000` |
| Health endpoint | `http://clara.local:8000/api/health` |
| Forecast service | `sentinel-forecasting.service`, container-local port `8010` |

Port 8000 is the production application port. High-numbered ports used for
parallel local development are not production configuration.

## What the service does

`systemd/sentinel.service` performs these steps on every start:

1. fetch `origin/main` inside the toolbox;
2. hard-reset the production checkout to `origin/main`;
3. run `uv sync --locked`;
4. execute `.venv/bin/python main.py --host 0.0.0.0`; and
5. restart after a failure.

Consequences:

- Uncommitted production-checkout changes are discarded on service start.
- A release must be committed and pushed to `main`.
- The lock file must represent every required production dependency.
- `web/dist` must be built and committed before the service is restarted.

`sentinel-deploy.timer` checks `origin/main` every minute. If the checked-out
revision differs, it restarts `sentinel.service`, whose pre-start step advances
the checkout.

## Release procedure

Before pushing:

```bash
source .venv/bin/activate
ruff check .
ruff format --check .
pyright
pytest
cd web
npm ci
npm run build
```

Review the diff and commit the source, lock file changes, documentation, and
tracked production bundle together. Push the intended commit to `main`.

To deploy immediately from the repository root:

```bash
scripts/deploy.sh
```

The script restarts the remote user service and waits up to 180 seconds for the
health endpoint. Set `SENTINEL_TARGET` only when deploying to a different SSH
target:

```bash
SENTINEL_TARGET=user@host scripts/deploy.sh
```

## Verification

A successful local build or a green systemd status is not proof that production
serves the intended release. Verify all relevant boundaries:

```bash
ssh aristath@clara.local 'systemctl --user --no-pager --full status sentinel.service'
ssh aristath@clara.local "podman exec --user aristath clara bash -lc 'cd /var/home/aristath/sentinel && git rev-parse HEAD'"
curl --fail --silent http://clara.local:8000/api/health
curl --fail --silent http://clara.local:8000/ | head
```

For a frontend change, confirm that the HTML references the bundle created by
the released revision and exercise the affected interaction in a browser. For a
database, scheduler, broker, AI, or forecasting change, verify the corresponding
real endpoint or job status rather than relying on `/api/health` alone.

Useful logs:

```bash
ssh aristath@clara.local 'journalctl --user -u sentinel.service -n 200 --no-pager'
ssh aristath@clara.local 'journalctl --user -u sentinel-forecasting.service -n 200 --no-pager'
```

## Rollback

Production follows `origin/main`; restarting after manually checking out an old
revision will immediately reset it again. The durable rollback is therefore:

1. revert the bad commit on `main`;
2. rebuild and commit `web/dist` if the reverted change affected the frontend;
3. push the revert; and
4. run `scripts/deploy.sh` and repeat live verification.

Do not use a manual hard reset in a working development checkout as a rollback
procedure.

## BGE-M3 memory migration

The embedding server on port 18200 serves `BAAI/bge-m3`, with 1,024-dimensional
vectors. Sentinel's dedicated target is `sentinel_memories`; its historical
owner value remains `clara`. Existing Granite settings and vectors are not
updated merely by deploying new defaults.

Regenerate the configured owner's records while Sentinel remains online:

```bash
source .venv/bin/activate
python scripts/migrate_memory_embeddings.py --source-collection clara_memories
```

The command creates a separate target, preserves UUIDs and complete payloads,
and leaves the shared source table and other owners untouched. It resumes an
interrupted rebuild by embedding only missing or changed records. The target
is marked with its source, owner, model and dimensions; an unrelated existing
table is rejected rather than overwritten. Empty texts, invalid embeddings or
an incomplete copy prevent activation.

Once current jobs and editable task runs are idle, stop Sentinel's writers and
run the same command with activation enabled:

```bash
python scripts/migrate_memory_embeddings.py \
  --source-collection clara_memories --activate
```

This catches up changed records, verifies every source ID and payload against
the target, and atomically updates `ai_embed_base_url`, `ai_embed_model`,
`ai_embed_dims` and `ai_memory_collection` through Sentinel's database API.
Restart the service after the intended revision is committed and pushed. Account
for `sentinel-deploy.timer` during this brief cutover so an automatic release
cannot restart writers midway through activation.

Verify the running settings, memory count and a real semantic search. Do not
reuse a 768-dimensional column for BGE-M3, and do not delete the old shared
collection as part of this migration. Clara's independent Go-memory rebuild
does not migrate these PostgreSQL records.

## SQLite backup and restore

The default data directory is `data/`, unless `SENTINEL_DATA_DIR` changes it.
Before a risky migration, use the configured R2 backup job or make a filesystem
copy while Sentinel is stopped. SQLite sidecar files are part of the live state:
copy the database, `-wal`, and `-shm` files together when they exist.

For a manual production restore:

1. stop `sentinel.service`;
2. preserve the current database files as a recoverable copy;
3. replace the database and matching sidecars with the selected backup;
4. confirm ownership and permissions;
5. start the service; and
6. verify health plus representative portfolio/settings endpoints.

Never overwrite a database while the application is writing to it. See
[Database](database.md) for ownership and migration rules.

## Forecasting service

Forecasting is a separate optional service. `sentinel-forecasting.service` runs
the Toto provider from `.venv-forecasting` on container-local port 8010. Its
failure must not prevent the main Sentinel API from serving; forecast status and
planner inputs should instead show that no fresh forecast is available.
