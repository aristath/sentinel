# TRANGE (True Range)

True Range technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the True Range (TRANGE) values for a given equity. True Range measures volatility by calculating the greatest of: current high-low, absolute value of current high minus previous close, or absolute value of current low minus previous close.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `TRANGE` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "True Range (TRANGE)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Zone": "US/Eastern"
    },
    "Technical Analysis: TRANGE": {
        "2024-01-15": {
            "TRANGE": "2.50"
        },
        "2024-01-14": {
            "TRANGE": "2.25"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=TRANGE&symbol=IBM&interval=daily&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- TRANGE = max(High - Low, |High - Previous Close|, |Low - Previous Close|)
- Accounts for gaps between trading sessions
- No time period parameter needed - calculated per period
- Used as the basis for ATR (Average True Range)
- Higher values indicate greater volatility
