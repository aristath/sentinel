# ETF_PROFILE

ETF profile and key metrics.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API retrieves key metrics for a specified ETF, such as net assets, expense ratio, and turnover.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `ETF_PROFILE` |
| `symbol` | string | Yes | The ETF ticker symbol (e.g., `SPY`, `QQQ`, `VTI`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "symbol": "SPY",
    "name": "SPDR S&P 500 ETF Trust",
    "assetType": "ETF",
    "description": "The SPDR S&P 500 ETF Trust seeks to provide investment results that correspond generally to the price and yield performance of the S&P 500 Index.",
    "cusip": "78463V107",
    "isin": "US78463V1070",
    "exchange": "NYSE Arca",
    "currency": "USD",
    "country": "United States",
    "sector": "Diversified",
    "industry": "Exchange Traded Fund",
    "address": "State Street Global Advisors, One Lincoln Street, Boston, MA, United States",
    "fullTimeEmployees": null,
    "fiscalYearEnd": "December",
    "latestQuarter": "2023-12-31",
    "marketCapitalization": "500000000000",
    "netAssets": "500000000000",
    "expenseRatio": "0.0009",
    "dividendYield": "0.0135",
    "52WeekHigh": "480.00",
    "52WeekLow": "380.00",
    "50DayMovingAverage": "450.00",
    "200DayMovingAverage": "440.00",
    "sharesOutstanding": "1040000000",
    "turnover": "0.05"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | ETF symbol |
| `name` | string | ETF name |
| `assetType` | string | Asset type (typically "ETF") |
| `description` | string | ETF description |
| `netAssets` | string | Net assets under management |
| `expenseRatio` | string | Annual expense ratio (as decimal) |
| `dividendYield` | string | Dividend yield |
| `turnover` | string | Portfolio turnover ratio |
| `sharesOutstanding` | string | Shares outstanding |
| `exchange` | string | Primary exchange |
| `currency` | string | Currency code |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=ETF_PROFILE&symbol=SPY&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns comprehensive ETF information
- Includes key metrics like expense ratio and net assets
- Similar structure to OVERVIEW but ETF-specific
- Useful for ETF research and comparison
