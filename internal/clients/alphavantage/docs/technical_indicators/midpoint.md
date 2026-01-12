# MIDPOINT (Midpoint)

Midpoint technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Midpoint values for a given equity. Midpoint calculates the average of the highest and lowest values over a specified period.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `MIDPOINT` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each MIDPOINT value (default: `14`) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Midpoint (MIDPOINT)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 14,
        "6: Series Type": "close",
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: MIDPOINT": {
        "2024-01-15": {
            "MIDPOINT": "185.00"
        },
        "2024-01-14": {
            "MIDPOINT": "184.50"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=MIDPOINT&symbol=IBM&interval=daily&time_period=14&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- MIDPOINT = (Highest Value + Lowest Value) / 2
- Calculates the midpoint of the price range over the period
- Standard time period is 14 periods
- Use `series_type=close` for most standard MIDPOINT calculations
- Useful for identifying the center of price action
