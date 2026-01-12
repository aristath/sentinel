# EARNINGS

Earnings data for a company.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns annual and quarterly earnings data for a specified company, including earnings per share (EPS) and surprise metrics.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `EARNINGS` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "symbol": "IBM",
    "annualEarnings": [
        {
            "fiscalDateEnding": "2023-12-31",
            "reportedEPS": "7.25"
        },
        {
            "fiscalDateEnding": "2022-12-31",
            "reportedEPS": "6.90"
        }
    ],
    "quarterlyEarnings": [
        {
            "fiscalDateEnding": "2023-09-30",
            "reportedDate": "2023-10-18",
            "reportedEPS": "1.85",
            "estimatedEPS": "1.80",
            "surprise": "0.05",
            "surprisePercentage": "2.78"
        },
        {
            "fiscalDateEnding": "2023-06-30",
            "reportedDate": "2023-07-19",
            "reportedEPS": "1.75",
            "estimatedEPS": "1.70",
            "surprise": "0.05",
            "surprisePercentage": "2.94"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Includes both annual and quarterly earnings
- Surprise metrics show how actual EPS compared to estimates
- Updated after each earnings report
