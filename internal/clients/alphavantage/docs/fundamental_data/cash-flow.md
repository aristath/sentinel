# CASH_FLOW

Cash flow statement data for a company.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns annual and quarterly cash flow statements for a specified company.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `CASH_FLOW` |
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
            "operatingCashflow": "15000000000",
            "paymentsForOperatingActivities": "5000000000",
            "proceedsFromOperatingActivities": "20000000000",
            "changeInOperatingLiabilities": "1000000000",
            "changeInOperatingAssets": "-2000000000",
            "depreciationDepletionAndAmortization": "2500000000",
            "capitalExpenditures": "-3000000000",
            "changeInReceivables": "-1000000000",
            "changeInInventory": "-500000000",
            "profitLoss": "7200000000",
            "cashflowFromInvestment": "-5000000000",
            "cashflowFromFinancing": "-8000000000",
            "proceedsFromRepaymentsOfShortTermDebt": "0",
            "paymentsForRepurchaseOfCommonStock": "-2000000000",
            "paymentsForRepurchaseOfEquity": "-2000000000",
            "paymentsForRepurchaseOfPreferredStock": "0",
            "dividendPayout": "-6000000000",
            "dividendPayoutCommonStock": "-6000000000",
            "dividendPayoutPreferredStock": "0",
            "proceedsFromIssuanceOfCommonStock": "0",
            "proceedsFromIssuanceOfLongTermDebtAndCapitalSecuritiesNet": "0",
            "proceedsFromIssuanceOfPreferredStock": "0",
            "proceedsFromRepurchaseOfEquity": "0",
            "proceedsFromSaleOfTreasuryStock": "0",
            "changeInCashAndCashEquivalents": "2000000000",
            "changeInExchangeRate": "0",
            "netIncome": "7200000000"
        }
    ],
    "quarterlyReports": [
        {
            "fiscalDateEnding": "2023-09-30",
            "reportedCurrency": "USD",
            "operatingCashflow": "3750000000",
            "paymentsForOperatingActivities": "1250000000",
            "proceedsFromOperatingActivities": "5000000000",
            "changeInOperatingLiabilities": "250000000",
            "changeInOperatingAssets": "-500000000",
            "depreciationDepletionAndAmortization": "625000000",
            "capitalExpenditures": "-750000000",
            "changeInReceivables": "-250000000",
            "changeInInventory": "-125000000",
            "profitLoss": "1800000000",
            "cashflowFromInvestment": "-1250000000",
            "cashflowFromFinancing": "-2000000000",
            "proceedsFromRepaymentsOfShortTermDebt": "0",
            "paymentsForRepurchaseOfCommonStock": "-500000000",
            "paymentsForRepurchaseOfEquity": "-500000000",
            "paymentsForRepurchaseOfPreferredStock": "0",
            "dividendPayout": "-1500000000",
            "dividendPayoutCommonStock": "-1500000000",
            "dividendPayoutPreferredStock": "0",
            "proceedsFromIssuanceOfCommonStock": "0",
            "proceedsFromIssuanceOfLongTermDebtAndCapitalSecuritiesNet": "0",
            "proceedsFromIssuanceOfPreferredStock": "0",
            "proceedsFromRepurchaseOfEquity": "0",
            "proceedsFromSaleOfTreasuryStock": "0",
            "changeInCashAndCashEquivalents": "500000000",
            "changeInExchangeRate": "0",
            "netIncome": "1800000000"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=CASH_FLOW&symbol=IBM&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns both annual and quarterly cash flow statements
- All monetary values are in the reported currency
- Updated quarterly after earnings reports
- Includes operating, investing, and financing cash flows
