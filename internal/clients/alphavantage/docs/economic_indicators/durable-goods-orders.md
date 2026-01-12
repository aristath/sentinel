# DURABLE_GOODS_ORDERS

Durable goods orders data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns durable goods orders data for the United States.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `DURABLE_GOODS_ORDERS` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Durable Goods Orders",
    "interval": "monthly",
    "unit": "Millions of Dollars",
    "data": [
        {
            "date": "2024-01-01",
            "value": "280000.0"
        },
        {
            "date": "2023-12-01",
            "value": "275000.0"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=DURABLE_GOODS_ORDERS&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Durable goods orders values are in millions of dollars
- Updated monthly
- Measures new orders for manufactured durable goods
