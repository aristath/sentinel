# GET /api/system/led/display

Get LED display state.

**Description:**
Returns the current state of the LED display including mode, text content, LED colors, and display configuration.

**Request:**
- Method: `GET`
- Path: `/api/system/led/display`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: LED display state object with mode, text, LED states, and configuration

**Error Responses:**
- `500 Internal Server Error`: Service error
