# DIGITAL_CURRENCY_MONTHLY

Monthly historical time series data for cryptocurrencies.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns monthly historical time series data for a specified digital currency traded on a specific market.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `DIGITAL_CURRENCY_MONTHLY` |
| `symbol` | string | Yes | The digital currency symbol (e.g., `BTC`, `ETH`, `XRP`) |
| `market` | string | Yes | The market currency (e.g., `USD`, `EUR`, `CNY`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Monthly Prices and Volumes for Digital Currency",
        "2. Digital Currency Code": "BTC",
        "3. Digital Currency Name": "Bitcoin",
        "4. Market Code": "USD",
        "5. Market Name": "United States Dollar",
        "6. Last Refreshed": "2024-01-31 00:00:00",
        "7. Time Zone": "UTC"
    },
    "Time Series (Digital Currency Monthly)": {
        "2024-01-31": {
            "1a. open (USD)": "42000.00",
            "1b. open (USD)": "42000.00",
            "2a. high (USD)": "45000.00",
            "2b. high (USD)": "45000.00",
            "3a. low (USD)": "40000.00",
            "3b. low (USD)": "40000.00",
            "4a. close (USD)": "44000.00",
            "4b. close (USD)": "44000.00",
            "5. volume": "450000.00",
            "6. market cap (USD)": "850000000000.00"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=DIGITAL_CURRENCY_MONTHLY&symbol=BTC&market=USD&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Monthly data aggregated from daily cryptocurrency data
- Supports major cryptocurrencies (BTC, ETH, XRP, etc.)
- Market currency determines the pricing currency
- Includes market capitalization data
- Useful for long-term cryptocurrency trend analysis
