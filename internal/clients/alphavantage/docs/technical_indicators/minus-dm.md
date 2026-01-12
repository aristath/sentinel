# MINUS_DM (Minus Directional Movement)

Minus Directional Movement technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Minus Directional Movement (-DM) values for a given equity. -DM measures downward price movement strength, part of the Directional Movement System.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `MINUS_DM` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each -DM value (default: `14`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Minus Directional Movement (-DM)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 14,
        "6: Time Zone": "US/Eastern"
    },
    "Technical Analysis: MINUS_DM": {
        "2024-01-15": {
            "MINUS_DM": "18.50"
        },
        "2024-01-14": {
            "MINUS_DM": "19.20"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=MINUS_DM&symbol=IBM&interval=daily&time_period=14&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- -DM measures downward price movement
- Part of the Directional Movement System
- Used with +DM to calculate ADX
- Higher -DM values indicate stronger downward movement
- Standard time period is 14 periods
- Raw directional movement value (not normalized)
