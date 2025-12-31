# Stock Data Issues - Investigation Report

## Summary

Three stocks in the universe have incomplete data (missing country and industry fields):
1. **AETF.GR** - ALPHA ETF FTSE Athex Large Cap Equity UCITS
2. **IPX.EU** - Impax Asset Management Group PL
3. **UKW.EU** - Greencoat UK Wind

## Root Cause

The stocks have **ISINs stored as `yahoo_symbol`** instead of proper Yahoo Finance ticker symbols:
- AETF.GR: `yahoo_symbol = "GRF000153004"` (should be `NULL` to use `AETF.AT` via converter)
- IPX.EU: `yahoo_symbol = "GB0004905260.SG"` (invalid Yahoo symbol)
- UKW.EU: `yahoo_symbol = "GB00B8SC6K54"` (invalid Yahoo symbol)

Yahoo Finance does not recognize ISINs as valid ticker symbols, so API calls to fetch country/industry data fail silently.

## Investigation Details

### How `yahoo_symbol` Gets Set

When stocks are added via `StockSetupService.add_stock_by_identifier()`:
- `SymbolResolver.resolve()` returns `SymbolInfo` with `yahoo_symbol = isin` (line 174 in `symbol_resolver.py`)
- This ISIN is then stored directly in the database

This works for some stocks but fails when Yahoo Finance doesn't recognize the ISIN format.

### Symbol Converter Behavior

The `get_yahoo_symbol()` function in `symbol_converter.py`:
- If `yahoo_override` is provided (non-null), it uses that value directly
- Otherwise, it applies conversions:
  - `.US` → strips suffix (AAPL.US → AAPL)
  - `.GR` → converts to `.AT` (AETF.GR → AETF.AT)
  - Other suffixes → passes through unchanged (IPX.EU → IPX.EU, UKW.EU → UKW.EU)

### Current State After Fix

We cleared the `yahoo_symbol` field (set to `NULL`) for all three stocks using the API:
```bash
curl -X PUT http://localhost:8000/api/securities/{ISIN} -H 'Content-Type: application/json' -d '{"yahoo_symbol": ""}'
```

After clearing and running refresh:
- **AETF.GR**: Uses `AETF.AT` (via converter) - Yahoo Finance returns no country/industry data
- **IPX.EU**: Uses `IPX.EU` (passed through) - Yahoo Finance doesn't recognize this format
- **UKW.EU**: Uses `UKW.EU` (passed through) - Yahoo Finance doesn't recognize this format

**Current database state:**
| Symbol | yahoo_symbol | country | industry | fullExchangeName |
|--------|--------------|---------|----------|------------------|
| AETF.GR | NULL | NULL | NULL | Athens |
| IPX.EU | NULL | NULL | NULL | Stuttgart |
| UKW.EU | NULL | NULL | NULL | LSE |

### Why Refresh Still Fails

Even with correct symbol conversion, Yahoo Finance API doesn't return country/industry data for these symbols:
- `AETF.AT` - Yahoo Finance may not have this ETF listed or uses different symbol
- `IPX.EU` - `.EU` suffix not recognized by Yahoo Finance (UK stocks typically use `.L` for LSE, German stocks use `.DE` or `.F` for Frankfurt)
- `UKW.EU` - Same issue, might need to be `UKW.L` for London Stock Exchange

**Note:** The `fullExchangeName` field already has values ("Athens", "Stuttgart", "LSE"), suggesting these were set during initial stock creation. However, the country field wasn't inferred because:
1. Yahoo Finance API returns `(None, None)` for these symbols
2. The fallback logic in `_detect_and_update_country_and_exchange()` only runs when Yahoo returns an exchange but no country
3. Since Yahoo returns neither, the fallback never executes

## Recommendations

1. **For AETF.GR**: Verify if `AETF.AT` is the correct Yahoo Finance symbol. May need manual lookup.
2. **For IPX.EU**: Try `IPX.L` (London Stock Exchange format) as the `yahoo_symbol`
3. **For UKW.EU**: Try `UKW.L` (London Stock Exchange format) as the `yahoo_symbol`

### Finding Correct Yahoo Symbols

To find the correct Yahoo Finance symbols:
1. Search for the stock on finance.yahoo.com
2. Check the URL - it typically shows the ticker symbol
3. Update the `yahoo_symbol` field via API:
   ```bash
   curl -X PUT http://localhost:8000/api/securities/{ISIN} \
     -H 'Content-Type: application/json' \
     -d '{"yahoo_symbol": "CORRECT.SYMBOL"}'
   ```
4. Run refresh to populate country/industry:
   ```bash
   curl -X POST http://localhost:8000/api/securities/{ISIN}/refresh-data
   ```

## Database Query to Check Incomplete Stocks

```sql
SELECT symbol, name, country, industry, fullExchangeName, yahoo_symbol, isin
FROM stocks
WHERE country IS NULL OR industry IS NULL OR fullExchangeName IS NULL
   OR yahoo_symbol IS NULL OR isin IS NULL OR currency IS NULL
ORDER BY symbol;
```

## Files Involved

- `app/infrastructure/external/yahoo/symbol_converter.py` - Symbol conversion logic
- `app/domain/services/symbol_resolver.py` - Sets `yahoo_symbol = isin` (line 174)
- `app/jobs/stocks_data_sync.py` - `_detect_and_update_country_and_exchange()` function
- `app/api/securities.py` - Update endpoint (`PUT /api/securities/{isin}`)
