# INSIDER_TRANSACTIONS

Insider transaction data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API offers data on the latest and historical insider transactions, providing transparency into insider buying and selling activities.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `INSIDER_TRANSACTIONS` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "symbol": "IBM",
    "name": "International Business Machines Corporation",
    "insider_transactions": [
        {
            "filing_date": "2024-01-10",
            "transaction_date": "2024-01-08",
            "transaction_code": "P",
            "transaction_type": "Purchase",
            "owner_name": "John Doe",
            "owner_title": "CEO",
            "shares_traded": "10000",
            "price": "185.50",
            "shares_held": "500000",
            "value": "1855000"
        },
        {
            "filing_date": "2024-01-05",
            "transaction_date": "2024-01-03",
            "transaction_code": "S",
            "transaction_type": "Sale",
            "owner_name": "Jane Smith",
            "owner_title": "CFO",
            "shares_traded": "5000",
            "price": "184.00",
            "shares_held": "200000",
            "value": "920000"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=INSIDER_TRANSACTIONS&symbol=IBM&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Includes both purchases and sales by company insiders
- Transaction codes: P (Purchase), S (Sale), A (Acquisition), D (Disposition)
- Shows filing date, transaction date, and transaction details
- Useful for tracking insider sentiment
