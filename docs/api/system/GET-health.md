# GET /health

Health check endpoint.

**Description:**
Returns basic health status of the system. This endpoint is not under `/api` prefix and is used for basic health monitoring.

**Request:**
- Method: `GET`
- Path: `/health`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "status": "healthy",
    "version": "1.0.0",
    "service": "sentinel"
  }
  ```
  - `status` (string): Health status ("healthy")
  - `version` (string): Application version
  - `service` (string): Service name
