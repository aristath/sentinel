# Editable tasks

Base paths: `/api/tasks`, `/api/task-runs`, and `/api/scheduler`

Task definitions live in folders and may be overlaid in `SENTINEL_HOME`. Writes
are rejected while a task has queued or running work. See [Editable tasks](../tasks.md)
for the file format and execution model.

## `GET /api/tasks`

Lists the merged bundled and user task definitions.

## `POST /api/tasks`

Creates a user task folder. Body: `{ "name": "Untitled task" }`. Returns the
created task with status 201 and resynchronizes schedules.

## `GET /api/tasks/{task_id}`

Returns one task definition, including its metadata, effective files, and
validation state. Unknown IDs return 404.

## `PUT /api/tasks/{task_id}`

Saves the task's main `task.js` content from `{ "markdown": "..." }`, then
resynchronizes schedules. This compatibility field is named `markdown` even
though the destination file is JavaScript.

## `DELETE /api/tasks/{task_id}`

Deletes a user-owned task and resynchronizes schedules. Bundled-only tasks
cannot be deleted directly; use an overlay to change their effective metadata.
Returns 204.

## `GET /api/tasks/{task_id}/validate`

Returns task-definition validation without running the task.

## `GET /api/tasks/{task_id}/files`

Lists editable and effective files for one task.

## `POST /api/tasks/{task_id}/files`

Creates a file with status 201:

```json
{
  "name": "prompt.md",
  "content": "Prompt text"
}
```

The filename is restricted by the task-definition layer; paths cannot escape
the task folder.

## `GET /api/tasks/{task_id}/files/{name}`

Returns one task file and its content.

## `PUT /api/tasks/{task_id}/files/{name}`

Replaces one task file from `{ "content": "..." }`. Saving `task.json`
resynchronizes scheduler registrations.

## `DELETE /api/tasks/{task_id}/files/{name}`

Deletes one user-owned task file. Returns 204.

## `PUT /api/tasks/{task_id}/meta`

Updates task metadata from the supplied object and resynchronizes schedules.
The accepted metadata fields and schedule policies are documented in
[Editable tasks](../tasks.md).

## `POST /api/tasks/{task_id}/run`

Queues a run with status 202. The body is optional:

```json
{
  "inputs": {
    "symbol": "AIR.EU"
  }
}
```

## `GET /api/tasks/{task_id}/runs`

Lists runs for one task. `limit` defaults to 50 and is clamped to 1 through 200.

## `GET /api/task-runs/{run_id}`

Returns one queued, running, completed, failed, or stopped run. Unknown IDs
return 404.

## `DELETE /api/task-runs/{run_id}`

Requests cancellation of an active run and returns `{ "status": "stopped" }`.
Unknown or no-longer-active IDs return 404.

## `POST /api/scheduler`

Queues one task or a batch of up to 500 tasks. The body may be one object, an
array, or `{ "items": [...] }`:

```json
{
  "task": "analyze-security",
  "inputs": {
    "symbol": "AIR.EU"
  },
  "title": "Analyze AIR.EU",
  "dedupeKey": "analyze:AIR.EU",
  "priority": 10,
  "eligibleAt": 1788460800000
}
```

`eligibleAt` accepts a Unix timestamp; values that look like seconds are
converted to milliseconds. A single request returns `{ "item": ... }`; a batch
returns `{ "items": [...] }`. Dedupe and eligibility are enforced by the task
runtime.
