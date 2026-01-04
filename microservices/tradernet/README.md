# Tradernet Microservice

Lightweight Python microservice wrapping the Tradernet SDK to expose trading and portfolio operations via REST API.

## What It Wraps

- **Library**: tradernet SDK v1.0.5
- **Purpose**: Broker API for trading, portfolio management, and market data

## Why This Service Exists

This microservice enables the Go-based portfolio management system to interact with the Tradernet broker API without requiring a Go SDK. It provides a clean REST API layer that:

1. **Unblocks Go Migration**: Allows 4 key endpoints to migrate from Python to Go
2. **Maintains Python-Only Dependencies**: Keeps complex SDK in lightweight Python container
3. **Simplifies Integration**: Provides consistent REST interface vs. tight SDK coupling
4. **Enables Future Flexibility**: Easy to swap brokers by changing microservice implementation

## API Endpoints

### Trading Operations

#### POST /api/trading/place-order
Execute a trade order.

**Request:**
```json
{
  "symbol": "AAPL.US",
  "side": "BUY",
  "quantity": 10
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "order_id": "12345",
    "symbol": "AAPL.US",
    "side": "BUY",
    "quantity": 10.0,
    "price": 175.50
  },
  "error": null,
  "timestamp": "2026-01-02T15:30:00Z"
}
```

#### GET /api/trading/pending-orders
Get all pending/active orders.

#### GET /api/trading/pending-orders/{symbol}
Check if symbol has pending orders.

#### GET /api/trading/pending-totals
Get total value of pending BUY orders by currency.

---

### Portfolio Operations

#### GET /api/portfolio/positions
Get current portfolio positions with market values.

#### GET /api/portfolio/cash-balances
Get cash balances in all currencies (including negative balances).

#### GET /api/portfolio/cash-total-eur
Get total cash balance converted to EUR.

---

### Transactions

#### GET /api/transactions/cash-movements
Get withdrawal history from broker.

**Note**: Deposits are not available via broker API.

#### GET /api/transactions/cash-flows
Get all cash flow transactions (withdrawals, dividends, fees).

Query params: `limit` (default: 1000, max: 5000)

#### GET /api/transactions/executed-trades
Get executed trade history.

Query params: `limit` (default: 500, max: 1000)

---

### Market Data

#### GET /api/market-data/quote/{symbol}
Get current quote for a symbol.

#### POST /api/market-data/quotes
Get quotes for multiple symbols (batch).

**Request:**
```json
{
  "symbols": ["AAPL.US", "TSLA.US", "GOOGL.US"]
}
```

#### GET /api/market-data/historical/{symbol}
Get historical OHLC data.

Query params:
- `start`: Start date (YYYY-MM-DD, default: 2010-01-01)
- `end`: End date (YYYY-MM-DD, default: today)

---

### Security Lookup

#### GET /api/securities/find
Find security by symbol or ISIN.

Query params:
- `symbol`: Symbol or ISIN to search
- `exchange`: Optional exchange filter

#### GET /api/securities/info/{symbol}
Get security metadata (lot size, min price increment).

---

### Health Check

#### GET /health
Service health and Tradernet connection status.

**Response:**
```json
{
  "status": "healthy",
  "service": "tradernet-service",
  "version": "1.0.0",
  "timestamp": "2026-01-02T15:30:00Z",
  "tradernet_connected": true
}
```

---

## Running Locally

### With Docker (Recommended)

```bash
# Build and run
docker-compose up

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TRADERNET_API_KEY="your-key"
export TRADERNET_API_SECRET="your-secret"

# Run server
uvicorn app.main:app --reload --port 9001
```

---

## Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| TRADERNET_API_KEY | Yes | Tradernet API key | - |
| TRADERNET_API_SECRET | Yes | Tradernet API secret | - |
| PORT | No | Service port | 9001 |
| LOG_LEVEL | No | Logging level | INFO |

---

## Integration with Go Services

### Example Go Client

```go
package tradernet

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

type Client struct {
    baseURL string
    client  *http.Client
}

type ServiceResponse struct {
    Success   bool        `json:"success"`
    Data      interface{} `json:"data"`
    Error     *string     `json:"error"`
    Timestamp string      `json:"timestamp"`
}

type PlaceOrderRequest struct {
    Symbol   string  `json:"symbol"`
    Side     string  `json:"side"`
    Quantity float64 `json:"quantity"`
}

type OrderResult struct {
    OrderID  string  `json:"order_id"`
    Symbol   string  `json:"symbol"`
    Side     string  `json:"side"`
    Quantity float64 `json:"quantity"`
    Price    float64 `json:"price"`
}

func NewClient(baseURL string) *Client {
    return &Client{
        baseURL: baseURL,
        client:  &http.Client{},
    }
}

func (c *Client) PlaceOrder(symbol, side string, quantity float64) (*OrderResult, error) {
    req := PlaceOrderRequest{
        Symbol:   symbol,
        Side:     side,
        Quantity: quantity,
    }

    body, _ := json.Marshal(req)
    resp, err := c.client.Post(
        c.baseURL+"/api/trading/place-order",
        "application/json",
        bytes.NewBuffer(body),
    )
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var result ServiceResponse
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, err
    }

    if !result.Success {
        return nil, fmt.Errorf("order failed: %s", *result.Error)
    }

    var order OrderResult
    dataBytes, _ := json.Marshal(result.Data)
    json.Unmarshal(dataBytes, &order)

    return &order, nil
}
```

### Usage in Go

```go
client := tradernet.NewClient("http://localhost:9001")

order, err := client.PlaceOrder("AAPL.US", "BUY", 10.0)
if err != nil {
    log.Fatal(err)
}

fmt.Printf("Order placed: %s at $%.2f\n", order.OrderID, order.Price)
```

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_api.py

# Run specific test
pytest tests/test_api.py::test_health_check
```

---

## Development

### Project Structure

```
services/tradernet/
├── Dockerfile              # Docker build configuration
├── docker-compose.yml      # Local development setup
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── DESIGN.md              # Detailed API design doc
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI application & endpoints
│   ├── config.py          # Configuration management
│   ├── models.py          # Pydantic request/response models
│   ├── service.py         # Tradernet SDK wrapper
│   └── health.py          # Health check endpoint
└── tests/
    ├── __init__.py
    ├── test_api.py        # API endpoint tests
    └── test_service.py    # Service logic tests
```

### Adding New Endpoints

1. Add Pydantic models to `app/models.py`
2. Add service method to `app/service.py`
3. Add endpoint to `app/main.py`
4. Add tests to `tests/test_api.py`
5. Update this README

---

## Production Deployment

### Docker

```bash
# Build image
docker build -t tradernet-service:1.0.0 .

# Run container
docker run -d \
  -p 9001:9001 \
  -e TRADERNET_API_KEY="your-key" \
  -e TRADERNET_API_SECRET="your-secret" \
  --name tradernet \
  tradernet-service:1.0.0
```

### Health Monitoring

The service includes a health check endpoint that monitors:
- Service availability
- Tradernet API connection status

Use for container orchestration (Kubernetes, Docker Swarm) health probes:

```yaml
healthCheck:
  test: ["CMD", "curl", "-f", "http://localhost:9001/health"]
  interval: 30s
  timeout: 3s
  retries: 3
```

---

## Troubleshooting

### Connection Issues

**Problem**: `tradernet_connected: false` in health check

**Solutions**:
1. Verify `TRADERNET_API_KEY` and `TRADERNET_API_SECRET` are set
2. Check API credentials are valid
3. Ensure network connectivity to Tradernet API
4. Check service logs: `docker-compose logs tradernet`

### API Errors

All endpoints return consistent error format:
```json
{
  "success": false,
  "data": null,
  "error": "Detailed error message",
  "timestamp": "2026-01-02T15:30:00Z"
}
```

Check `error` field for details when `success: false`.

---

## License

Same as parent project.
