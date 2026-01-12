# TREASURY_YIELD

Treasury yield data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns Treasury yield data for the United States.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `TREASURY_YIELD` |
| `interval` | string | No | Time interval. Valid values: `daily`, `weekly`, `monthly` (default: `monthly`) |
| `maturity` | string | No | Treasury maturity. Valid values: `3month`, `2year`, `5year`, `7year`, `10year`, `30year` (default: `10year`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "10-Year Treasury Yield",
    "interval": "monthly",
    "unit": "Percent",
    "data": [
        {
            "date": "2024-01-01",
            "value": "4.25"
        },
        {
            "date": "2023-12-01",
            "value": "4.20"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=TREASURY_YIELD&interval=monthly&maturity=10year&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Treasury yields are percentages
- Available maturities: 3-month, 2-year, 5-year, 7-year, 10-year, 30-year
- Available intervals: daily, weekly, monthly
- Updated daily
