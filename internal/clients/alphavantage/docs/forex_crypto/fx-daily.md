# FX_DAILY

Daily time series data for forex currency pairs.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API provides daily time series data for a specified forex currency pair.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `FX_DAILY` |
| `from_symbol` | string | Yes | The base currency (e.g., `EUR`, `USD`, `GBP`) |
| `to_symbol` | string | Yes | The quote currency (e.g., `USD`, `EUR`, `GBP`) |
| `outputsize` | string | No | Determines the amount of data returned. Valid values: `compact` (default, latest 100 data points), `full` (full-length time series) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Forex Daily Prices (open, high, low, close)",
        "2. From Symbol": "EUR",
        "3. To Symbol": "USD",
        "4. Last Refreshed": "2024-01-15 16:00:00",
        "5. Output Size": "Compact",
        "6. Time Zone": "UTC"
    },
    "Time Series FX (Daily)": {
        "2024-01-15": {
            "1. open": "1.0920",
            "2. high": "1.0950",
            "3. low": "1.0900",
            "4. close": "1.0930"
        },
        "2024-01-14": {
            "1. open": "1.0900",
            "2. high": "1.0925",
            "3. low": "1.0880",
            "4. close": "1.0920"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=EUR&to_symbol=USD&outputsize=full&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Daily forex data for major currency pairs
- Use `outputsize=full` to get complete historical time series
- Data updated daily
