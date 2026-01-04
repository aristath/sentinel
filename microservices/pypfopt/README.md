# PyPortfolioOpt Microservice

Minimal REST API wrapper for the PyPortfolioOpt library, exposing only the portfolio optimization methods used by the arduino-trader system.

## Overview

This microservice provides a simple JSON API for:
- **Mean-Variance Optimization**: Modern portfolio theory using EfficientFrontier
- **Hierarchical Risk Parity (HRP)**: Machine learning-based portfolio optimization
- **Covariance Matrix Calculation**: Ledoit-Wolf shrinkage estimation
- **Progressive Optimization**: Multi-strategy fallback optimization with constraint relaxation

## Architecture

- **Framework**: FastAPI (async, high-performance)
- **Optimization Library**: PyPortfolioOpt 1.5.5
- **Data Processing**: pandas + numpy
- **Validation**: Pydantic v2
- **Server**: Uvicorn ASGI
- **Container**: Docker multi-stage build

## API Endpoints

### Health Check

```bash
GET /health
```

Returns service health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "pypfopt",
  "version": "1.0.0",
  "timestamp": "2026-01-02T15:30:00Z"
}
```

### Mean-Variance Optimization

```bash
POST /optimize/mean-variance
```

Optimize portfolio using specified strategy (efficient_return, min_volatility, efficient_risk, max_sharpe).

**Request:**
```json
{
  "expected_returns": {"AAPL": 0.12, "MSFT": 0.10},
  "covariance_matrix": [[0.04, 0.02], [0.02, 0.05]],
  "symbols": ["AAPL", "MSFT"],
  "weight_bounds": [[0.02, 0.10], [0.01, 0.08]],
  "sector_constraints": [
    {
      "sector_mapper": {"AAPL": "US", "MSFT": "US"},
      "sector_lower": {"US": 0.50},
      "sector_upper": {"US": 1.00}
    }
  ],
  "strategy": "efficient_return",
  "target_return": 0.11
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "weights": {"AAPL": 0.085, "MSFT": 0.072},
    "strategy_used": "efficient_return",
    "achieved_return": 0.095,
    "achieved_volatility": 0.12
  },
  "error": null,
  "timestamp": "2026-01-02T15:30:00Z"
}
```

**Strategies:**
- `efficient_return`: Maximize return for target (requires `target_return`)
- `min_volatility`: Minimize portfolio volatility
- `efficient_risk`: Maximize return for target volatility (requires `target_volatility`)
- `max_sharpe`: Maximize Sharpe ratio

### Hierarchical Risk Parity (HRP)

```bash
POST /optimize/hrp
```

Optimize portfolio using HRP algorithm (no expected returns needed).

**Request:**
```json
{
  "returns": {
    "dates": ["2025-01-01", "2025-01-02"],
    "data": {
      "AAPL": [0.01, -0.02],
      "MSFT": [0.005, 0.015]
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "weights": {"AAPL": 0.06, "MSFT": 0.08}
  },
  "error": null,
  "timestamp": "2026-01-02T15:30:00Z"
}
```

### Covariance Matrix Calculation

```bash
POST /risk-model/covariance
```

Calculate covariance matrix using Ledoit-Wolf shrinkage.

**Request:**
```json
{
  "prices": {
    "dates": ["2025-01-01", "2025-01-02"],
    "data": {
      "AAPL": [150.0, 151.5],
      "MSFT": [380.0, 382.5]
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "covariance_matrix": [[0.04, 0.02], [0.02, 0.05]],
    "symbols": ["AAPL", "MSFT"]
  },
  "error": null,
  "timestamp": "2026-01-02T15:30:00Z"
}
```

### Progressive Optimization

```bash
POST /optimize/progressive
```

**Main optimization endpoint** used by arduino-trader. Implements robust multi-strategy optimization with automatic constraint relaxation.

**Strategy:**
1. Try each strategy (efficient_return → min_volatility → efficient_risk → max_sharpe) with full constraints
2. If all fail, relax sector constraints by 50% and retry all strategies
3. If all still fail, remove all sector constraints and retry
4. Return first successful result

**Request:** Same as mean-variance endpoint

**Response:**
```json
{
  "success": true,
  "data": {
    "weights": {"AAPL": 0.085, "MSFT": 0.072},
    "strategy_used": "min_volatility",
    "constraint_level": "relaxed",
    "attempts": 3,
    "achieved_return": 0.092,
    "achieved_volatility": 0.11
  },
  "error": null,
  "timestamp": "2026-01-02T15:30:00Z"
}
```

## Running Locally

### Prerequisites
- Python 3.11+
- pip

### Setup

```bash
cd services/pypfopt

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload --port 9001
```

Service will be available at:
- API: http://localhost:9001
- Interactive docs: http://localhost:9001/docs
- OpenAPI spec: http://localhost:9001/openapi.json

## Running with Docker

### Build and Run

```bash
cd services/pypfopt

# Build image
docker build -t pypfopt-service:latest .

# Run container
docker run -d -p 9001:9001 --name pypfopt pypfopt-service:latest
```

### Using Docker Compose

```bash
cd services/pypfopt

# Start service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop service
docker-compose down
```

## Deployment (Arduino)

### Option 1: Docker

```bash
# On Arduino device
docker pull pypfopt-service:latest
docker run -d \
  --name pypfopt \
  --restart unless-stopped \
  -p 9001:9001 \
  pypfopt-service:latest
```

### Option 2: systemd Service

Create `/etc/systemd/system/pypfopt.service`:

```ini
[Unit]
Description=PyPortfolioOpt Microservice
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/services/pypfopt
ExecStart=/home/trader/services/pypfopt/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 9001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable pypfopt
sudo systemctl start pypfopt
sudo systemctl status pypfopt
```

## Integration with Go

Example Go client code:

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

type OptimizeRequest struct {
    ExpectedReturns   map[string]float64     `json:"expected_returns"`
    CovarianceMatrix  [][]float64            `json:"covariance_matrix"`
    Symbols           []string               `json:"symbols"`
    WeightBounds      [][2]float64           `json:"weight_bounds"`
    SectorConstraints []SectorConstraint     `json:"sector_constraints"`
    Strategy          string                 `json:"strategy"`
    TargetReturn      *float64               `json:"target_return,omitempty"`
}

type ServiceResponse struct {
    Success   bool                   `json:"success"`
    Data      map[string]interface{} `json:"data"`
    Error     *string                `json:"error"`
    Timestamp string                 `json:"timestamp"`
}

func CallPyPortfolioOpt(req OptimizeRequest) (map[string]float64, error) {
    jsonData, err := json.Marshal(req)
    if err != nil {
        return nil, err
    }

    resp, err := http.Post(
        "http://localhost:9001/optimize/progressive",
        "application/json",
        bytes.NewBuffer(jsonData),
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
        return nil, fmt.Errorf("optimization failed: %s", *result.Error)
    }

    weights := make(map[string]float64)
    for symbol, weight := range result.Data["weights"].(map[string]interface{}) {
        weights[symbol] = weight.(float64)
    }

    return weights, nil
}
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_api.py -v
```

## Project Structure

```
services/pypfopt/
├── Dockerfile                  # Multi-stage Docker build
├── docker-compose.yml          # Local development setup
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── .env.example               # Environment configuration template
├── app/
│   ├── __init__.py            # Package initialization
│   ├── main.py                # FastAPI application
│   ├── config.py              # Settings management
│   ├── models.py              # Pydantic request/response models
│   ├── service.py             # Core PyPortfolioOpt wrapper
│   └── converters.py          # JSON ↔ pandas DataFrame conversions
└── tests/
    ├── __init__.py
    ├── test_api.py            # API endpoint tests
    ├── test_service.py        # Service logic tests
    ├── test_converters.py     # Converter tests
    └── fixtures/
        └── sample_data.json   # Test data
```

## Performance

- Typical response time: <500ms for portfolios with 10-20 securities
- Memory usage: <100MB
- Concurrent requests: Handled via async FastAPI

## Troubleshooting

### Port already in use

```bash
# Find process using port 9001
lsof -i :9001

# Kill process
kill -9 <PID>
```

### Docker build fails

```bash
# Clean build
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

### Optimization fails

Check logs for specific error:
```bash
# Docker
docker-compose logs pypfopt

# systemd
sudo journalctl -u pypfopt -f
```

Common issues:
- Infeasible constraints (sector bounds too tight)
- Singular covariance matrix (not enough data)
- Invalid weight bounds (min > max)

## License

Part of arduino-trader project. Internal use only.
