# HT_TRENDLINE (Hilbert Transform - Instantaneous Trendline)

Hilbert Transform Instantaneous Trendline technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Hilbert Transform Instantaneous Trendline values for a given equity. This indicator uses the Hilbert Transform to identify the instantaneous trendline, removing noise and providing a smooth trend representation.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `HT_TRENDLINE` |
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
        "2: Indicator": "Hilbert Transform - Instantaneous Trendline (HT_TRENDLINE)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Series Type": "close",
        "6: Time Zone": "US/Eastern"
    },
    "Technical Analysis: HT_TRENDLINE": {
        "2024-01-15": {
            "TRENDLINE": "185.4567"
        },
        "2024-01-14": {
            "TRENDLINE": "185.3456"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=HT_TRENDLINE&symbol=IBM&interval=daily&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Uses Hilbert Transform for cycle analysis
- Provides a smooth trendline that removes noise
- No time period parameter needed
- Use `series_type=close` for most standard calculations
- Part of the Hilbert Transform indicator family
