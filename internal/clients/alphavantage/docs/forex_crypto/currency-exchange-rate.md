# CURRENCY_EXCHANGE_RATE

Real-time exchange rate between two currencies.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the real-time exchange rate for any pair of digital or physical currencies.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `CURRENCY_EXCHANGE_RATE` |
| `from_currency` | string | Yes | The currency you want to convert from (e.g., `USD`, `EUR`, `BTC`) |
| `to_currency` | string | Yes | The currency you want to convert to (e.g., `USD`, `EUR`, `BTC`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Realtime Currency Exchange Rate": {
        "1. From_Currency Code": "USD",
        "2. From_Currency Name": "United States Dollar",
        "3. To_Currency Code": "EUR",
        "4. To_Currency Name": "Euro",
        "5. Exchange Rate": "0.9200",
        "6. Last Refreshed": "2024-01-15 16:00:00",
        "7. Time Zone": "UTC",
        "8. Bid Price": "0.9198",
        "9. Ask Price": "0.9202"
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=USD&to_currency=EUR&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Supports both physical currencies (USD, EUR, GBP, etc.) and cryptocurrencies (BTC, ETH, etc.)
- Exchange rates are updated in real-time
- Includes bid and ask prices for forex pairs
