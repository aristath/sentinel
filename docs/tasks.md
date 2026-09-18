# Editable folder tasks

The folder-task runtime is a durable, Clara-compatible workflow system used by
Sentinel's AI research pipeline and available for additional local workflows.
It is separate from fixed portfolio jobs.

## Storage and overlays

Bundled tasks live in `sentinel/task_definitions/<task-id>/`. User-owned tasks
and overrides live in `$SENTINEL_HOME/tasks/<task-id>/`, where `SENTINEL_HOME`
defaults to `~/.sentinel`.

When a bundled task is edited, Sentinel copies the complete folder into the
user directory and edits that copy. The user copy then shadows the bundled
definition. Bundled tasks cannot be deleted through the API; disable them or
edit their user overlay. A user-created task can be deleted when it has no
queued or running work.

## Folder format

Every task requires:

```text
task-id/
├── task.json
└── task.js
```

Optional sibling files can be `.js`, `.mjs`, `.py`, `.sh`, `.md`, `.json`, or
`.txt`. `task.js` and `task.json` are protected from file deletion.

Task IDs use lowercase letters, numbers, dots, underscores, and dashes. File
names cannot contain paths.

## `task.json`

Example:

```json
{
  "name": "Analyze Security",
  "description": "Research one security and persist its report.",
  "enabled": false,
  "tags": ["REQUIRES-INPUT"],
  "cwd": "@/tasks/artifacts/{{task-id}}",
  "timeout": 5400,
  "schedule": null,
  "schedulePolicy": {
    "staleAfterSeconds": 86400,
    "runWhen": "idle",
    "priority": 0
  }
}
```

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Display name; defaults to task ID |
| `description` | string | UI/administration description |
| `enabled` | boolean | Allows cron/stale scheduling; manual runs remain explicit |
| `tags` | string array | Classification such as `REQUIRES-INPUT` |
| `cwd` | string | Artifact/working directory; `@/` expands under `$SENTINEL_HOME` |
| `statePath` | string | Optional task-owned state path |
| `timeout` | non-negative seconds | Whole-run timeout; `0`/absent means no task-level timeout |
| `schedule` | string or null | Five-field cron expression |
| `schedulePolicy` | object or null | Staleness scheduling policy |

`{{task-id}}` is replaced in `cwd`. Stale policy supports
`staleAfterSeconds`, `runWhen` (`idle` or `immediate`), and an integer `priority`.

## `task.js` runtime

`task.js` runs as an async JavaScript function in a Node bridge. It receives:

- `prompt(file, options)` — run an LLM prompt file.
- `run(file, options)` — run a sibling JavaScript, Python, or shell helper.
- `tool(name, args, options)` — call an allowed research tool.
- `console` — writes durable log/live-output events.
- `process.env` — task inputs and runtime paths.
- `task.id` and `task.dir` — current definition identity.

Example:

```javascript
const context = JSON.parse(await run("resolve.py", {
  env: { SYMBOL: process.env.symbol || "" },
}));

const result = await prompt("analyze.md", {
  context,
  timeoutSeconds: 600,
  outputType: "json",
});

console.log(result);
```

`prompt` options include `context`, `systemPrompt`, `outputType: "json"`,
`temperature`, `useTools` (default `true`), and `timeoutSeconds`. `run` options
include `cwd`, `env`, and `timeoutSeconds`. Tool calls accept `timeoutSeconds`.

Helper processes receive the task inputs plus:

| Variable | Meaning |
|---|---|
| `SENTINEL_TASKS_HOME` | `$SENTINEL_HOME` task data root |
| `SENTINEL_BASE_URL` | Current Sentinel HTTP base URL |
| `SENTINEL_APP_ROOT` | Repository root |
| `SENTINEL_PYTHON` | Python executable running Sentinel |
| `SENTINEL_URL_SUMMARIZER_BASE_URL` | Configured summarizer URL |
| `TASK_CWD` | Resolved task artifact directory |

## Validation and editing

Validation checks `task.json`, runs `node --check` on `task.js`, and verifies
simple sibling `prompt()`/`run()` file references. It does not execute the task
or prove satellite availability.

The Research > Tasks UI uses CodeMirror for syntax-aware editing. The API is
documented in [Tasks API](api/tasks.md).

Definitions cannot be edited, deleted, or have files changed while that task
has queued or running work. Metadata changes resynchronize schedules.

## Runs, queue, and checkpoints

Manual or scheduled enqueue creates durable queue state in SQLite. The worker:

1. Claims the next eligible item by priority and age.
2. Hashes the complete task folder.
3. Refuses automatic resume if the definition changed mid-run.
4. Stores logs and replaces the live-output event.
5. Checkpoints every successful `prompt`, `run`, or `tool` result by call order.
6. Replays checkpoints after an interrupted run.
7. Marks completion, error, cancellation, or interruption durably.

Deleting `/api/task-runs/{run_id}` means stop/cancel an active run; it does not
erase historical records.

## Bundled AI tasks

| Task | Purpose |
|---|---|
| `refresh-securities-universe` | Write the active security snapshot |
| `schedule-next-security-analysis` | Queue the stalest/missing security analysis |
| `analyze-security` | Build a source-backed profile, security research, per-security external context, report, and summary |
| `rate-security` | Rate one security from its last six months of research memory |
| `rate-portfolio` | Rate the whole eligible universe relative to itself |

See [AI pipeline](ai-pipeline.md) for dependencies and artifacts.
