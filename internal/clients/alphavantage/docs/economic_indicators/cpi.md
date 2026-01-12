# CPI (Consumer Price Index)

Consumer Price Index data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Consumer Price Index (CPI) for the United States.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `CPI` |
| `interval` | string | No | Time interval. Valid values: `monthly` (default), `semiannual` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Consumer Price Index",
    "interval": "monthly",
    "unit": "Index 1982-1984=100",
    "data": [
        {
            "date": "2024-01-01",
            "value": "300.0"
        },
        {
            "date": "2023-12-01",
            "value": "299.0"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=CPI&interval=monthly&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- CPI measures inflation
- Base period is 1982-1984 = 100
- Available in monthly and semiannual intervals
- Updated monthly
