# NONFARM_PAYROLL

Nonfarm payroll employment data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns nonfarm payroll employment data for the United States.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `NONFARM_PAYROLL` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Nonfarm Payroll Employment",
    "interval": "monthly",
    "unit": "Thousands of Persons",
    "data": [
        {
            "date": "2024-01-01",
            "value": "157000.0"
        },
        {
            "date": "2023-12-01",
            "value": "156500.0"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=NONFARM_PAYROLL&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Nonfarm payroll values are in thousands of persons
- Updated monthly
- Measures total nonfarm employment excluding farm workers, private household employees, and nonprofit organization employees
