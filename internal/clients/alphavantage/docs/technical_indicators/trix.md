# TRIX (1-day Rate of Change of a Triple Smooth EMA)

TRIX technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the TRIX values for a given equity. TRIX is a momentum oscillator that shows the rate of change of a triple exponentially smoothed moving average of the closing price.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `TRIX` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each TRIX value (default: `30`) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "1-day Rate of Change of a Triple Smooth EMA (TRIX)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 30,
        "6: Series Type": "close",
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: TRIX": {
        "2024-01-15": {
            "TRIX": "0.0025"
        },
        "2024-01-14": {
            "TRIX": "0.0020"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=TRIX&symbol=IBM&interval=daily&time_period=30&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- TRIX is expressed as a percentage rate of change
- Positive TRIX indicates upward momentum
- Negative TRIX indicates downward momentum
- TRIX crossing above zero may signal a buy signal
- TRIX crossing below zero may signal a sell signal
- Standard time period is 30 periods
- Use `series_type=close` for most standard TRIX calculations
- Less sensitive to short-term price fluctuations due to triple smoothing
