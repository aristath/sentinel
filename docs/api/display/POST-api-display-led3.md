# POST /api/display/led3

Set LED3 RGB color.

**Description:**
Sets the RGB color of LED3 on the display using RGB values (0-255 for each component).

**Request:**
- Method: `POST`
- Path: `/api/display/led3`
- Body (JSON):
  ```json
  {
    "r": 0,
    "g": 255,
    "b": 0
  }
  ```
  - `r` (integer, required): Red component (0-255)
  - `g` (integer, required): Green component (0-255)
  - `b` (integer, required): Blue component (0-255)

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "status": "ok"
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid request body, invalid RGB values
- `500 Internal Server Error`: Display update failed
