# ANALYTICS_FIXED_WINDOW

Advanced analytics metrics over a fixed temporal window.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns advanced analytics metrics (e.g., total return, variance, auto-correlation) for a given time series over a fixed temporal window. Supports multiple symbols in a single request.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `ANALYTICS_FIXED_WINDOW` |
| `SYMBOLS` | string | Yes | Comma-separated list of symbols (e.g., `AAPL,MSFT,IBM`). Free API keys support up to 5 symbols; premium keys support up to 50 |
| `RANGE` | string | Yes | Date range for the series. Options: `full`, `{N}day`, `{N}week`, `{N}month`, `{N}year`, `{N}minute`, `{N}hour`, `YYYY-MM-DD`, `YYYY-MM-DDT00:00:00` |
| `INTERVAL` | string | Yes | Time interval. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `DAILY`, `WEEKLY`, `MONTHLY` |
| `CALCULATIONS` | string | Yes | Comma-separated list of analytics metrics. Options: `MIN`, `MAX`, `MEAN`, `MEDIAN`, `CUMULATIVE_RETURN`, `VARIANCE`, `STDDEV`, `MAX_DRAWDOWN`, `HISTOGRAM`, `AUTOCORRELATION`, `COVARIANCE`, `CORRELATION` |
| `OHLC` | string | No | Price field to perform calculations on. Valid values: `open`, `high`, `low`, `close` (default: `close`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Analytics Fixed Window",
        "2. Symbols": "AAPL,MSFT,IBM",
        "3. Interval": "DAILY",
        "4. Range": "1year",
        "5. Calculations": "MEAN,VARIANCE,STDDEV,CUMULATIVE_RETURN"
    },
    "Analytics": {
        "AAPL": {
            "MEAN": "175.50",
            "VARIANCE": "1250.25",
            "STDDEV": "35.36",
            "CUMULATIVE_RETURN": "0.25"
        },
        "MSFT": {
            "MEAN": "420.30",
            "VARIANCE": "3200.50",
            "STDDEV": "56.57",
            "CUMULATIVE_RETURN": "0.18"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=ANALYTICS_FIXED_WINDOW&SYMBOLS=AAPL,MSFT&RANGE=1year&INTERVAL=DAILY&CALCULATIONS=MEAN,VARIANCE,STDDEV&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day, up to 5 symbols per request
- **Premium Tier**: 75-1200 requests per minute, up to 50 symbols per request

## Notes

- Supports multiple symbols in a single request
- Free tier: up to 5 symbols
- Premium tier: up to 50 symbols
- Flexible date range specification
- Multiple calculation types available
- Useful for portfolio analysis and risk metrics
