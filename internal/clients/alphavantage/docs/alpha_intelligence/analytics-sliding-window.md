# ANALYTICS_SLIDING_WINDOW

Advanced analytics metrics over sliding time windows.

## API Tier

**Free Tier Available**: Yes  
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns advanced analytics metrics for time series over sliding time windows. Calculates metrics for each window as it slides through the time series.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `ANALYTICS_SLIDING_WINDOW` |
| `SYMBOLS` | string | Yes | Comma-separated list of symbols (e.g., `AAPL,MSFT,IBM`). Free API keys support up to 5 symbols; premium keys support up to 50 |
| `RANGE` | string | Yes | Date range for the series. Options: `full`, `{N}day`, `{N}week`, `{N}month`, `{N}year`, `{N}minute`, `{N}hour`, `YYYY-MM-DD`, `YYYY-MM-DDT00:00:00` |
| `INTERVAL` | string | Yes | Time interval. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `DAILY`, `WEEKLY`, `MONTHLY` |
| `WINDOW_SIZE` | integer | Yes | Size of the sliding window (e.g., `20` for a 20-day window) |
| `CALCULATIONS` | string | Yes | Comma-separated list of analytics metrics. Options: `MIN`, `MAX`, `MEAN`, `MEDIAN`, `CUMULATIVE_RETURN`, `VARIANCE`, `STDDEV`, `MAX_DRAWDOWN`, `HISTOGRAM`, `AUTOCORRELATION`, `COVARIANCE`, `CORRELATION` |
| `OHLC` | string | No | Price field to perform calculations on. Valid values: `open`, `high`, `low`, `close` (default: `close`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Analytics Sliding Window",
        "2. Symbols": "AAPL",
        "3. Interval": "DAILY",
        "4. Range": "1year",
        "5. Window Size": 20,
        "6. Calculations": "MEAN,STDDEV"
    },
    "Analytics": {
        "AAPL": {
            "2024-01-15": {
                "MEAN": "175.50",
                "STDDEV": "35.36"
            },
            "2024-01-14": {
                "MEAN": "175.30",
                "STDDEV": "35.20"
            },
            "2024-01-13": {
                "MEAN": "175.10",
                "STDDEV": "35.05"
            }
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=ANALYTICS_SLIDING_WINDOW&SYMBOLS=AAPL&RANGE=1year&INTERVAL=DAILY&WINDOW_SIZE=20&CALCULATIONS=MEAN,STDDEV&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day, up to 5 symbols per request
- **Premium Tier**: 75-1200 requests per minute, up to 50 symbols per request

## Notes

- Calculates metrics for each sliding window
- Window slides through the time series
- Returns time series of calculated metrics
- Useful for rolling statistics and trend analysis
- Free tier: up to 5 symbols
- Premium tier: up to 50 symbols
