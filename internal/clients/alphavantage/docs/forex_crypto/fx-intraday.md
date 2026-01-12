# FX_INTRADAY

Intraday time series data for forex currency pairs.

## API Tier

**Free Tier Available**: No
**Premium Required**: Yes

## Description

This API returns intraday time series data (open, high, low, close) for a specified forex currency pair, updated in real-time. This is a premium endpoint.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `FX_INTRADAY` |
| `from_symbol` | string | Yes | The base currency (e.g., `EUR`, `USD`, `GBP`) |
| `to_symbol` | string | Yes | The quote currency (e.g., `USD`, `EUR`, `GBP`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min` |
| `outputsize` | string | No | Determines the amount of data returned. Valid values: `compact` (default, latest 100 data points), `full` (full-length time series) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "FX Intraday (1min) Time Series",
        "2. From Symbol": "EUR",
        "3. To Symbol": "USD",
        "4. Last Refreshed": "2024-01-15 16:00:00",
        "5. Interval": "1min",
        "6. Output Size": "Compact",
        "7. Time Zone": "UTC"
    },
    "Time Series FX (1min)": {
        "2024-01-15 16:00:00": {
            "1. open": "1.0920",
            "2. high": "1.0925",
            "3. low": "1.0918",
            "4. close": "1.0922"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=EUR&to_symbol=USD&interval=5min&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Premium Tier Only**: 75-1200 requests per minute (depending on plan)

## Notes

- **Premium endpoint** - requires a paid subscription
- Real-time forex data during market hours
- Supports major currency pairs
- Use `outputsize=full` to get complete historical intraday time series
