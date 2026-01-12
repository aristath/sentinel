# FX_MONTHLY

Monthly time series data for forex currency pairs.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API provides monthly time series data for a specified forex currency pair.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `FX_MONTHLY` |
| `from_symbol` | string | Yes | The base currency (e.g., `EUR`, `USD`, `GBP`) |
| `to_symbol` | string | Yes | The quote currency (e.g., `USD`, `EUR`, `GBP`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Forex Monthly Prices (open, high, low, close)",
        "2. From Symbol": "EUR",
        "3. To Symbol": "USD",
        "4. Last Refreshed": "2024-01-31 16:00:00",
        "5. Time Zone": "UTC"
    },
    "Time Series FX (Monthly)": {
        "2024-01-31": {
            "1. open": "1.0920",
            "2. high": "1.1050",
            "3. low": "1.0850",
            "4. close": "1.0980"
        },
        "2023-12-29": {
            "1. open": "1.0900",
            "2. high": "1.1000",
            "3. low": "1.0800",
            "4. close": "1.0920"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=FX_MONTHLY&from_symbol=EUR&to_symbol=USD&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Monthly forex data aggregated from daily data
- The date represents the last trading day of the month
- Use for long-term forex trend analysis
