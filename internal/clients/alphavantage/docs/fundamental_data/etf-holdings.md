# ETF_HOLDINGS

ETF holdings and constituents.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the holdings or constituents of a specified ETF, detailing the allocation by asset types and sectors.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `ETF_HOLDINGS` |
| `symbol` | string | Yes | The ETF ticker symbol (e.g., `SPY`, `QQQ`, `VTI`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "symbol": "SPY",
    "name": "SPDR S&P 500 ETF Trust",
    "holdings": [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "weight": "7.25",
            "shares": "25000000"
        },
        {
            "symbol": "MSFT",
            "name": "Microsoft Corporation",
            "weight": "6.80",
            "shares": "18000000"
        },
        {
            "symbol": "AMZN",
            "name": "Amazon.com Inc.",
            "weight": "3.20",
            "shares": "12000000"
        }
    ],
    "sectorAllocation": {
        "Information Technology": "28.50",
        "Health Care": "13.20",
        "Financials": "11.80",
        "Communication Services": "10.50",
        "Consumer Discretionary": "10.20"
    },
    "assetAllocation": {
        "Stocks": "99.50",
        "Cash": "0.50"
    }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | ETF symbol |
| `name` | string | ETF name |
| `holdings` | array | Array of holdings |
| `holdings[].symbol` | string | Holding symbol |
| `holdings[].name` | string | Holding company name |
| `holdings[].weight` | string | Weight percentage in ETF |
| `holdings[].shares` | string | Number of shares held |
| `sectorAllocation` | object | Sector allocation percentages |
| `assetAllocation` | object | Asset type allocation percentages |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=ETF_HOLDINGS&symbol=SPY&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns top holdings of the ETF
- Includes weight percentages for each holding
- Shows sector and asset allocation
- Updated periodically as ETF rebalances
- Useful for understanding ETF composition and diversification
