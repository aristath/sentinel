# REAL_GDP

Real Gross Domestic Product data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns real Gross Domestic Product (GDP) data for the United States.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `REAL_GDP` |
| `interval` | string | No | Time interval. Valid values: `annual` (default), `quarterly` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Real Gross Domestic Product",
    "interval": "annual",
    "unit": "Billions of Dollars",
    "data": [
        {
            "date": "2023-01-01",
            "value": "22000.0"
        },
        {
            "date": "2022-01-01",
            "value": "21000.0"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=REAL_GDP&interval=annual&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Real GDP is adjusted for inflation
- Available in annual and quarterly intervals
- Values are in billions of dollars
