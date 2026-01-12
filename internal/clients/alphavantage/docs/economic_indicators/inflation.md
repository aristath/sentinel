# INFLATION

Inflation rate data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the inflation rate for the United States.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `INFLATION` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Inflation Rate",
    "interval": "monthly",
    "unit": "Percent",
    "data": [
        {
            "date": "2024-01-01",
            "value": "3.2"
        },
        {
            "date": "2023-12-01",
            "value": "3.1"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=INFLATION&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Inflation rate is calculated as the year-over-year change in CPI
- Values are percentages
- Updated monthly
- Measures the rate of price increase for goods and services
