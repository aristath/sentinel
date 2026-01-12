# HT_TRENDMODE (Hilbert Transform - Trend vs Cycle Mode)

Hilbert Transform Trend vs Cycle Mode technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Hilbert Transform Trend vs Cycle Mode values for a given equity. This indicator identifies whether the market is in a trending mode or a cycling mode.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `HT_TRENDMODE` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Hilbert Transform - Trend vs Cycle Mode (HT_TRENDMODE)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Series Type": "close",
        "6: Time Zone": "US/Eastern"
    },
    "Technical Analysis: HT_TRENDMODE": {
        "2024-01-15": {
            "TRENDMODE": "1"
        },
        "2024-01-14": {
            "TRENDMODE": "0"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=HT_TRENDMODE&symbol=IBM&interval=daily&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns 1 for trending mode, 0 for cycling mode
- Uses Hilbert Transform for cycle analysis
- Trending mode: use trend-following indicators
- Cycling mode: use oscillators
- Use `series_type=close` for most standard calculations
- Helps determine which type of indicators to use
