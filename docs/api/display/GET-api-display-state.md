# GET /api/display/state

Get current LED display state.

**Description:**
Returns the current state of the LED display including text content, LED colors, and mode.

**Request:**
- Method: `GET`
- Path: `/api/display/state`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Display state object:
  ```json
  {
    "text": "Portfolio Value: €50,000",
    "led3_color": "green",
    "led4_color": "blue",
    "mode": "portfolio"
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Display service error
