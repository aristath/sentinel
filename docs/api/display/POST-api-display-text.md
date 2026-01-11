# POST /api/display/text

Set display text.

**Description:**
Updates the text content displayed on the LED matrix display.

**Request:**
- Method: `POST`
- Path: `/api/display/text`
- Body (JSON):
  ```json
  {
    "text": "New display message"
  }
  ```
  - `text` (string, required): Text to display

**Response:**
- Status: `200 OK` on success
- Body: Success confirmation

**Error Responses:**
- `400 Bad Request`: Invalid request body
- `500 Internal Server Error`: Display update failed

**Side Effects:**
- Updates LED display text immediately
- Display state is updated
