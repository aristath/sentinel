# POST /api/quantum/multimodal-correction

Calculate multimodal correction.

**Description:**
Calculates multimodal correction factor for probability distributions with high kurtosis. Used for adjusting probabilities in non-normal distributions.

**Request:**
- Method: `POST`
- Path: `/api/quantum/multimodal-correction`
- Body (JSON):
  ```json
  {
    "volatility": 0.20,
    "kurtosis": 5.0
  }
  ```
  - `volatility` (float, required): Volatility value
  - `kurtosis` (float, optional): Kurtosis value

**Response:**
- Status: `200 OK`
- Body: Multimodal correction factor and calculation details

**Error Responses:**
- `400 Bad Request`: Invalid request body
