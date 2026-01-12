# TRIMA (Triangular Moving Average)

Triangular Moving Average technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Triangular Moving Average (TRIMA) values for a given equity. TRIMA is a double-smoothed moving average that gives more weight to middle-period data.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `TRIMA` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each TRIMA value (e.g., `60` for 60-period TRIMA) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Triangular Moving Average (TRIMA)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 60,
        "6: Series Type": "close",
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: TRIMA": {
        "2024-01-15": {
            "TRIMA": "185.3456"
        },
        "2024-01-14": {
            "TRIMA": "185.2345"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=TRIMA&symbol=IBM&interval=daily&time_period=60&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- TRIMA is a double-smoothed moving average
- Gives more weight to middle-period data points
- Smoother than SMA but less responsive than EMA
- Common time periods: 20, 50, 100, 200 days
- Use `series_type=close` for most standard TRIMA calculations
