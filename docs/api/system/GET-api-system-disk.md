# GET /api/system/disk

Get disk usage statistics.

**Description:**
Returns disk usage statistics for data directory, logs directory, backups directory, and available disk space.

**Request:**
- Method: `GET`
- Path: `/api/system/disk`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data_dir_mb": 500.0,
    "logs_dir_mb": 100.0,
    "backups_mb": 200.0,
    "total_mb": 800.0,
    "available_mb": 5000.0
  }
  ```
  - `data_dir_mb` (float): Data directory size in MB
  - `logs_dir_mb` (float): Logs directory size in MB
  - `backups_mb` (float): Backups directory size in MB
  - `total_mb` (float): Total usage in MB
  - `available_mb` (float, optional): Available disk space in MB

**Error Responses:**
- `500 Internal Server Error`: Disk usage check failed
