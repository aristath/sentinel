# RETAIL_SALES

Retail sales data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns retail sales data for the United States.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `RETAIL_SALES` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Retail Sales",
    "interval": "monthly",
    "unit": "Millions of Dollars",
    "data": [
        {
            "date": "2024-01-01",
            "value": "700000.0"
        },
        {
            "date": "2023-12-01",
            "value": "695000.0"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=RETAIL_SALES&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Retail sales values are in millions of dollars
- Updated monthly
- Measures total sales at retail establishments
