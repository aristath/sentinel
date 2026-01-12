# MAMA (MESA Adaptive Moving Average)

MESA Adaptive Moving Average technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the MESA Adaptive Moving Average (MAMA) values for a given equity. MAMA adapts to price changes based on the rate of change of phase, using the Hilbert Transform.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `MAMA` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `fastlimit` | float | No | Upper limit for the adaptive factor (default: `0.5`) |
| `slowlimit` | float | No | Lower limit for the adaptive factor (default: `0.05`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "MESA Adaptive Moving Average (MAMA)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Series Type": "close",
        "6: Fast Limit": 0.5,
        "7: Slow Limit": 0.05,
        "8: Time Zone": "US/Eastern"
    },
    "Technical Analysis: MAMA": {
        "2024-01-15": {
            "MAMA": "185.5678",
            "FAMA": "185.4567"
        },
        "2024-01-14": {
            "MAMA": "185.4567",
            "FAMA": "185.3456"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=MAMA&symbol=IBM&interval=daily&series_type=close&fastlimit=0.5&slowlimit=0.05&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- MAMA adapts based on the rate of change of phase
- Returns both MAMA and FAMA (Following Adaptive Moving Average)
- Uses Hilbert Transform for cycle detection
- Standard parameters: fastlimit=0.5, slowlimit=0.05
- Use `series_type=close` for most standard MAMA calculations
- FAMA is a smoothed version of MAMA
