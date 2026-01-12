# OVERVIEW

Company overview and fundamental data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns company information, financial ratios, and other key metrics for a specified equity.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `OVERVIEW` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Symbol": "IBM",
    "AssetType": "Common Stock",
    "Name": "International Business Machines Corporation",
    "Description": "International Business Machines Corporation...",
    "CIK": "0000051143",
    "Exchange": "NYSE",
    "Currency": "USD",
    "Country": "USA",
    "Sector": "Technology",
    "Industry": "Information Technology Services",
    "Address": "1 New Orchard Road, Armonk, NY, United States",
    "FullTimeEmployees": "288300",
    "FiscalYearEnd": "December",
    "LatestQuarter": "2023-09-30",
    "MarketCapitalization": "150000000000",
    "EBITDA": "12000000000",
    "PERatio": "25.5",
    "PEGRatio": "2.1",
    "BookValue": "25.3",
    "DividendPerShare": "6.64",
    "DividendYield": "0.035",
    "EPS": "7.25",
    "RevenuePerShareTTM": "65.2",
    "ProfitMargin": "0.12",
    "OperatingMarginTTM": "0.15",
    "ReturnOnAssetsTTM": "0.05",
    "ReturnOnEquityTTM": "0.28",
    "RevenueTTM": "60000000000",
    "GrossProfitTTM": "30000000000",
    "DilutedEPSTTM": "7.25",
    "QuarterlyEarningsGrowthYOY": "0.05",
    "QuarterlyRevenueGrowthYOY": "0.03",
    "AnalystTargetPrice": "185.00",
    "TrailingPE": "25.5",
    "ForwardPE": "24.0",
    "PriceToSalesRatioTTM": "2.5",
    "PriceToBookRatio": "7.3",
    "EVToRevenue": "2.8",
    "EVToEBITDA": "12.5",
    "Beta": "0.95",
    "52WeekHigh": "190.00",
    "52WeekLow": "120.00",
    "50DayMovingAverage": "175.00",
    "200DayMovingAverage": "165.00",
    "SharesOutstanding": "900000000",
    "DividendDate": "2024-03-09",
    "ExDividendDate": "2024-02-08"
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=OVERVIEW&symbol=IBM&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns comprehensive company fundamental data
- Includes financial ratios, market metrics, and company information
- Updated quarterly after earnings reports
