# HT_SINE (Hilbert Transform - Sine Wave)

Hilbert Transform Sine Wave technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Hilbert Transform Sine Wave values for a given equity. This indicator uses the Hilbert Transform to generate sine and cosine waves that represent the dominant cycle in the price data.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `HT_SINE` |
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
        "2: Indicator": "Hilbert Transform - SineWave (HT_SINE)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Series Type": "close",
        "6: Time Zone": "US/Eastern"
    },
    "Technical Analysis: HT_SINE": {
        "2024-01-15": {
            "SINE": "0.75",
            "LEAD": "0.80"
        },
        "2024-01-14": {
            "SINE": "0.73",
            "LEAD": "0.78"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=HT_SINE&symbol=IBM&interval=daily&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns SINE and LEAD (leading sine) values
- Values range from -1 to +1
- Uses Hilbert Transform for cycle detection
- LEAD crosses above SINE for buy signals
- LEAD crosses below SINE for sell signals
- Use `series_type=close` for most standard calculations
