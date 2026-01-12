# REALTIME_BULK_QUOTES

Real-time quotes for multiple US-traded symbols.

## API Tier

**Free Tier Available**: No
**Premium Required**: Yes

## Description

This API fetches real-time quotes for up to 100 US-traded symbols in a single request. This is a premium endpoint that requires a subscription to a premium membership plan that includes "Realtime US Market Data".

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `REALTIME_BULK_QUOTES` |
| `symbol` | string | Yes | Comma-separated list of up to 100 stock symbols (e.g., `MSFT,AAPL,IBM,GOOGL`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Realtime Bulk Quotes": {
        "MSFT": {
            "01. symbol": "MSFT",
            "02. price": "420.50",
            "03. volume": "12345678",
            "04. timestamp": "2024-01-15 16:00:00"
        },
        "AAPL": {
            "01. symbol": "AAPL",
            "02. price": "185.75",
            "03. volume": "23456789",
            "04. timestamp": "2024-01-15 16:00:00"
        },
        "IBM": {
            "01. symbol": "IBM",
            "02. price": "186.20",
            "03. volume": "3456789",
            "04. timestamp": "2024-01-15 16:00:00"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=REALTIME_BULK_QUOTES&symbol=MSFT,AAPL,IBM&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Premium Tier Only**: 75-1200 requests per minute (depending on plan)

## Notes

- **Premium endpoint** - requires a paid subscription with "Realtime US Market Data" access
- Supports up to 100 symbols per request
- Real-time data updated during market hours
- More efficient than making individual requests for multiple symbols
- Symbols must be comma-separated with no spaces
