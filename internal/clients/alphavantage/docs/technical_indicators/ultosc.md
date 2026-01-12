# ULTOSC (Ultimate Oscillator)

Ultimate Oscillator technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Ultimate Oscillator values for a given equity. The Ultimate Oscillator combines short, medium, and long-term price momentum into a single indicator.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `ULTOSC` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `timeperiod1` | integer | No | First time period (default: `7`) |
| `timeperiod2` | integer | No | Second time period (default: `14`) |
| `timeperiod3` | integer | No | Third time period (default: `28`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Ultimate Oscillator (ULTOSC)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period 1": 7,
        "6: Time Period 2": 14,
        "7: Time Period 3": 28,
        "8: Time Zone": "US/Eastern"
    },
    "Technical Analysis: ULTOSC": {
        "2024-01-15": {
            "ULTOSC": "65.50"
        },
        "2024-01-14": {
            "ULTOSC": "63.25"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=ULTOSC&symbol=IBM&interval=daily&timeperiod1=7&timeperiod2=14&timeperiod3=28&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- ULTOSC values range from 0 to 100
- Combines three different time periods (7, 14, 28) for more reliable signals
- Values above 70 typically indicate overbought conditions
- Values below 30 typically indicate oversold conditions
- Standard parameters: timeperiod1=7, timeperiod2=14, timeperiod3=28
- Less prone to false signals than single-period oscillators
