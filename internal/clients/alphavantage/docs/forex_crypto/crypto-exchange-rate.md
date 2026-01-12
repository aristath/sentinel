# CRYPTO_EXCHANGE_RATE

Real-time exchange rate for cryptocurrency pairs.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the real-time exchange rate for any pair of digital and physical currencies. This is the same as `CURRENCY_EXCHANGE_RATE` but specifically documented for crypto use cases.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `CURRENCY_EXCHANGE_RATE` (or use `CRYPTO_EXCHANGE_RATE` if available) |
| `from_currency` | string | Yes | The digital currency symbol (e.g., `BTC`, `ETH`, `XRP`) |
| `to_currency` | string | Yes | The physical currency symbol (e.g., `USD`, `EUR`, `GBP`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Realtime Currency Exchange Rate": {
        "1. From_Currency Code": "BTC",
        "2. From_Currency Name": "Bitcoin",
        "3. To_Currency Code": "USD",
        "4. To_Currency Name": "United States Dollar",
        "5. Exchange Rate": "42000.0000",
        "6. Last Refreshed": "2024-01-15 16:00:00",
        "7. Time Zone": "UTC",
        "8. Bid Price": "41998.0000",
        "9. Ask Price": "42002.0000"
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=BTC&to_currency=USD&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Uses the same `CURRENCY_EXCHANGE_RATE` function
- Supports all major cryptocurrencies (BTC, ETH, XRP, etc.)
- Exchange rates are updated in real-time
- Includes bid and ask prices
- Same functionality as regular currency exchange rate endpoint
