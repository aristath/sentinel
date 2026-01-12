# FX_WEEKLY

Weekly time series data for forex currency pairs.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API provides weekly time series data for a specified forex currency pair.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `FX_WEEKLY` |
| `from_symbol` | string | Yes | The base currency (e.g., `EUR`, `USD`, `GBP`) |
| `to_symbol` | string | Yes | The quote currency (e.g., `USD`, `EUR`, `GBP`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Forex Weekly Prices (open, high, low, close)",
        "2. From Symbol": "EUR",
        "3. To Symbol": "USD",
        "4. Last Refreshed": "2024-01-12 16:00:00",
        "5. Time Zone": "UTC"
    },
    "Time Series FX (Weekly)": {
        "2024-01-12": {
            "1. open": "1.0920",
            "2. high": "1.0980",
            "3. low": "1.0880",
            "4. close": "1.0950"
        },
        "2024-01-05": {
            "1. open": "1.0900",
            "2. high": "1.0950",
            "3. low": "1.0850",
            "4. close": "1.0920"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=FX_WEEKLY&from_symbol=EUR&to_symbol=USD&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Weekly forex data aggregated from daily data
- The date represents the end of the trading week
- Use for longer-term forex trend analysis
