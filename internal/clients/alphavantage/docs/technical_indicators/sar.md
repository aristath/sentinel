# SAR (Parabolic SAR)

Parabolic SAR technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Parabolic SAR (Stop and Reverse) values for a given equity. SAR is a trend-following indicator that provides potential entry and exit points.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `SAR` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `acceleration` | float | No | Acceleration factor (default: `0.02`) |
| `maximum` | float | No | Maximum acceleration factor (default: `0.20`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Parabolic SAR (SAR)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Acceleration": 0.02,
        "6: Maximum": 0.20,
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: SAR": {
        "2024-01-15": {
            "SAR": "183.50"
        },
        "2024-01-14": {
            "SAR": "183.25"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=SAR&symbol=IBM&interval=daily&acceleration=0.02&maximum=0.20&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- SAR appears as dots above or below the price
- When SAR is below price, it indicates an uptrend
- When SAR is above price, it indicates a downtrend
- SAR flips position when price crosses it, signaling potential trend reversal
- Standard parameters: acceleration=0.02, maximum=0.20
- Useful for setting trailing stop-loss levels
