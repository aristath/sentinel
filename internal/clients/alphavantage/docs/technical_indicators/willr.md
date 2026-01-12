# WILLR (Williams' %R)

Williams' %R technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns Williams' %R values for a given equity. Williams' %R is a momentum indicator that measures overbought/oversold levels, similar to Stochastic but with an inverted scale.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `WILLR` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each WILLR value (default: `14`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Williams' %R (WILLR)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 14,
        "6: Time Zone": "US/Eastern"
    },
    "Technical Analysis: WILLR": {
        "2024-01-15": {
            "WILLR": "-34.75"
        },
        "2024-01-14": {
            "WILLR": "-36.50"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=WILLR&symbol=IBM&interval=daily&time_period=14&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- WILLR values range from -100 to 0 (inverted scale)
- Values above -20 typically indicate overbought conditions
- Values below -80 typically indicate oversold conditions
- Standard time period is 14 periods
- Similar to Stochastic but with inverted scale (multiply by -1 to get 0-100 range)
