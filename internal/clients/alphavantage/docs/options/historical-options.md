# HISTORICAL_OPTIONS

Historical options chain data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the full historical options chain for a specific symbol on a given date, covering over 15 years of history. It includes implied volatility and common Greeks (delta, gamma, theta, vega, rho).

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `HISTORICAL_OPTIONS` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `date` | string | Yes | The date for which to retrieve options data in format `YYYY-MM-DD` (e.g., `2017-11-15`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "symbol": "IBM",
    "date": "2017-11-15",
    "expirationDates": [
        "2017-11-17",
        "2017-11-24",
        "2017-12-01"
    ],
    "options": {
        "2017-11-17": {
            "calls": [
                {
                    "contractSymbol": "IBM171117C00185000",
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
                    "contractSymbol": "IBM171117P00185000",
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
curl "https://www.alphavantage.co/query?function=HISTORICAL_OPTIONS&symbol=IBM&date=2017-11-15&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Covers over 15 years of historical options data
- Includes Greeks: delta, gamma, theta, vega, rho
- Option chains are sorted by expiration dates, then by strike prices
- Available for all API key tiers
