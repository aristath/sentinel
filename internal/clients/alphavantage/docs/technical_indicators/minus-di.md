# MINUS_DI (Minus Directional Indicator)

Minus Directional Indicator technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Minus Directional Indicator (-DI) values for a given equity. -DI is part of the Directional Movement System and measures downward price movement strength.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `MINUS_DI` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each -DI value (default: `14`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Minus Directional Indicator (-DI)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 14,
        "6: Time Zone": "US/Eastern"
    },
    "Technical Analysis: MINUS_DI": {
        "2024-01-15": {
            "MINUS_DI": "18.50"
        },
        "2024-01-14": {
            "MINUS_DI": "19.20"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=MINUS_DI&symbol=IBM&interval=daily&time_period=14&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- -DI values range from 0 to 100
- Higher -DI values indicate stronger downward price movement
- Used with +DI (PLUS_DI) and ADX to form the Directional Movement System
- When -DI crosses above +DI, it may signal a downtrend
- Standard time period is 14 periods
- Often used in conjunction with ADX for trend analysis
