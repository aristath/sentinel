# DX (Directional Movement Index)

Directional Movement Index technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Directional Movement Index (DX) values for a given equity. DX is the raw calculation used to derive ADX, measuring the strength of directional movement.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `DX` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each DX value (default: `14`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Directional Movement Index (DX)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 14,
        "6: Time Zone": "US/Eastern"
    },
    "Technical Analysis: DX": {
        "2024-01-15": {
            "DX": "26.50"
        },
        "2024-01-14": {
            "DX": "25.80"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=DX&symbol=IBM&interval=daily&time_period=14&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- DX is the raw calculation for ADX
- ADX is a smoothed version of DX
- Values range from 0 to 100
- Higher values indicate stronger directional movement
- Standard time period is 14 periods
- More volatile than ADX, less commonly used directly
