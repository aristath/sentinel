# Tradernet Microservice - API Design

## Overview

Lightweight Python microservice wrapping the Tradernet SDK to expose trading and portfolio operations via REST API.

**Impact**: Unblocks 4 endpoints in Go migration (trading execution, transactions, cash breakdown, symbol lookup)

---

## Tradernet SDK Methods Used

Found **15 methods** actively used across the codebase:

### Trading Operations (3 methods)
- `place_order(symbol, side, quantity)` - Execute trades
- `get_pending_orders()` - List pending orders
- `has_pending_order_for_symbol(symbol)` - Check if symbol has pending order

### Portfolio & Positions (2 methods)
- `get_portfolio()` - Get current positions
- `get_cash_balances()` - Get cash balances by currency

### Cash Flows & Transactions (3 methods)
- `get_cash_movements()` - Get withdrawal history
- `get_all_cash_flows(limit)` - All cash flow transactions
- `get_total_cash_eur()` - Total cash in EUR

### Market Data (4 methods)
- `get_quote(symbol)` - Get single quote
- `get_quotes_raw(symbols)` - Get batch quotes
- `get_historical_prices(symbol, start, end)` - OHLC data
- `get_executed_trades(limit)` - Trade history

### Security Lookup (3 methods)
- `find_symbol(symbol, exchange)` - Symbol/ISIN lookup
- `get_security_info(symbol)` - Security metadata (lot size)
- `get_pending_order_totals()` - Total pending order values by currency

---

## REST API Endpoints

All endpoints follow the blueprint's standard response format:

```json
{
  "success": bool,
  "data": any | null,
  "error": str | null,
  "timestamp": "2026-01-02T15:30:00Z"
}
```

### 1. Trading Operations

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
  }
}
```

#### GET /api/trading/pending-orders
Get all pending/active orders.

**Response:**
```json
{
  "success": true,
  "data": {
    "orders": [
      {
        "id": "67890",
        "symbol": "TSLA.US",
        "side": "buy",
        "quantity": 5.0,
        "price": 250.00,
        "currency": "USD"
      }
    ]
  }
}
```

#### GET /api/trading/pending-orders/{symbol}
Check if symbol has any pending orders.

**Response:**
```json
{
  "success": true,
  "data": {
    "has_pending": true,
    "symbol": "AAPL.US"
  }
}
```

#### GET /api/trading/pending-totals
Get total value of pending BUY orders grouped by currency.

**Response:**
```json
{
  "success": true,
  "data": {
    "totals": {
      "EUR": 1500.00,
      "USD": 500.00
    }
  }
}
```

---

### 2. Portfolio Operations

#### GET /api/portfolio/positions
Get current portfolio positions.

**Response:**
```json
{
  "success": true,
  "data": {
    "positions": [
      {
        "symbol": "AAPL.US",
        "quantity": 10.0,
        "avg_price": 170.00,
        "current_price": 175.50,
        "market_value": 1755.00,
        "market_value_eur": 1623.45,
        "unrealized_pnl": 55.00,
        "currency": "USD",
        "currency_rate": 1.081
      }
    ]
  }
}
```

#### GET /api/portfolio/cash-balances
Get cash balances in all currencies (including negative and TEST).

**Response:**
```json
{
  "success": true,
  "data": {
    "balances": [
      {"currency": "EUR", "amount": 1250.00},
      {"currency": "USD", "amount": -50.00},
      {"currency": "TEST", "amount": 10000.00}
    ]
  }
}
```

#### GET /api/portfolio/cash-total-eur
Get total cash balance converted to EUR.

**Response:**
```json
{
  "success": true,
  "data": {
    "total_eur": 1203.75
  }
}
```

---

### 3. Transactions & Cash Flows

#### GET /api/transactions/cash-movements
Get withdrawal history (deposits not available via API).

**Response:**
```json
{
  "success": true,
  "data": {
    "total_withdrawals": 5000.00,
    "withdrawals": [
      {
        "transaction_id": "W123",
        "date": "2025-12-15",
        "amount": 2000.00,
        "currency": "EUR",
        "amount_eur": 2000.00,
        "status": "completed"
      }
    ],
    "note": "Deposits are not available via API"
  }
}
```

#### GET /api/transactions/cash-flows
Get all cash flow transactions (withdrawals, dividends, coupons, fees).

**Query params:** `limit` (default: 1000)

**Response:**
```json
{
  "success": true,
  "data": {
    "transactions": [
      {
        "transaction_id": "T456",
        "type_doc_id": "dividend",
        "transaction_type": "Dividend Payment",
        "date": "2025-12-20",
        "amount": 50.00,
        "currency": "USD",
        "amount_eur": 46.25,
        "status": "completed",
        "description": "AAPL dividend"
      }
    ]
  }
}
```

#### GET /api/transactions/executed-trades
Get executed trade history.

**Query params:** `limit` (default: 500)

**Response:**
```json
{
  "success": true,
  "data": {
    "trades": [
      {
        "order_id": "98765",
        "symbol": "AAPL.US",
        "side": "BUY",
        "quantity": 10.0,
        "price": 175.50,
        "executed_at": "2025-12-28T14:30:00"
      }
    ]
  }
}
```

---

### 4. Market Data

#### GET /api/market-data/quote/{symbol}
Get current quote for a symbol.

**Response:**
```json
{
  "success": true,
  "data": {
    "symbol": "AAPL.US",
    "price": 175.50,
    "change": 2.30,
    "change_pct": 1.33,
    "volume": 45000000,
    "timestamp": "2026-01-02T15:30:00Z"
  }
}
```

#### POST /api/market-data/quotes
Get quotes for multiple symbols (batch).

**Request:**
```json
{
  "symbols": ["AAPL.US", "TSLA.US", "GOOGL.US"]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "quotes": {
      "AAPL.US": {...},
      "TSLA.US": {...}
    }
  }
}
```

#### GET /api/market-data/historical/{symbol}
Get historical OHLC data.

**Query params:**
- `start`: Start date (YYYY-MM-DD, default: 2010-01-01)
- `end`: End date (YYYY-MM-DD, default: today)

**Response:**
```json
{
  "success": true,
  "data": {
    "symbol": "AAPL.US",
    "candles": [
      {
        "date": "2025-12-27",
        "open": 173.00,
        "high": 176.00,
        "low": 172.50,
        "close": 175.50,
        "volume": 48000000
      }
    ]
  }
}
```

---

### 5. Security Lookup

#### GET /api/securities/find
Find security by symbol or ISIN.

**Query params:**
- `symbol`: Symbol or ISIN to search
- `exchange`: Optional exchange filter

**Response:**
```json
{
  "success": true,
  "data": {
    "found": [
      {
        "symbol": "AAPL.US",
        "name": "Apple Inc",
        "isin": "US0378331005",
        "currency": "USD",
        "market": "NASDAQ",
        "exchange_code": "US"
      }
    ]
  }
}
```

#### GET /api/securities/info/{symbol}
Get security metadata (lot size, etc.).

**Response:**
```json
{
  "success": true,
  "data": {
    "symbol": "AAPL.US",
    "lot": 1,
    "min_price_increment": 0.01,
    "currency": "USD"
  }
}
```

---

### 6. Health Check

#### GET /health
Health check endpoint (required by blueprint).

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

## Implementation Notes

### Authentication
- Service will use Tradernet API credentials from environment variables
- Single connection shared across all requests (singleton pattern)
- Connection established on startup, health check monitors connection status

### Research Mode Support
- Automatically injects TEST currency in research mode
- Returns mock order results when `TRADING_MODE=research`
- Uses settings database to get virtual_test_cash amount

### Error Handling
- All connection errors return `success: false` with clear error messages
- No crashes - degrade gracefully
- Log all errors with context

### LED Indicator Integration
- All Tradernet API calls wrapped in `led_api_call()` context manager
- Maintains LED status updates for visual feedback

### Exchange Rate Integration
- Automatically converts currencies to EUR where needed
- Uses ExchangeRateService for all conversions
- Handles negative balances correctly

---

## Dependencies

```txt
tradernet==1.0.5
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0
python-dateutil==2.8.2
```

---

## Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| TRADERNET_API_KEY | Yes | Tradernet API key | - |
| TRADERNET_API_SECRET | Yes | Tradernet API secret | - |
| PORT | No | Service port | 9001 |
| LOG_LEVEL | No | Logging level | INFO |
| TRADING_MODE | No | Trading mode (production/research) | production |

---

## Port Allocation

**Port 9001** - Tradernet microservice

Other planned microservices:
- Port 9002 - Yahoo Finance microservice
- Port 9003 - PyFolio Analytics microservice

---

## Go Integration Example

```go
type TradernetClient struct {
    baseURL string
    client  *http.Client
}

func (c *TradernetClient) PlaceOrder(symbol, side string, quantity float64) (*OrderResult, error) {
    req := map[string]interface{}{
        "symbol":   symbol,
        "side":     side,
        "quantity": quantity,
    }

    resp, err := c.post("/api/trading/place-order", req)
    if err != nil {
        return nil, err
    }

    if !resp.Success {
        return nil, fmt.Errorf("order failed: %s", resp.Error)
    }

    var result OrderResult
    if err := mapstructure.Decode(resp.Data, &result); err != nil {
        return nil, err
    }

    return &result, nil
}
```

---

## Success Criteria

- ✅ All 15 Tradernet methods exposed via REST API
- ✅ Consistent response format across all endpoints
- ✅ Health check with connection status
- ✅ Research mode support preserved
- ✅ LED indicator integration maintained
- ✅ Comprehensive error handling
- ✅ Docker container builds successfully
- ✅ Integration tests verify equivalence with Python client
