# Tradernet SDK vs yfinance: Replacement Feasibility Analysis

This document analyzes whether the Tradernet SDK can completely replace yfinance in the arduino-trader project.

## Executive Summary

**Conclusion: Tradernet SDK CANNOT fully replace yfinance** due to missing fundamental data, analyst recommendations, and industry classification. However, it can replace yfinance for **price data** (historical and current).

**Important Note**: We do **NOT** calculate fundamental data ourselves - we fetch all fundamental metrics (P/E, margins, ROE, etc.) directly from yfinance. We only calculate **scores** from that data and **metrics from price data** (CAGR, Sharpe, RSI, etc.).

**Recommendation**: Use a **hybrid approach**:
- **Tradernet SDK**: Price data (quotes, historical candles) - already implemented
- **yfinance**: Fundamental data, analyst data, industry classification - keep for now
- **Future**: Consider alternative data providers for fundamentals if Tradernet adds this capability

---

## Detailed Feature Comparison

### 1. Price Data (Historical & Current)

#### yfinance Usage
```python
# Historical prices
prices = yahoo.get_historical_prices("AAPL.US", period="1y")

# Current prices (single)
price = yahoo.get_current_price("AAPL.US")

# Batch quotes
quotes = yahoo.get_batch_quotes({"AAPL.US": "AAPL", "MSFT.US": "MSFT"})
```

#### Tradernet SDK Capability
✅ **FULLY SUPPORTED**

```python
# Historical prices (candles)
client.get_historical_prices(symbol, start=start, end=end)

# Current quotes (single)
client.get_quote(symbol)

# Batch quotes
client.get_quotes_raw(symbols)
```

**Verdict**: ✅ **Can replace** - Tradernet already provides this via `get_candles()` and `get_quotes()`

---

### 2. Fundamental Data

#### yfinance Usage
```python
fundamentals = yahoo.get_fundamental_data("AAPL.US")
# Returns:
# - pe_ratio, forward_pe, peg_ratio
# - price_to_book
# - revenue_growth, earnings_growth
# - profit_margin, operating_margin
# - roe (Return on Equity)
# - debt_to_equity, current_ratio
# - market_cap
# - dividend_yield, five_year_avg_dividend_yield
```

**Used in**: Stock scoring (`scoring_service.py`), fundamental analysis

#### Tradernet SDK Capability
❌ **NOT SUPPORTED**

The Tradernet SDK provides:
- `security_info(symbol)` - Returns basic security info (lot size, trading currency, etc.)
- `get_quotes()` - Returns current price, volume, change
- **NO fundamental metrics** (P/E, PEG, margins, ROE, etc.)

**Verdict**: ❌ **Cannot replace** - Tradernet does not provide fundamental financial metrics

**Impact**: **CRITICAL** - Fundamental data is essential for stock scoring. Without it, the scoring system cannot function.

---

### 3. Analyst Recommendations & Price Targets

#### yfinance Usage
```python
analyst_data = yahoo.get_analyst_data("AAPL.US")
# Returns:
# - recommendation (strongBuy, buy, hold, sell, strongSell)
# - target_price (mean analyst target)
# - current_price
# - upside_pct (potential upside)
# - num_analysts
# - recommendation_score (0-1 normalized)
```

**Used in**: Opinion scoring group (`opinion.py`), stock scoring

#### Tradernet SDK Capability
❌ **NOT SUPPORTED**

The Tradernet SDK provides:
- News related to securities (via `authorized_request` or news endpoints)
- **NO analyst recommendations**
- **NO price targets**

**Verdict**: ❌ **Cannot replace** - Tradernet does not provide analyst recommendations

**Impact**: **HIGH** - Analyst data is used in the "opinion" scoring group (10% weight). Scoring can work without it, but with reduced accuracy.

---

### 4. Industry Classification

#### yfinance Usage
```python
industry = yahoo.get_stock_industry("AAPL.US")
# Returns Yahoo Finance industry/sector directly (e.g., "Consumer Electronics", "Drug Manufacturers", etc.)
```

**Used in**: Diversification scoring, portfolio analysis

#### Tradernet SDK Capability
❌ **NOT SUPPORTED**

The Tradernet SDK provides:
- `security_info(symbol)` - Basic security metadata
- **NO industry/sector classification**

**Verdict**: ❌ **Cannot replace** - Tradernet does not provide industry classification

**Impact**: **MEDIUM** - Industry data is used for diversification scoring (8% weight). Can be manually maintained in the stocks table as a workaround.

---

### 5. Historical Price Data (Charts)

#### yfinance Usage
```python
# Used in charts.py as fallback
prices = yahoo.get_historical_prices("AAPL.US", period="10y")
```

#### Tradernet SDK Capability
✅ **SUPPORTED**

```python
# Already implemented in tradernet.py
client.get_historical_prices(symbol, start=start, end=end)
```

**Verdict**: ✅ **Can replace** - Tradernet already provides this via `get_candles()`

**Current Status**: Charts API already uses Tradernet as primary source, Yahoo as fallback.

---

## Current Implementation Status

### Already Using Tradernet for Prices

1. **Charts API** (`charts.py`):
   - Primary: Tradernet `get_historical_prices()`
   - Fallback: Yahoo `get_historical_prices()`

2. **Price Sync** (`sync_cycle.py`):
   - Currently uses Yahoo `get_batch_quotes()`
   - Could switch to Tradernet `get_quotes_raw()`

3. **Daily Sync** (`daily_sync.py`):
   - Uses Yahoo for price updates
   - Could use Tradernet quotes

### Still Requiring yfinance

1. **Stock Scoring** (`scoring_service.py`):
   - Requires: Fundamentals (P/E, margins, ROE, etc.)
   - Requires: Analyst recommendations
   - Optional: Industry (can be manual)

2. **Daily Pipeline** (`daily_pipeline.py`):
   - Fetches fundamentals for scoring
   - Fetches analyst data for scoring

3. **Optimizer** (`optimizer.py`):
   - Uses fundamentals for analysis

---

## Tradernet SDK Methods Available

Based on codebase analysis, the Tradernet SDK provides:

### Market Data
- ✅ `get_quotes(symbols)` - Current quotes
- ✅ `get_candles(symbol, start, end)` - Historical OHLC data
- ✅ `security_info(symbol)` - Basic security info (lot size, currency)

### Account Data
- ✅ `account_summary()` - Full account overview
- ✅ `get_trades_history()` - Executed trades
- ✅ `get_placed(active=True)` - Pending orders
- ✅ `corporate_actions()` - Corporate actions (dividends, splits)

### Trading
- ✅ `buy(symbol, quantity)` - Place buy order
- ✅ `sell(symbol, quantity)` - Place sell order
- ✅ `cancel(order_id)` - Cancel order

### Custom Requests
- ✅ `authorized_request(method, params, version)` - Custom API calls

**Missing Methods**:
- ❌ No fundamental data methods
- ❌ No analyst recommendation methods
- ❌ No industry classification methods

---

## Replacement Strategy Options

### Option 1: Keep yfinance (Recommended)
**Pros**:
- ✅ All features work immediately
- ✅ No code changes needed
- ✅ Free, no API limits
- ✅ Comprehensive data coverage

**Cons**:
- ❌ Additional dependency
- ❌ Requires symbol conversion (Tradernet → Yahoo format)

**Effort**: None (current state)

---

### Option 2: Hybrid Approach (Best Balance)
**Use Tradernet for prices, yfinance for fundamentals**

**Implementation**:
1. Replace Yahoo price fetching with Tradernet:
   - `sync_cycle.py`: Use `client.get_quotes_raw()` instead of `yahoo.get_batch_quotes()`
   - `daily_sync.py`: Use `client.get_quote()` instead of `yahoo.get_current_price()`
   - Remove Yahoo fallback from `charts.py` (Tradernet is primary)

2. Keep yfinance for:
   - `get_fundamental_data()` - Stock scoring
   - `get_analyst_data()` - Opinion scoring
   - `get_stock_industry()` - Diversification (or make manual)

**Pros**:
- ✅ Reduces yfinance usage (only for fundamentals)
- ✅ Uses Tradernet for price data (already authenticated)
- ✅ Maintains all functionality

**Cons**:
- ❌ Still requires yfinance dependency
- ❌ Requires symbol conversion for fundamentals

**Effort**: Medium (replace price fetching, keep fundamentals)

---

### Option 3: Remove yfinance, Accept Limitations
**Remove yfinance, use Tradernet only**

**Impact**:
- ❌ **Stock scoring will break** - No fundamental data
- ❌ **Opinion scoring reduced** - No analyst recommendations
- ⚠️ **Diversification scoring** - Can work with manual industry data
- ✅ **Price data** - Fully functional

**Workarounds**:
1. **Fundamentals**: Manually maintain in stocks table (not scalable)
2. **Analyst Data**: Remove opinion scoring group (reduce score accuracy)
3. **Industry**: Manually maintain in stocks table (feasible)

**Pros**:
- ✅ Single dependency (Tradernet only)
- ✅ No symbol conversion needed

**Cons**:
- ❌ **CRITICAL**: Stock scoring system will not work
- ❌ Reduced scoring accuracy
- ❌ Manual data maintenance required

**Verdict**: ❌ **NOT RECOMMENDED** - Would break core functionality

---

### Option 4: Alternative Data Providers
**Replace yfinance with another fundamental data provider**

**Options**:
1. **Alpha Vantage** - Free tier, fundamentals available
2. **Financial Modeling Prep** - Free tier, comprehensive fundamentals
3. **Polygon.io** - Paid, comprehensive data
4. **IEX Cloud** - Paid, good fundamentals

**Pros**:
- ✅ Can get fundamentals from alternative source
- ✅ May have better data quality
- ✅ Can remove yfinance

**Cons**:
- ❌ Additional API integration required
- ❌ May have rate limits or costs
- ❌ Requires API keys

**Effort**: High (new integration, testing)

---

## Recommended Action Plan

### Phase 1: Optimize Current Usage (Low Risk)
1. ✅ **Already done**: Charts use Tradernet as primary
2. 🔄 **Next**: Replace Yahoo price fetching with Tradernet in:
   - `sync_cycle.py` - Use `get_quotes_raw()` for batch quotes
   - `daily_sync.py` - Use `get_quote()` for single prices
3. ✅ **Keep**: yfinance for fundamentals and analyst data

**Result**: Reduced yfinance usage, all features work

### Phase 2: Evaluate Alternatives (If Needed)
1. Monitor Tradernet SDK updates for fundamental data support
2. Evaluate alternative data providers if yfinance becomes unreliable
3. Consider manual industry data if needed

### Phase 3: Full Migration (Future)
Only if Tradernet adds fundamental/analyst data support

---

## Code Changes Required (Option 2: Hybrid)

### 1. Replace Price Fetching in `sync_cycle.py`

**Current**:
```python
quotes = yahoo.get_batch_quotes(symbol_yahoo_map)
```

**New**:
```python
symbols = list(symbol_yahoo_map.keys())
quotes_raw = tradernet_client.get_quotes_raw(symbols)
quotes = {sym: float(q.get("ltp", 0)) for sym, q in quotes_raw.items()}
```

### 2. Replace Price Fetching in `daily_sync.py`

**Current**:
```python
price = yahoo.get_current_price(symbol)
```

**New**:
```python
quote = tradernet_client.get_quote(symbol)
price = quote.price if quote else None
```

### 3. Keep yfinance for Fundamentals

**No changes needed** - Continue using:
- `yahoo.get_fundamental_data()`
- `yahoo.get_analyst_data()`
- `yahoo.get_stock_industry()` (or make manual)

---

## Testing Checklist

If implementing Option 2 (Hybrid):

- [ ] Test Tradernet batch quotes match Yahoo batch quotes
- [ ] Test Tradernet single quotes match Yahoo single quotes
- [ ] Verify price sync still works correctly
- [ ] Verify charts still work (Tradernet primary)
- [ ] Verify fundamentals still work (yfinance)
- [ ] Verify analyst data still works (yfinance)
- [ ] Test error handling when Tradernet unavailable
- [ ] Test symbol conversion (Tradernet format)

---

## Conclusion

**Tradernet SDK CANNOT fully replace yfinance** because:

1. ❌ **No fundamental data** (P/E, margins, ROE, etc.) - **CRITICAL**
2. ❌ **No analyst recommendations** - **HIGH IMPACT**
3. ❌ **No industry classification** - **MEDIUM IMPACT** (can work around)

**Recommended Approach**: **Hybrid**
- Use Tradernet for **price data** (quotes, historical)
- Keep yfinance for **fundamental data** and **analyst data**
- Consider manual industry data or keep yfinance for it

This provides the best balance of:
- ✅ Reduced dependencies (less yfinance usage)
- ✅ All features functional
- ✅ Reasonable implementation effort

**Next Steps**:
1. Implement Phase 1 (replace price fetching with Tradernet)
2. Monitor Tradernet SDK updates for fundamental data support
3. Evaluate alternative providers if needed in the future
