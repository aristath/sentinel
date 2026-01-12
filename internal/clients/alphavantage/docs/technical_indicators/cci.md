# CCI (Commodity Channel Index)

Commodity Channel Index technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Commodity Channel Index (CCI) values for a given equity. CCI identifies cyclical trends in commodities and equities.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `CCI` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each CCI value (default: `20`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Commodity Channel Index (CCI)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 20,
        "6: Time Zone": "US/Eastern"
    },
    "Technical Analysis: CCI": {
        "2024-01-15": {
            "CCI": "125.50"
        },
        "2024-01-14": {
            "CCI": "110.25"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=CCI&symbol=IBM&interval=daily&time_period=20&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- CCI values typically range from -100 to +100
- Values above +100 indicate overbought conditions
- Values below -100 indicate oversold conditions
- Standard time period is 20 periods
- CCI can exceed these bounds in strong trends
