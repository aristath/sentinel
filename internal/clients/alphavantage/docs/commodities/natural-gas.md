# NATURAL_GAS

Natural gas price data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns time series data for natural gas prices.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `NATURAL_GAS` |
| `interval` | string | Yes | Time interval. Valid values: `daily`, `weekly`, `monthly` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Natural Gas Prices",
    "interval": "daily",
    "unit": "USD per MMBtu",
    "data": [
        {
            "date": "2024-01-15",
            "value": "3.50"
        },
        {
            "date": "2024-01-14",
            "value": "3.45"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=NATURAL_GAS&interval=daily&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Natural gas prices in USD per MMBtu (Million British Thermal Units)
- Available intervals: daily, weekly, monthly
- Updated daily
