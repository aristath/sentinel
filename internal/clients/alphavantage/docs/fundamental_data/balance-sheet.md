# BALANCE_SHEET

Balance sheet data for a company.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns annual and quarterly balance sheets for a specified company.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `BALANCE_SHEET` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "symbol": "IBM",
    "annualReports": [
        {
            "fiscalDateEnding": "2023-12-31",
            "reportedCurrency": "USD",
            "totalAssets": "135000000000",
            "totalCurrentAssets": "25000000000",
            "cashAndCashEquivalentsAtCarryingValue": "8000000000",
            "cashAndShortTermInvestments": "10000000000",
            "inventory": "2000000000",
            "currentNetReceivables": "8000000000",
            "totalNonCurrentAssets": "110000000000",
            "propertyPlantEquipment": "15000000000",
            "accumulatedDepreciationAmortizationPPE": "5000000000",
            "intangibleAssets": "50000000000",
            "intangibleAssetsExcludingGoodwill": "20000000000",
            "goodwill": "30000000000",
            "investments": "30000000000",
            "longTermInvestments": "25000000000",
            "shortTermInvestments": "2000000000",
            "otherCurrentAssets": "5000000000",
            "otherNonCurrentAssets": "10000000000",
            "totalLiabilities": "95000000000",
            "totalCurrentLiabilities": "20000000000",
            "currentAccountsPayable": "5000000000",
            "deferredRevenue": "3000000000",
            "currentDebt": "5000000000",
            "shortTermDebt": "5000000000",
            "totalNonCurrentLiabilities": "75000000000",
            "capitalLeaseObligations": "2000000000",
            "longTermDebt": "50000000000",
            "currentLongTermDebt": "0",
            "longTermDebtNoncurrent": "50000000000",
            "shortLongTermDebtTotal": "55000000000",
            "otherCurrentLiabilities": "7000000000",
            "otherNonCurrentLiabilities": "23000000000",
            "totalShareholderEquity": "40000000000",
            "treasuryStock": "5000000000",
            "retainedEarnings": "30000000000",
            "commonStock": "5000000000",
            "commonStockSharesOutstanding": "900000000"
        }
    ],
    "quarterlyReports": [
        {
            "fiscalDateEnding": "2023-09-30",
            "reportedCurrency": "USD",
            "totalAssets": "133000000000",
            "totalCurrentAssets": "24000000000",
            "cashAndCashEquivalentsAtCarryingValue": "7500000000",
            "cashAndShortTermInvestments": "9500000000",
            "inventory": "1900000000",
            "currentNetReceivables": "7800000000",
            "totalNonCurrentAssets": "109000000000",
            "propertyPlantEquipment": "14800000000",
            "accumulatedDepreciationAmortizationPPE": "4800000000",
            "intangibleAssets": "49500000000",
            "intangibleAssetsExcludingGoodwill": "19500000000",
            "goodwill": "30000000000",
            "investments": "29500000000",
            "longTermInvestments": "24500000000",
            "shortTermInvestments": "2000000000",
            "otherCurrentAssets": "4800000000",
            "otherNonCurrentAssets": "9800000000",
            "totalLiabilities": "94000000000",
            "totalCurrentLiabilities": "19500000000",
            "currentAccountsPayable": "4800000000",
            "deferredRevenue": "2900000000",
            "currentDebt": "4800000000",
            "shortTermDebt": "4800000000",
            "totalNonCurrentLiabilities": "74500000000",
            "capitalLeaseObligations": "1950000000",
            "longTermDebt": "49500000000",
            "currentLongTermDebt": "0",
            "longTermDebtNoncurrent": "49500000000",
            "shortLongTermDebtTotal": "54300000000",
            "otherCurrentLiabilities": "6800000000",
            "otherNonCurrentLiabilities": "22800000000",
            "totalShareholderEquity": "39000000000",
            "treasuryStock": "4800000000",
            "retainedEarnings": "29200000000",
            "commonStock": "5000000000",
            "commonStockSharesOutstanding": "900000000"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol=IBM&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns both annual and quarterly balance sheets
- All monetary values are in the reported currency
- Updated quarterly after earnings reports
