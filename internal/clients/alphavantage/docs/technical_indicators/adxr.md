# ADXR (Average Directional Movement Index Rating)

Average Directional Movement Index Rating technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Average Directional Movement Index Rating (ADXR) values for a given equity. ADXR is a smoothed version of ADX, providing a more stable trend strength indicator.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `ADXR` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each ADXR value (default: `14`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Average Directional Movement Index Rating (ADXR)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 14,
        "6: Time Zone": "US/Eastern"
    },
    "Technical Analysis: ADXR": {
        "2024-01-15": {
            "ADXR": "24.50"
        },
        "2024-01-14": {
            "ADXR": "24.20"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=ADXR&symbol=IBM&interval=daily&time_period=14&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- ADXR is a smoothed version of ADX
- More stable than ADX, less prone to whipsaws
- ADXR = (ADX + ADX N periods ago) / 2
- Values range from 0 to 100
- ADXR above 25 indicates a strong trend
- Standard time period is 14 periods
- Often used in conjunction with ADX for trend confirmation
