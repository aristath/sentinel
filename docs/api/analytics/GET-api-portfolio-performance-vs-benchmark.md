# GET /api/portfolio/performance/vs-benchmark

Get performance vs benchmark.

**Description:**
Compares portfolio performance against a benchmark index (e.g., Euro Stoxx 50, S&P 500).

**Request:**
- Method: `GET`
- Path: `/api/portfolio/performance/vs-benchmark`
- Query Parameters:
  - `benchmark` (optional, string): Benchmark symbol (default: "^STOXX50E")

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "benchmark": "^STOXX50E",
      "portfolio_return": 5.2,
      "benchmark_return": 4.5,
      "alpha": 0.7
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `alpha` (float): Excess return over benchmark

**Error Responses:**
- `500 Internal Server Error`: Service error, benchmark data not available
