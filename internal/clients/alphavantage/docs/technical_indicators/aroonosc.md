# AROONOSC (Aroon Oscillator)

Aroon Oscillator technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Aroon Oscillator values for a given equity. Aroon Oscillator is the difference between Aroon Up and Aroon Down, providing a single value to identify trend strength and direction.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `AROONOSC` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each AROONOSC value (default: `14`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Aroon Oscillator (AROONOSC)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 14,
        "6: Time Zone": "US/Eastern"
    },
    "Technical Analysis: AROONOSC": {
        "2024-01-15": {
            "AROONOSC": "71.42"
        },
        "2024-01-14": {
            "AROONOSC": "57.14"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=AROONOSC&symbol=IBM&interval=daily&time_period=14&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- AROONOSC = Aroon Up - Aroon Down
- Values range from -100 to +100
- Positive values indicate uptrend strength
- Negative values indicate downtrend strength
- Values near zero indicate weak or sideways trends
- Standard time period is 14 periods
- Easier to interpret than separate Aroon Up/Down values
