"""Backup API routes."""

from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps

router = APIRouter(prefix="/backup", tags=["backup"])


@router.post("/run")
async def run_backup() -> dict:
    from sentinel.jobs import run_now

    return await run_now("backup:r2")


@router.get("/status")
async def get_backup_status(deps: Annotated[CommonDependencies, Depends(get_common_deps)]) -> dict:
    account_id = await deps.settings.get("r2_account_id", "")
    access_key = await deps.settings.get("r2_access_key", "")
    secret_key = await deps.settings.get("r2_secret_key", "")
    bucket_name = await deps.settings.get("r2_bucket_name", "")

    if not all([account_id, access_key, secret_key, bucket_name]):
        return {"configured": False, "backups": []}

    try:
        from sentinel.jobs.tasks import _get_r2_client

        client = _get_r2_client(account_id, access_key, secret_key)
        response = client.list_objects_v2(Bucket=bucket_name, Prefix="backups/")
        contents = response.get("Contents", [])

        backups = sorted(
            [
                {
                    "key": obj["Key"],
                    "size_bytes": obj.get("Size", 0),
                    "last_modified": obj["LastModified"].isoformat() if obj.get("LastModified") else None,
                }
                for obj in contents
            ],
            key=lambda x: x["last_modified"] or "",
            reverse=True,
        )

        return {"configured": True, "backups": backups}
    except Exception as e:  # noqa: BLE001
        return {"configured": True, "backups": [], "error": str(e)}
