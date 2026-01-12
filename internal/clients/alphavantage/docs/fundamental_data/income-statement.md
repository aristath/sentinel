# INCOME_STATEMENT

Income statement data for a company.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns annual and quarterly income statements for a specified company.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `INCOME_STATEMENT` |
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
            "grossProfit": "30000000000",
            "totalRevenue": "60000000000",
            "costOfRevenue": "30000000000",
            "costofGoodsAndServicesSold": "30000000000",
            "operatingIncome": "9000000000",
            "sellingGeneralAndAdministrative": "15000000000",
            "researchAndDevelopment": "6000000000",
            "operatingExpenses": "21000000000",
            "investmentIncomeNet": "500000000",
            "netInterestIncome": "500000000",
            "interestIncome": "600000000",
            "interestExpense": "100000000",
            "nonInterestIncome": "0",
            "otherNonOperatingIncome": "200000000",
            "depreciation": "2000000000",
            "depreciationAndAmortization": "2500000000",
            "incomeBeforeTax": "9200000000",
            "incomeTaxExpense": "2000000000",
            "interestAndDebtExpense": "100000000",
            "netIncomeFromContinuingOperations": "7200000000",
            "comprehensiveIncomeNetOfTax": "7200000000",
            "ebit": "9000000000",
            "ebitda": "11500000000",
            "netIncome": "7200000000"
        }
    ],
    "quarterlyReports": [
        {
            "fiscalDateEnding": "2023-09-30",
            "reportedCurrency": "USD",
            "grossProfit": "7500000000",
            "totalRevenue": "15000000000",
            "costOfRevenue": "7500000000",
            "costofGoodsAndServicesSold": "7500000000",
            "operatingIncome": "2250000000",
            "sellingGeneralAndAdministrative": "3750000000",
            "researchAndDevelopment": "1500000000",
            "operatingExpenses": "5250000000",
            "investmentIncomeNet": "125000000",
            "netInterestIncome": "125000000",
            "interestIncome": "150000000",
            "interestExpense": "25000000",
            "nonInterestIncome": "0",
            "otherNonOperatingIncome": "50000000",
            "depreciation": "500000000",
            "depreciationAndAmortization": "625000000",
            "incomeBeforeTax": "2300000000",
            "incomeTaxExpense": "500000000",
            "interestAndDebtExpense": "25000000",
            "netIncomeFromContinuingOperations": "1800000000",
            "comprehensiveIncomeNetOfTax": "1800000000",
            "ebit": "2250000000",
            "ebitda": "2875000000",
            "netIncome": "1800000000"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol=IBM&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns both annual and quarterly income statements
- All monetary values are in the reported currency
- Updated quarterly after earnings reports
