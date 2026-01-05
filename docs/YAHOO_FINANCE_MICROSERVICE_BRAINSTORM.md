# Yahoo Finance Microservice - Brainstorming

## Overview

Create a Python microservice (similar to `tradernet`) that wraps `yfinance` and exposes HTTP endpoints. This would:
- Leverage yfinance's proven browser impersonation (which works)
- Keep Go code simple (just HTTP calls)
- Reuse existing microservice infrastructure
- Be easier to maintain (yfinance handles all the Yahoo Finance complexity)

## Architecture

```
Go Application (trader)
    ↓ HTTP calls
Yahoo Finance Microservice (port 9003)
    ↓ Python calls
yfinance library
    ↓ HTTP with browser impersonation
Yahoo Finance API
```

## Structure

```
microservices/yfinance/
├── app/
│   ├── __init__.py
│   ├── config.py          # Settings (port, log level, etc.)
│   ├── health.py           # Health check endpoint
│   ├── main.py             # FastAPI app with routes
│   ├── models.py           # Pydantic request/response models
│   └── service.py          # Core service wrapping yfinance
├── requirements.txt        # yfinance, fastapi, uvicorn, etc.
├── Dockerfile              # Optional (for Docker deployment)
├── docker-compose.yml      # Optional
└── tests/
    ├── __init__.py
    ├── test_api.py
    └── test_service.py
```

## API Endpoints

### 1. Current Price
```
GET /api/quotes/{symbol}
POST /api/quotes/batch
```

### 2. Historical Prices
```
GET /api/historical/{symbol}?period=1y&interval=1d
```

### 3. Fundamental Data
```
GET /api/fundamentals/{symbol}
```

### 4. Analyst Data
```
GET /api/analyst/{symbol}
```

### 5. Security Info
```
GET /api/security/industry/{symbol}
GET /api/security/country-exchange/{symbol}
GET /api/security/product-type/{symbol}
```

### 6. Symbol Conversion
```
POST /api/symbol/convert
Body: { "symbol": "AAPL.US", "target": "yahoo" }
```

## Request/Response Models

### Batch Quotes Request
```python
class BatchQuotesRequest(BaseModel):
    symbols: list[str]  # List of symbols (Tradernet format)
    yahoo_overrides: Optional[dict[str, str]] = None  # symbol -> yahoo_symbol
```

### Batch Quotes Response
```python
class BatchQuotesResponse(BaseModel):
    quotes: dict[str, float]  # symbol -> price
```

### Historical Prices Request
```python
class HistoricalPricesRequest(BaseModel):
    symbol: str
    yahoo_symbol: Optional[str] = None
    period: str = "1y"  # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    interval: str = "1d"  # 1d, 1wk, 1mo
```

### Historical Prices Response
```python
class HistoricalPrice(BaseModel):
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float

class HistoricalPricesResponse(BaseModel):
    symbol: str
    prices: list[HistoricalPrice]
```

## Service Implementation

### Core Service (service.py)
```python
import yfinance as yf
from typing import Optional, Dict, List
from datetime import datetime

class YahooFinanceService:
    """Service wrapping yfinance library."""

    def get_current_price(
        self,
        symbol: str,
        yahoo_symbol: Optional[str] = None
    ) -> Optional[float]:
        """Get current price for a symbol."""
        yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        return info.get("currentPrice") or info.get("regularMarketPrice")

    def get_batch_quotes(
        self,
        symbols: List[str],
        yahoo_overrides: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """Get current prices for multiple symbols."""
        # Convert symbols
        yf_symbols = []
        symbol_map = {}  # yf_symbol -> tradernet_symbol

        for symbol in symbols:
            yf_symbol = self._convert_symbol(
                symbol,
                yahoo_overrides.get(symbol) if yahoo_overrides else None
            )
            yf_symbols.append(yf_symbol)
            symbol_map[yf_symbol] = symbol

        # Use yfinance download for batch efficiency
        data = yf.download(
            tickers=" ".join(yf_symbols),
            period="5d",
            progress=False,
            threads=True,
            auto_adjust=True,
        )

        # Extract prices
        result = {}
        for yf_symbol, tradernet_symbol in symbol_map.items():
            if yf_symbol in data["Close"].columns:
                close_series = data["Close"][yf_symbol].dropna()
                if len(close_series) > 0:
                    result[tradernet_symbol] = float(close_series.iloc[-1].item())

        return result

    def get_historical_prices(
        self,
        symbol: str,
        yahoo_symbol: Optional[str] = None,
        period: str = "1y",
        interval: str = "1d"
    ) -> List[HistoricalPrice]:
        """Get historical OHLCV data."""
        yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period=period, interval=interval)

        result = []
        for date, row in hist.iterrows():
            result.append(HistoricalPrice(
                date=date.to_pydatetime(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
                adj_close=float(row.get("Adj Close", row["Close"])),
            ))

        return result

    def get_fundamental_data(self, symbol: str, yahoo_symbol: Optional[str] = None):
        """Get fundamental analysis data."""
        yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info

        return {
            "symbol": symbol,
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "roe": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "market_cap": info.get("marketCap"),
            "dividend_yield": info.get("dividendYield"),
            "five_year_avg_dividend_yield": info.get("fiveYearAvgDividendYield"),
        }

    def get_analyst_data(self, symbol: str, yahoo_symbol: Optional[str] = None):
        """Get analyst recommendations and price targets."""
        yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info

        recommendation = info.get("recommendationKey", "hold")
        target_price = info.get("targetMeanPrice", 0) or 0
        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0) or 0

        upside_pct = 0.0
        if current_price > 0 and target_price > 0:
            upside_pct = ((target_price - current_price) / current_price) * 100

        rec_scores = {
            "strongBuy": 1.0,
            "buy": 0.8,
            "hold": 0.5,
            "sell": 0.2,
            "strongSell": 0.0,
        }
        recommendation_score = rec_scores.get(recommendation, 0.5)

        return {
            "symbol": symbol,
            "recommendation": recommendation,
            "target_price": target_price,
            "current_price": current_price,
            "upside_pct": upside_pct,
            "num_analysts": info.get("numberOfAnalystOpinions", 0) or 0,
            "recommendation_score": recommendation_score,
        }

    def get_security_industry(self, symbol: str, yahoo_symbol: Optional[str] = None):
        """Get security industry/sector."""
        yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info

        return {
            "symbol": symbol,
            "industry": info.get("industry"),
            "sector": info.get("sector"),
        }

    def get_security_country_exchange(
        self, symbol: str, yahoo_symbol: Optional[str] = None
    ):
        """Get security country and exchange."""
        yf_symbol = self._convert_symbol(symbol, yahoo_symbol)
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info

        return {
            "symbol": symbol,
            "country": info.get("country"),
            "full_exchange_name": info.get("fullExchangeName"),
        }

    def _convert_symbol(self, symbol: str, yahoo_override: Optional[str] = None) -> str:
        """Convert Tradernet symbol to Yahoo symbol."""
        if yahoo_override:
            return yahoo_override

        # Convert Tradernet format to Yahoo format
        if symbol.endswith(".US"):
            return symbol[:-3]  # Remove .US
        if symbol.endswith(".JP"):
            base = symbol[:-3]
            return f"{base}.T"  # Japanese stocks use .T

        return symbol  # European stocks use as-is
```

## Go Client

### Client Structure (similar to tradernet client)
```go
package yahoo

import (
    "encoding/json"
    "fmt"
    "net/http"
    "time"
    "github.com/rs/zerolog"
)

type Client struct {
    baseURL string
    client  *http.Client
    log     zerolog.Logger
}

func NewClient(baseURL string, log zerolog.Logger) *Client {
    return &Client{
        baseURL: baseURL,
        client: &http.Client{
            Timeout: 30 * time.Second,
        },
        log: log.With().Str("client", "yahoo").Logger(),
    }
}

// GetBatchQuotes fetches current prices for multiple symbols
func (c *Client) GetBatchQuotes(
    symbolOverrides map[string]*string,
) (map[string]*float64, error) {
    // Convert to request format
    symbols := make([]string, 0, len(symbolOverrides))
    yahooOverrides := make(map[string]string)

    for symbol, yahooOverride := range symbolOverrides {
        symbols = append(symbols, symbol)
        if yahooOverride != nil {
            yahooOverrides[symbol] = *yahooOverride
        }
    }

    req := BatchQuotesRequest{
        Symbols: symbols,
        YahooOverrides: yahooOverrides,
    }

    resp, err := c.post("/api/quotes/batch", req)
    if err != nil {
        return nil, err
    }

    var result BatchQuotesResponse
    if err := json.Unmarshal(resp.Data, &result); err != nil {
        return nil, fmt.Errorf("failed to parse quotes: %w", err)
    }

    // Convert to map[string]*float64
    quotes := make(map[string]*float64)
    for symbol, price := range result.Quotes {
        p := price
        quotes[symbol] = &p
    }

    return quotes, nil
}
```

## Deployment

### Systemd Service
```ini
[Unit]
Description=Yahoo Finance Python Microservice
Documentation=https://github.com/aristath/arduino-trader
After=network.target
Wants=network.target

[Service]
Type=simple
User=arduino
Group=arduino
WorkingDirectory=/opt/arduino-trader/microservices/yfinance
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="PORT=9003"
ExecStart=/opt/arduino-trader/microservices/yfinance/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 9003
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=yfinance

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

# Resource limits
MemoryMax=512M
CPUQuota=25%

[Install]
WantedBy=multi-user.target
```

### Configuration
```go
// In trader/internal/config/config.go
YahooFinanceServiceURL: getEnv("YAHOO_FINANCE_SERVICE_URL", "http://localhost:9003"),
```

## Benefits

1. **Leverages yfinance's proven browser impersonation** - No need to reimplement
2. **Simple Go code** - Just HTTP calls, no complex cookie/session management
3. **Reuses existing infrastructure** - Same pattern as tradernet microservice
4. **Easy to maintain** - yfinance handles all Yahoo Finance complexity
5. **Isolated failures** - If Yahoo Finance is down, only the microservice is affected
6. **Can be updated independently** - Update yfinance without rebuilding Go app

## Migration Path

1. Create `microservices/yfinance/` directory structure
2. Implement FastAPI service with yfinance wrapper
3. Create Go HTTP client (similar to tradernet client)
4. Update Go code to use new client instead of direct HTTP calls
5. Deploy microservice as systemd service
6. Test and verify
7. Remove old Go Yahoo Finance client code

## Requirements

```txt
yfinance>=0.2.28
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0
python-dateutil==2.8.2
httpx==0.26.0
```

## Next Steps

1. Create microservice structure
2. Implement core service wrapping yfinance
3. Add FastAPI endpoints
4. Create Go HTTP client
5. Update Go code to use new client
6. Deploy and test
