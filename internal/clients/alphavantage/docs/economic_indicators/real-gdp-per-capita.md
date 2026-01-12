# REAL_GDP_PER_CAPITA

Real Gross Domestic Product per capita data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns real Gross Domestic Product (GDP) per capita data for the United States.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `REAL_GDP_PER_CAPITA` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Real Gross Domestic Product per Capita",
    "interval": "annual",
    "unit": "Dollars",
    "data": [
        {
            "date": "2023-01-01",
            "value": "65000.0"
        },
        {
            "date": "2022-01-01",
            "value": "63000.0"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=REAL_GDP_PER_CAPITA&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Real GDP per capita is adjusted for inflation
- Values are in dollars per person
- Annual data only
- Updated annually
