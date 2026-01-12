# CMO (Chande Momentum Oscillator)

Chande Momentum Oscillator technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Chande Momentum Oscillator (CMO) values for a given equity. CMO is a momentum indicator that measures the strength of price movement in both directions.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `CMO` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each CMO value (default: `14`) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Chande Momentum Oscillator (CMO)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 14,
        "6: Series Type": "close",
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: CMO": {
        "2024-01-15": {
            "CMO": "45.50"
        },
        "2024-01-14": {
            "CMO": "42.25"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=CMO&symbol=IBM&interval=daily&time_period=14&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- CMO values range from -100 to +100
- Values above +50 typically indicate overbought conditions
- Values below -50 typically indicate oversold conditions
- CMO uses both up and down price changes in its calculation
- Standard time period is 14 periods
- Use `series_type=close` for most standard CMO calculations
- Similar to RSI but uses a different calculation method
