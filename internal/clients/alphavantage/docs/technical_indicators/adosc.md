# ADOSC (Chaikin A/D Oscillator)

Chaikin A/D Oscillator technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Chaikin A/D Oscillator (ADOSC) values for a given equity. ADOSC is the difference between fast and slow EMAs of the Accumulation/Distribution Line, providing momentum signals.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `ADOSC` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `fastperiod` | integer | No | Number of periods for the fast EMA (default: `3`) |
| `slowperiod` | integer | No | Number of periods for the slow EMA (default: `10`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Chaikin A/D Oscillator (ADOSC)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Fast Period": 3,
        "6: Slow Period": 10,
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: ADOSC": {
        "2024-01-15": {
            "ADOSC": "123456.78"
        },
        "2024-01-14": {
            "ADOSC": "123000.00"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=ADOSC&symbol=IBM&interval=daily&fastperiod=3&slowperiod=10&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- ADOSC = Fast EMA of A/D Line - Slow EMA of A/D Line
- Provides momentum signals from the A/D Line
- Positive values indicate accumulation momentum
- Negative values indicate distribution momentum
- Standard parameters: fastperiod=3, slowperiod=10
- Useful for identifying changes in accumulation/distribution momentum
