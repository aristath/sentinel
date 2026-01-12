# CRYPTO_INTRADAY

Intraday time series data for cryptocurrencies.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API provides intraday time series data for a specified cryptocurrency and market, updated in real-time during market hours.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `CRYPTO_INTRADAY` |
| `symbol` | string | Yes | The digital currency symbol (e.g., `BTC`, `ETH`, `XRP`) |
| `market` | string | Yes | The market currency (e.g., `USD`, `EUR`, `CNY`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min` |
| `outputsize` | string | No | Determines the amount of data returned. Valid values: `compact` (default, latest 100 data points), `full` (full-length time series) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Crypto Intraday (1min) Time Series",
        "2. Digital Currency Code": "BTC",
        "3. Digital Currency Name": "Bitcoin",
        "4. Market Code": "USD",
        "5. Market Name": "United States Dollar",
        "6. Last Refreshed": "2024-01-15 16:00:00",
        "7. Interval": "1min",
        "8. Output Size": "Compact",
        "9. Time Zone": "UTC"
    },
    "Time Series Crypto (1min)": {
        "2024-01-15 16:00:00": {
            "1a. open (USD)": "42000.00",
            "1b. open (USD)": "42000.00",
            "2a. high (USD)": "42050.00",
            "2b. high (USD)": "42050.00",
            "3a. low (USD)": "41950.00",
            "3b. low (USD)": "41950.00",
            "4a. close (USD)": "42025.00",
            "4b. close (USD)": "42025.00",
            "5. volume": "150.00",
            "6. market cap (USD)": "825000000000.00"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=CRYPTO_INTRADAY&symbol=BTC&market=USD&interval=5min&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Intraday data for cryptocurrencies
- Supports major cryptocurrencies (BTC, ETH, XRP, etc.)
- Market currency determines the pricing currency
- Includes market capitalization data
- Use `outputsize=full` to get complete historical intraday time series
- Note: Some users report this endpoint may not be fully available - check API status
