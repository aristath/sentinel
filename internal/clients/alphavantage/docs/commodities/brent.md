# BRENT (Brent Crude Oil)

Brent crude oil price data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns time series data for Brent crude oil prices.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `BRENT` |
| `interval` | string | Yes | Time interval. Valid values: `daily`, `weekly`, `monthly` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Brent Crude Oil Prices",
    "interval": "daily",
    "unit": "USD per barrel",
    "data": [
        {
            "date": "2024-01-15",
            "value": "80.50"
        },
        {
            "date": "2024-01-14",
            "value": "80.20"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=BRENT&interval=daily&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Brent is a major benchmark for crude oil prices
- Prices are in USD per barrel
- Available intervals: daily, weekly, monthly
