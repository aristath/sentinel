# TOP_GAINERS_LOSERS

Top gainers, losers, and most active stocks.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the top 20 gainers, losers, and most active traded tickers in the US market.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `TOP_GAINERS_LOSERS` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "metadata": "Top gainers, losers, and most actively traded US tickers",
    "last_updated": "2024-01-15 16:00:00",
    "top_gainers": [
        {
            "ticker": "AAPL",
            "price": "185.50",
            "change_amount": "5.50",
            "change_percentage": "3.05%",
            "volume": "50000000"
        }
    ],
    "top_losers": [
        {
            "ticker": "XYZ",
            "price": "10.25",
            "change_amount": "-1.25",
            "change_percentage": "-10.87%",
            "volume": "15000000"
        }
    ],
    "most_actively_traded": [
        {
            "ticker": "TSLA",
            "price": "250.00",
            "change_amount": "2.50",
            "change_percentage": "1.01%",
            "volume": "75000000"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=TOP_GAINERS_LOSERS&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns top 20 gainers, losers, and most active stocks
- Updated throughout the trading day
- US market only
