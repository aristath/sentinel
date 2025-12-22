# Cash Flows API Investigation Results

## Summary

After thorough investigation of the Tradernet API, here's what we found regarding cash flow data availability.

## Available Cash Flow Data Sources

### 1. getClientCpsHistory (get_requests_history)
**Endpoint**: `getClientCpsHistory`  
**Method**: `client.get_requests_history()` or `client.authorized_request('getClientCpsHistory', {...}, version=2)`

**Findings**:
- Returns **42 records total** (all available history)
- Date range: 2024-05-07 to 2025-12-04
- **NO DEPOSITS** found in this endpoint
- Only cash flow types found:
  - **Type 337**: Withdrawals (25 records) - includes withdrawal fees in `total_commission` field
  - **Type 297**: Structured product purchases (1 record)
  - Other types (217, 269, 278, 290, 355, 356): Document/account management, not cash flows

**Parameters**:
- `limit`: Maximum records (default: all available)
- `date_from`: Start date (YYYY-MM-DD format)
- `date_to`: End date (YYYY-MM-DD format)
- `cpsDocId`: Filter by type_doc_id (doesn't seem to work as expected)

**Withdrawal Fees**:
- Embedded in withdrawal records (type 337)
- Field: `total_commission` in params
- Currency: `commission_currency` in params
- Total found: 56.89 EUR across 25 withdrawals
- **Now extracted as separate transactions** in our implementation

### 2. corporate_actions
**Endpoint**: `corporate_actions`  
**Method**: `client.corporate_actions()`

**Findings**:
- **2,606 executed actions** that result in cash flows
- Types:
  - **Dividends**: 2,219 executed
  - **Coupons**: 228 executed
  - **Maturities**: 77 executed
  - **Partial maturities**: 2 executed
  - **Conversions**: 1 executed
  - **Splits**: 79 executed (not cash flow)

**Data Structure**:
- `amount_per_one`: Dividend/coupon per share
- `executed_count`: Number of shares
- `currency`: Payment currency
- `pay_date`: Payment date
- `ex_date`: Ex-dividend date
- Total amount = `amount_per_one × executed_count`

**Status**: ✅ **Now included in get_all_cash_flows()**

### 3. get_trades_history
**Endpoint**: `get_trades_history`  
**Method**: `client.get_trades_history()`

**Findings**:
- **200 trades** in history
- Contains trading fees/commissions:
  - Field: `commission`
  - Currency: `commission_currency`
  - Date: `date`

**Status**: ✅ **Now included in get_all_cash_flows()**

## Missing Cash Flow Types

### Deposits
- **NOT available** via API
- This explains why the existing codebase has a `manual_deposits` setting
- No deposit type_doc_id found in getClientCpsHistory
- No separate deposit endpoint found

### Card Payments
- Card information is present in withdrawal records (type 337):
  - `card_bank`: Bank name
  - `card_number`: Masked card number
  - `cardholder`: Cardholder name
- But these are withdrawals, not deposits
- **Card deposits are NOT available via API**

### Negative Balance Fees
- **NOT found** in any endpoint
- May not exist, or may be included in other fee types
- Could potentially be in account summary, but not found there

### Other Fees
- Withdrawal fees: ✅ Found (embedded in withdrawals)
- Trading fees: ✅ Found (in trades history)
- Structured product fees: ✅ Found (in structured product purchases)
- Negative balance fees: ❌ Not found
- Account maintenance fees: ❌ Not found

## Implementation Status

### ✅ Implemented
1. **Withdrawals** (type 337) - from getClientCpsHistory
2. **Withdrawal fees** - extracted from withdrawal records
3. **Structured product purchases** (type 297) - from getClientCpsHistory
4. **Structured product fees** - extracted from purchase records
5. **Dividends** - from corporate_actions
6. **Coupons** - from corporate_actions
7. **Maturities** - from corporate_actions
8. **Trading fees/commissions** - from get_trades_history

### ❌ Not Available via API
1. **Deposits** - Must be tracked manually (existing `manual_deposits` setting)
2. **Card payment deposits** - Not available
3. **Negative balance fees** - Not found
4. **Account maintenance fees** - Not found

## Recommendations

1. **Keep manual deposits setting** - Deposits are not available via API
2. **Use the implemented solution** - It captures all available cash flows:
   - ~2,600+ corporate actions (dividends, coupons, maturities)
   - 25 withdrawals + 25 withdrawal fees
   - 1 structured product purchase + fee
   - 200 trading fees (if any have non-zero commissions)
3. **Total expected transactions**: ~2,850+ cash flow records

## API Documentation

Official documentation: https://tradernet.com/tradernet-api/get-client-cps-history

The documentation mentions:
- Parameters: `date_from`, `date_to`, `limit`, `cpsDocId` (type_doc_id filter)
- Returns: List of client request/transaction history
- Note: The API only returns withdrawals, not deposits
