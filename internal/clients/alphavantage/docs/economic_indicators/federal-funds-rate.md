# FEDERAL_FUNDS_RATE

Federal Funds Rate data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Federal Funds Rate for the United States.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `FEDERAL_FUNDS_RATE` |
| `interval` | string | No | Time interval. Valid values: `daily`, `weekly`, `monthly` (default: `monthly`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Federal Funds Rate",
    "interval": "monthly",
    "unit": "Percent",
    "data": [
        {
            "date": "2024-01-01",
            "value": "5.25"
        },
        {
            "date": "2023-12-01",
            "value": "5.25"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=FEDERAL_FUNDS_RATE&interval=monthly&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Federal Funds Rate is set by the Federal Reserve
- Values are percentages
- Available in daily, weekly, and monthly intervals
- Updated when the Fed changes rates
