# Backup

Base path: `/api/backup`

Manages Cloudflare R2 database backups. Configure R2 credentials via [Settings](settings.md) (`r2_account_id`, `r2_access_key`, `r2_secret_key`, `r2_bucket_name`, `r2_backup_retention_days`).

---

## `POST /api/backup/run`

Triggers an immediate Cloudflare R2 backup (`backup:r2` job).

**Response**
```json
{ "status": "ok", "job_type": "backup:r2" }
```

---

## `GET /api/backup/status`

Returns backup configuration status and a list of existing backups in R2, sorted newest first.

**Response** (configured)
```json
{
  "configured": true,
  "backups": [
    {
      "key": "backups/sentinel-2026-04-27.tar.gz",
      "size_bytes": 204800,
      "last_modified": "2026-04-27T03:00:00+00:00"
    }
  ]
}
```

**Response** (not configured — missing one or more R2 credentials)
```json
{ "configured": false, "backups": [] }
```

When configured but the R2 request fails, `error` is included alongside an empty `backups` list:
```json
{ "configured": true, "backups": [], "error": "NoSuchBucket: ..." }
```
