# REALTIME_OPTIONS

Real-time options chain data.

## API Tier

**Free Tier Available**: No
**Premium Required**: Yes

## Description

This API provides real-time U.S. options data, including options chains with optional Greeks and implied volatility. This is a premium endpoint that requires a premium subscription.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `REALTIME_OPTIONS` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "symbol": "IBM",
    "lastRefreshed": "2024-01-15 16:00:00",
    "expirationDates": [
        "2024-01-19",
        "2024-01-26",
        "2024-02-02"
    ],
    "options": {
        "2024-01-19": {
            "calls": [
                {
                    "contractSymbol": "IBM240119C00185000",
                    "strike": "185.00",
                    "lastPrice": "2.50",
                    "bid": "2.45",
                    "ask": "2.55",
                    "volume": "150",
                    "openInterest": "500",
                    "impliedVolatility": "0.25",
                    "delta": "0.55",
                    "gamma": "0.02",
                    "theta": "-0.05",
                    "vega": "0.10",
                    "rho": "0.03"
                }
            ],
            "puts": [
                {
                    "contractSymbol": "IBM240119P00185000",
                    "strike": "185.00",
                    "lastPrice": "1.50",
                    "bid": "1.45",
                    "ask": "1.55",
                    "volume": "100",
                    "openInterest": "300",
                    "impliedVolatility": "0.24",
                    "delta": "-0.45",
                    "gamma": "0.02",
                    "theta": "-0.04",
                    "vega": "0.10",
                    "rho": "-0.03"
                }
            ]
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=REALTIME_OPTIONS&symbol=IBM&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Premium Tier Only**: 75-1200 requests per minute (depending on plan)

## Notes

- **Premium endpoint** - requires a paid subscription
- Real-time data updated during market hours
- Includes Greeks: delta, gamma, theta, vega, rho
- Requires data entitlement through Alpha X Terminal for premium plans
- Standard plans and free accounts will receive placeholder data instead of actual market data
