# KAMA (Kaufman Adaptive Moving Average)

Kaufman Adaptive Moving Average technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Kaufman Adaptive Moving Average (KAMA) values for a given equity. KAMA adjusts its sensitivity based on market volatility, becoming more responsive in trending markets and less responsive in choppy markets.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `KAMA` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each KAMA value (default: `30`) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Kaufman Adaptive Moving Average (KAMA)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 30,
        "6: Series Type": "close",
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: KAMA": {
        "2024-01-15": {
            "KAMA": "185.4567"
        },
        "2024-01-14": {
            "KAMA": "185.3456"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=KAMA&symbol=IBM&interval=daily&time_period=30&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- KAMA adapts to market volatility automatically
- More responsive in trending markets
- Less responsive in choppy/volatile markets
- Standard time period is 30 periods
- Use `series_type=close` for most standard KAMA calculations
- Designed to reduce false signals in sideways markets
