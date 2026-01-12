# GLOBAL_COMMODITIES

Global commodities price index.

## API Tier

**Free Tier Available**: Yes  
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the global price index of all commodities in monthly, quarterly, and annual temporal dimensions.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `GLOBAL_COMMODITIES` or `ALL_COMMODITIES` |
| `interval` | string | No | Time interval. Valid values: `monthly` (default), `quarterly`, `annual` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Global Commodities Price Index",
    "interval": "monthly",
    "unit": "Index (Base = 100)",
    "data": [
        {
            "date": "2024-01-01",
            "value": "125.50"
        },
        {
            "date": "2023-12-01",
            "value": "124.80"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=GLOBAL_COMMODITIES&interval=monthly&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns aggregate commodities price index
- Available intervals: monthly, quarterly, annual
- Index-based (base = 100)
- Represents overall commodities market performance
- Useful for commodities market trend analysis
