# OBV (On Balance Volume)

On Balance Volume technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the On Balance Volume (OBV) values for a given equity. OBV is a volume-based indicator that uses volume flow to predict changes in stock price.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `OBV` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "On Balance Volume (OBV)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Zone": "US/Eastern"
    },
    "Technical Analysis: OBV": {
        "2024-01-15": {
            "OBV": "1234567890"
        },
        "2024-01-14": {
            "OBV": "1230000000"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=OBV&symbol=IBM&interval=daily&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- OBV is a cumulative indicator that adds volume on up days and subtracts on down days
- Rising OBV suggests accumulation (buying pressure)
- Falling OBV suggests distribution (selling pressure)
- OBV divergences from price can signal trend reversals
- No time period parameter needed - it's a cumulative calculation
