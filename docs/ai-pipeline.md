# AI research pipeline

The AI pipeline researches each security and its specific external context,
stores source-backed artifacts and memories, and writes per-security
`ai_research_multiplier` ratings. Those ratings influence long-term target
weights; deterministic market signals and optional forecasts influence timing.

The pipeline is implemented as bundled editable folder tasks. It is not a
second scheduler or an opaque background daemon.

## Pipeline flow

```text
refresh securities universe
          │
          └──► schedule/analyze stale securities
                       │
                       ├──► security-specific research
                       ├──► per-security external-context research
                       └──► reports/summaries
                                                         │
                                                         ▼
                                          rate individual security
                                                         │
                                                         ▼
                                              rate whole portfolio
                                                         │
                                                         ▼
                                      POST security research ratings
```

The scheduler tasks choose stale units; the analyze tasks gather and distill
evidence; rating tasks turn the current evidence set into relative ratings.
The `rate-portfolio` output is the primary batch update path.

## Research units

The AI API exposes two unit kinds:

- `security`: an active security from the generated universe snapshot.
- `portfolio`: the relative portfolio-rating result.

External context is not a separate research unit. It is derived from each
security's source-backed profile, researched through bounded fixed-month
searches, distilled separately, and stored with that security.

A security is stale when its canonical non-empty `summary.md` is missing or at
least seven days old. The short-cadence scheduler queues stale securities for
analysis. Portfolio rating is eligible only after every security summary is
fresh and the canonical `rate-portfolio/latest.json` result is missing or at
least five days old.

`rate-portfolio` also has a weekly Sunday schedule as a backstop. Its own
preflight applies the same dependency gate before any LLM work: stale security
summaries are queued for analysis, a portfolio result younger than five days is
a no-op, and rating proceeds only when all summaries are fresh and the previous
portfolio result needs refreshing.

## Required services

| Service | Default | Purpose |
|---|---|---|
| OpenAI-compatible LLM | `http://127.0.0.1:8080/v1` | Prompt execution and model discovery |
| SearXNG | `http://127.0.0.1:8888` | Search discovery |
| Browser search | `http://127.0.0.1:8891` | Browser-backed search where required |
| URL summarizer | `http://127.0.0.1:8890` | Fetch and distill sources |
| PostgreSQL/pgvector | `127.0.0.1:5432` | mem0-compatible research memory |
| Embeddings API | `http://127.0.0.1:18200/v1` | Memory similarity and retrieval |

Configure these through [Configuration](configuration.md). Satellite failures
must make the affected task fail visibly; they must not disable portfolio,
trading, or basic status APIs.

## Artifacts

Artifacts live beneath:

```text
$SENTINEL_HOME/tasks/artifacts/
```

Common outputs include:

- `refresh-securities-universe/securities-universe.json`
- per-security `profile.json`, `context.md`, `report.md`, and `summary.md`
- per-security `rating.json`
- portfolio `ratings.json` and `latest.json`

`analyze-security` reuses a source-backed profile for at most 30 days, based on
the profile sidecar's filesystem modification time. Older profiles are rebuilt
before the task generates its research queries. Legacy report profiles are
eligible for migration only while the report itself is no more than 30 days old.

The unit-oriented artifact API allowlists `analysis.md`, `context.md`,
`evidence-pack.md`, `latest.json`, `profile.json`, `rating.json`, `ratings.json`,
`report.md`, and `summary.md`. The Sentinel MCP additionally provides listing,
reading, and searching across the complete generated artifact tree so Research
chat can inspect intermediate `.work` files.

## Memory

Security finalizers submit both security-specific and external-context findings
to `POST /api/memory/dedup-store`. Similarity at or above
`ai_dedup_similarity_threshold` reinforces/skips a duplicate rather than
creating a redundant vector record. Tags and metadata preserve unit context.

Memory is shared with Clara-compatible mem0 data, so database identity,
collection, user ID, embedding model, and vector dimensions must remain aligned.
Changing embedding dimensions without a data migration is incompatible with
existing vectors.

## Monitoring and manual control

The Research modal provides Status, Units, History, Chat, and Tasks views. Chat
uses Sentinel's inherited system prompt and can call the complete Sentinel MCP,
SearXNG MCP, Firefox MCP, URL reader, Bash, and filesystem tools. Equivalent
read-only checks are:

```bash
curl --fail http://localhost:8000/api/ai/status
curl --fail http://localhost:8000/api/ai/units
curl --fail http://localhost:8000/api/ai/history
curl --fail http://localhost:8000/api/tasks
```

`/api/ai/status` reports whether scheduled AI tasks are enabled, the running
unit, queued work, stale/total counts, most stale unit, the last terminal run,
and memory health. `next_tick_at` is currently reserved and returned as `null`.

Queue one analysis through the high-level API:

```http
POST /api/ai/requests
Content-Type: application/json

{"kind":"analyze","unit_kind":"security","unit_key":"AAPL.US"}
```

Use the lower-level tasks API for editing, validation, arbitrary inputs, and run
logs. See [AI API](api/ai.md) and [Tasks API](api/tasks.md).

## Rating semantics

`ai_research_multiplier` is bounded to `0..1`:

- `0`: avoid
- `0.5`: neutral
- `1`: prefer

The stored value defines relative strategic conviction. The fixed decay job
moves stale values toward `0.5` using the configured factor and interval. A
manual/API update refreshes its timestamp and source.

AI ratings never bypass `allow_buy`, `allow_sell`, lot sizing, price validation,
position caps, cash constraints, market state, or `research` mode.

## Failure diagnosis

1. Check `/api/ai/status` for the current/last run and memory error.
2. Inspect `/api/task-runs/{run_id}` for logs, live output, and the stored error.
3. Verify model discovery with `/api/ai/models`.
4. Verify the configured search, summarizer, PostgreSQL, and embedding services.
5. Validate the task with `/api/tasks/{task_id}/validate`.
6. Check that `$SENTINEL_HOME` and its artifact paths are writable.
7. Do not mark a failed task complete or replace its evidence with unsourced
   manual content merely to clear status.
