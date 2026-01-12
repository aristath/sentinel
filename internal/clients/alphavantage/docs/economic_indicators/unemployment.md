# UNEMPLOYMENT

Unemployment rate data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the unemployment rate for the United States.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `UNEMPLOYMENT` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Unemployment Rate",
    "interval": "monthly",
    "unit": "Percent",
    "data": [
        {
            "date": "2024-01-01",
            "value": "3.7"
        },
        {
            "date": "2023-12-01",
            "value": "3.8"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=UNEMPLOYMENT&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Monthly unemployment rate data
- Values are percentages
- Updated monthly
