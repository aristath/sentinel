# Product Type Differentiation Strategy

## Status: 📋 **DESIGN PHASE**

This document outlines the strategy for treating different product types (EQUITY, ETF, ETC, MUTUALFUND) differently in the optimizer and planner systems.

## Current State

### Product Types Tracked
The system currently tracks product types:
- `EQUITY` - Individual stocks/shares
- `ETF` - Exchange Traded Funds
- `ETC` - Exchange Traded Commodities
- `MUTUALFUND` - Mutual funds (some UCITS products)
- `CASH` - Cash positions (synthetic securities)
- `UNKNOWN` - Unknown type

### Product Type Detection

**Source: Yahoo Finance (not Tradernet)**

Product types are determined from **Yahoo Finance's `quoteType` field**, with heuristics as fallback:

1. **Primary Method: Yahoo Finance `quoteType`**
   - Location: `trader/internal/modules/universe/security_setup_service.go::detectProductType()`
   - Calls: `yahooClient.GetQuoteType()` → gets `quoteType` from Yahoo Finance API
   - Direct mappings:
     - `quoteType == "EQUITY"` → `ProductTypeEquity`
     - `quoteType == "ETF"` → `ProductTypeETF`
     - `quoteType == "MUTUALFUND"` → Uses heuristics (see below)

2. **Simplified Heuristics for MUTUALFUND (Only Distinguish ETCs)**
   - Location: `trader/internal/modules/universe/product_type.go::FromYahooQuoteType()`
   - Yahoo often returns `MUTUALFUND` for UCITS ETFs and ETCs
   - **Simplified approach**: Only distinguish ETCs (commodities) - different asset class
   - Uses product name to detect:
     - **ETC indicators**: "ETC", "COMMODITY", "GOLD", "SILVER", "OIL", etc. → `ProductTypeETC`
     - **Everything else**: → `ProductTypeETF` (treat UCITS ETFs and mutual funds the same)
   - **Rationale**: ETFs and Mutual Funds have similar portfolio behavior (both are diversified products). Only ETCs need different treatment (commodities are a different asset class).

3. **Fallback: Name-based heuristics**
   - Location: `trader/internal/modules/universe/security_setup_service.go::detectProductTypeFromName()`
   - Used when Yahoo Finance is unavailable
   - Checks name for "ETF", commodity keywords, defaults to EQUITY

### Simplified Heuristics Rationale

**Decision: Only distinguish ETCs (commodities), treat ETFs and Mutual Funds identically**

**Why:**
1. **ETCs are a different asset class:**
   - Commodities have different risk/return profiles
   - Different correlation with equities
   - Need different treatment (lower concentration limits, commodity-specific considerations)

2. **ETFs and Mutual Funds are functionally equivalent for portfolio management:**
   - Both are diversified products
   - Both have similar risk/return characteristics
   - Structural differences (trading, fees) don't affect portfolio optimization
   - UCITS ETFs are just ETFs with regulatory compliance - same behavior

3. **Simpler code:**
   - Less heuristics to maintain
   - Fewer edge cases
   - Clearer logic: only distinguish commodities

**Implementation Impact:**
- In `FromYahooQuoteType()`: Only check for ETC indicators, everything else in MUTUALFUND → ETF
- In optimizer/planner: Treat `ETF` and `MUTUALFUND` identically (same concentration limits, same scoring)
- This simplifies the code while maintaining correct portfolio management behavior

**Files:**
- `trader/internal/modules/universe/product_type.go` - Product type constants and detection logic
- `trader/internal/modules/universe/security_setup_service.go` - Detection orchestration
- `trader/internal/clients/yahoo/client.go` - Yahoo Finance API client

**Note:** Tradernet is NOT used for product type detection. It's only used for:
- ISIN lookup
- Symbol resolution
- Trading execution

### Current Implementation
**Product types are stored but NOT used:**
- ✅ Product type is detected from Yahoo Finance (with heuristics)
- ✅ Product type is stored in `universe.db`
- ✅ Product type is available in `Security` model
- ❌ Optimizer does NOT differentiate by product type
- ❌ Planner does NOT differentiate by product type
- ❌ Scoring system does NOT differentiate by product type
- ❌ Evaluation system does NOT differentiate by product type

**All securities are treated identically:**
- Same expected returns calculation (70% CAGR + 30% score)
- Same risk model (covariance matrix - but this naturally captures differences)
- Same concentration limits (20% max per security)
- Same opportunity scoring (value, quality, dividends)
- Same quality gates (fundamentals, consistency)

### Important Limitation: Missing Country/Industry Data

**Problem:** For non-EQUITY products (ETFs, Mutual Funds, ETCs), Yahoo Finance often doesn't provide country or industry information.

**Current Behavior:**
- **Optimizer**: Missing country/industry → grouped into "OTHER"
  - If no target exists for "OTHER", these securities are not constrained by country/industry
  - They're still included in optimization, just not subject to geographic/industry constraints
- **Planner**: Missing country/industry → uses "OTHER" or neutral scores
  - Diversification scorer returns neutral (0.5) when country/industry is missing
  - Securities are not excluded, just not prioritized for diversification

**Impact:**
- ETFs/Mutual Funds without country/industry can't be used for geographic/industry diversification
- They're still optimized and planned, but diversification constraints don't apply
- This is acceptable since ETFs are already diversified by design

**Requirement:**
- ✅ Both optimizer and planner must gracefully handle missing country/industry
- ✅ Securities should NOT be excluded due to missing country/industry
- ✅ Missing data should result in neutral/ignored diversification, not errors

## Financial Analysis

### Why Product Types Should Be Treated Differently

#### 1. Risk Characteristics

**Stocks (EQUITY):**
- High idiosyncratic risk (company-specific)
- Higher volatility
- Potential for higher returns
- Concentration risk if over-weighted

**ETFs & Mutual Funds:**
- Lower idiosyncratic risk (diversified by design)
- Lower volatility (usually)
- More stable but lower upside potential
- Better for portfolio stabilization
- **Note**: Treated identically for portfolio management purposes

**ETCs:**
- Commodity exposure (different asset class)
- Different risk profile (commodity cycles)
- Lower correlation with equities

**Implication:**
- ETFs should naturally show lower volatility in covariance matrix
- Stocks may need tighter concentration limits
- ETCs provide diversification but need careful allocation

#### 2. Expected Returns

**Current Approach:** 70% CAGR + 30% score (same for all)

**Consideration:**
- ETFs: CAGR reflects underlying index/strategy (more predictable)
- Stocks: CAGR reflects company performance (more variable)
- ETFs may have slightly lower CAGR due to diversification trade-off

**Recommendation:**
- Keep same formula (data should reflect differences naturally)
- No explicit discount needed if historical data is accurate
- Covariance matrix will naturally capture volatility differences

#### 3. Opportunity Identification

**Stocks:**
- Value opportunities (P/E, below 52W high) are meaningful
- Quality gates matter more (company fundamentals)
- Dividend yield is company-specific

**ETFs & Mutual Funds:**
- Value opportunities less meaningful (tracking an index/strategy)
- Quality gates less relevant (diversification is the quality)
- Dividend yield reflects underlying holdings
- Should focus on: tracking error, expense ratio, liquidity, AUM
- **Note**: Treated identically for portfolio management purposes

#### 4. Concentration Constraints

**Current:** 20% max per security (same for all)

**Consideration:**
- 20% in a single stock = high concentration risk
- 20% in a broad-market ETF = diversified exposure
- Different product types have different risk profiles

**Recommendation:**
- Stocks: 15-20% max (tighter limit)
- Broad-market ETFs: 30-40% max (higher limit)
- Sector/country ETFs: 20% max (similar to stocks)
- ETCs: 10-12% max (commodity exposure limit, lower for retirement funds)

#### 5. Scoring System

**Current:** Same scoring weights for all (25% long-term, 20% fundamentals, 18% dividends, etc.)

**Consideration:**
- Stocks: Fundamentals matter (profit margin, debt-to-equity, current ratio)
- ETFs: Fundamentals less relevant (tracking an index)
- ETFs: Should focus on tracking quality, consistency, expense ratio

**Recommendation:**
- Stocks: Keep current scoring weights
- ETFs & Mutual Funds: Adjust weights (treated identically):
  - Fundamentals: 20% → 10% (less relevant)
  - Long-term/consistency: 25% → 35% (tracking quality matters)
  - Keep others similar

## Recommendations

### Critical: Handling Missing Country/Industry Data

**Problem:** ETFs, Mutual Funds, and ETCs often don't have country/industry data from Yahoo Finance.

**Current Behavior (Verified):**
- ✅ **Optimizer**: Missing country/industry → grouped into "OTHER"
  - Location: `trader/internal/modules/optimization/constraints.go::buildSectorConstraints()`
  - Lines 173-175: `if country == "" { country = "OTHER" }`
  - Lines 187-189: `if industry == "" { industry = "OTHER" }`
  - If no target exists for "OTHER", securities are not constrained by country/industry
  - **They're still included in optimization** - just not subject to geographic/industry constraints
- ✅ **Planner**: Missing country/industry → neutral diversification scores
  - Location: `trader/internal/modules/scoring/scorers/diversification.go`
  - Location: `trader/internal/evaluation/scoring.go`
  - Returns neutral (0.5) when country/industry is missing
  - **Securities are not excluded** - just not prioritized for diversification

**Requirement:**
- ✅ Both systems already handle this correctly
- ✅ Securities are NOT excluded due to missing country/industry
- ✅ Missing data results in neutral/ignored diversification, not errors
- ✅ This is acceptable since ETFs/Mutual Funds are already diversified by design

**No Changes Needed:**
- Current implementation is correct
- ETFs/Mutual Funds without country/industry are included but not constrained
- This is the desired behavior (they're already diversified, so geographic/industry constraints are less relevant)

### For the Optimizer

#### 1. Product-Type-Aware Concentration Limits

**Current:** All securities have 20% max concentration limit

**Proposed:**
```go
// In ConstraintsManager.calculateWeightBounds()

func (cm *ConstraintsManager) getMaxConcentration(productType string) float64 {
    switch productType {
    case "EQUITY":
        return 0.20 // 20% max for individual stocks
    case "ETF", "MUTUALFUND":
        // Treat ETFs and Mutual Funds identically (both are diversified products)
        // Check if broad-market ETF (heuristic: name contains "All-World", "S&P 500", etc.)
        // For now, use 0.30 (30%) for all diversified products
        // Future: Detect broad-market vs sector/country ETFs
        return 0.30
    case "ETC":
        return 0.12 // 12% max for commodities (different asset class, lower for retirement funds)
        // Could make configurable: etc_max_concentration (default: 0.12)
    default:
        return 0.20 // Default to 20%
    }
}
```

**Implementation:**
- Modify `ConstraintsManager.calculateWeightBounds()` to use product type
- Read product type from `Security` model
- Apply different max concentration based on product type
- **Note**: Country/industry constraints already handle missing data gracefully (groups into "OTHER")
  - ETFs/Mutual Funds without country/industry are not excluded
  - They're just not subject to geographic/industry constraints (which is acceptable)

**Future Enhancement:**
- Detect broad-market ETFs vs sector/country ETFs
- Apply higher limits (40%) for broad-market ETFs
- Apply lower limits (20%) for sector/country ETFs

#### 2. Expected Returns & Target Return Filtering

**Current:** 70% CAGR + 30% score (same for all)

**Decision:** Keep same formula, but add minimum return filtering
- Historical data should naturally reflect differences
- ETFs will have lower CAGR if they're less volatile
- Covariance matrix will capture volatility differences
- **CRITICAL**: Must filter out securities below configured target return

**Target Return Requirement (Configurable):**
- **Setting**: `optimizer_target_return` (default: 0.11 = 11%)
- **Threshold Setting**: `target_return_threshold_pct` (default: 0.80 = 80%, configurable)
  - **Rationale**: 80% provides tighter guardrails for retirement funds (20% shortfall vs 25% at 75%)
  - Users can adjust based on risk tolerance (0.75 for more aggressive, 0.85 for more conservative)
- **Location**: `settings` table, configurable via UI
- **Problem**: ETFs/Mutual Funds with low CAGR (< target) might still be chosen
- **Solution**: Add explicit filtering for securities below minimum threshold with absolute minimum guardrail
- **Implementation**:
  ```go
  // In ReturnsCalculator.calculateSingle()
  // Get target return and threshold from settings (passed as parameter)
  thresholdPct := config.TargetReturnThresholdPct // Default: 0.80 = 80%
  minExpectedReturnThreshold := targetReturn * thresholdPct // 80% of target (default)

  // Absolute minimum: Never allow below 6% or 50% of target (whichever is higher)
  absoluteMinReturn := math.Max(0.06, targetReturn * 0.50)

  // After calculating expected return
  if clamped < absoluteMinReturn {
      // Hard filter: Exclude regardless of quality
      return nil, nil
  }

  if clamped < minExpectedReturnThreshold {
      // Filter out securities below threshold
      return nil, nil
      // Or apply penalty: clamped = clamped * 0.5
  }
  ```
- **Rationale**:
  - 80% of target provides proportional scaling with tighter guardrails for retirement funds (e.g., 11% target → 8.8% minimum, 15% target → 12% minimum)
  - Absolute minimum (6% or 50% of target) prevents extremely low returns regardless of quality
  - Prevents choosing low-return ETFs just for diversification
  - Ensures portfolio meets configured target return goal
  - Dynamic threshold adapts proportionally if user changes target return
- **Location**: `trader/internal/modules/optimization/returns.go::calculateSingle()`
- **Note**: Target return and threshold are passed from `OptimizerService.Optimize()` which reads from settings

#### 3. Risk Model (No Change Needed)

**Current:** Covariance matrix built from historical returns

**Decision:** Keep current approach
- Covariance matrix naturally captures volatility differences
- ETFs will show lower volatility if they're less volatile
- No explicit adjustment needed

#### 4. Country/Industry Constraints (Already Handles Missing Data)

**Current:** Missing country/industry → grouped into "OTHER"

**Decision:** No changes needed
- Current implementation already handles missing data correctly
- ETFs/Mutual Funds without country/industry are grouped into "OTHER"
- If no target exists for "OTHER", they're not constrained by geography/industry
- **This is correct behavior** - they're still included in optimization, just not constrained
- ETFs are already diversified by design, so geographic/industry constraints are less relevant

### For the Planner

#### 1. Target Return Filtering in Planner

**Current:** Planner doesn't explicitly filter by target return

**Proposed:**
- Add minimum CAGR check in opportunity calculators with absolute minimum guardrail
- Filter out opportunities with CAGR below minimum threshold (80% of target, configurable)
- Location: `trader/internal/modules/opportunities/calculators/opportunity_buys.go`
- **Implementation**:
  ```go
  // In OpportunityBuysCalculator.Calculate()
  // Get target return and threshold from config (passed via OpportunityContext or config)
  targetReturn := config.TargetAnnualReturn // From settings
  thresholdPct := config.TargetReturnThresholdPct // Default: 0.80 = 80%
  minCAGRThreshold := targetReturn * thresholdPct // 80% of target (default)

  // Absolute minimum: Never allow below 6% or 50% of target (whichever is higher)
  absoluteMinCAGR := math.Max(0.06, targetReturn * 0.50)

  // Before adding to candidates, check CAGR
  cagr, err := getCAGR(symbol) // Get from calculations table
  if err == nil && cagr != nil {
      // Hard filter: Never allow below absolute minimum
      if *cagr < absoluteMinCAGR {
          continue
      }
      // Filter: Skip securities below minimum CAGR threshold
      if *cagr < minCAGRThreshold {
          continue
      }
  }
  ```
- **Rationale**: Ensures planner doesn't recommend low-return ETFs/Mutual Funds, with tighter guardrails for retirement funds
- **Note**:
  - Target return comes from `target_annual_return` setting (configurable via UI)
  - Threshold percentage comes from `target_return_threshold_pct` setting (configurable, default: 0.80 = 80%)
- **Proportional scaling**: 80% of target adapts to different target values (e.g., 11% → 8.8%, 15% → 12%)

#### 2. Product-Type-Aware Opportunity Scoring

**Current:** Same opportunity scoring for all (value, quality, dividends)

**Proposed:**
```go
// In OpportunityScorer.CalculateWithQualityGate()

func (os *OpportunityScorer) CalculateWithQualityGate(
    dailyPrices []float64,
    peRatio *float64,
    forwardPE *float64,
    marketAvgPE float64,
    fundamentalsScore *float64,
    longTermScore *float64,
    productType string, // NEW parameter
) OpportunityScore {
    // For ETFs & Mutual Funds: Reduce P/E ratio weight (less meaningful)
    // Both are treated identically - both are diversified products
    var peWeight float64
    if productType == "ETF" || productType == "MUTUALFUND" {
        peWeight = 0.25 // 25% weight (down from 50%)
    } else {
        peWeight = 0.50 // 50% weight (normal for stocks)
    }

    below52wWeight := 1.0 - peWeight

    // Calculate scores
    below52wScore := scoreBelow52WeekHigh(currentPrice, high52w)
    peScore := scorePERatio(peRatio, forwardPE, marketAvgPE)

    // Weighted combination
    baseScore := below52wScore*below52wWeight + peScore*peWeight

    // ... rest of calculation
}
```

**Implementation:**
- Add `productType` parameter to `OpportunityScorer.CalculateWithQualityGate()`
- Pass product type from `SecurityScorer` (which has access to `Security` model)
- Adjust P/E ratio weight for ETFs (reduce from 50% to 25%)
- Keep 52W high weight higher for ETFs (75% vs 50%)

#### 3. Product-Type-Aware Scoring Weights

**Current:** Same scoring weights for all securities

**Proposed:**
```go
// In SecurityScorer.ScoreSecurity()

func (ss *SecurityScorer) ScoreSecurity(input ScoreSecurityInput) *domain.CalculatedSecurityScore {
    // Get product type from security
    productType := input.ProductType // NEW field in ScoreSecurityInput

    // Adjust weights based on product type
    weights := ss.getScoreWeights(productType)

    // ... rest of calculation using adjusted weights
}

func (ss *SecurityScorer) getScoreWeights(productType string) map[string]float64 {
    // Treat ETFs and Mutual Funds identically (both are diversified products)
    if productType == "ETF" || productType == "MUTUALFUND" {
        // Diversified product weights (ETFs & Mutual Funds)
        return map[string]float64{
            "long_term":       0.35, // ↑ from 25% (tracking quality matters)
            "fundamentals":    0.10, // ↓ from 20% (less relevant)
            "dividends":       0.18, // Same
            "opportunity":     0.12, // Same
            "short_term":      0.08, // Same
            "technicals":      0.07, // Same
            "opinion":         0.05, // Same
            "diversification": 0.05, // Same
        }
    }

    // Default weights for stocks (EQUITY)
    return ScoreWeights // Current weights
}
```

**Implementation:**
- Add `ProductType` field to `ScoreSecurityInput`
- Create `getScoreWeights()` method that returns weights based on product type
- Modify `ScoreSecurity()` to use adjusted weights
- Pass product type from scoring service (which has access to `Security` model)

#### 4. ETF-Specific Quality Gates

**Current:** Quality gates focus on fundamentals (profit margin, debt-to-equity, etc.)

**Proposed:**
```go
// New: ETFQualityGateChecker

type ETFQualityGateChecker struct {
    // Could check:
    // - Tracking error (lower is better)
    // - Expense ratio (lower is better)
    // - Liquidity (higher is better)
    // - AUM (larger is better)
    // For now, use simplified approach
}

func (c *ETFQualityGateChecker) CheckQuality(security Security) bool {
    // Treat ETFs and Mutual Funds identically (both are diversified products)
    if security.ProductType != "ETF" && security.ProductType != "MUTUALFUND" {
        return true // Not applicable
    }

    // Simplified: Check if diversified product has reasonable fundamentals
    // (Even ETFs/Mutual Funds should have some basic quality metrics)
    // Future: Add tracking error, expense ratio checks

    return true // Default pass for now
}
```

**Implementation:**
- Create `ETFQualityGateChecker` (future enhancement)
- For now, keep current quality gates (they still apply)
- Future: Add tracking error, expense ratio data to `Security` model
- Future: Add ETF-specific quality checks

#### 5. Opportunity Calculator Adjustments

**Current:** `OpportunityBuysCalculator` treats all securities the same

**Proposed:**
- No changes needed to calculators themselves
- Scoring adjustments (above) will naturally affect opportunity identification
- ETFs will score differently, affecting which opportunities are identified

#### 5. Country/Industry Diversification (Already Handles Missing Data)

**Current:** Missing country/industry → neutral diversification scores

**Decision:** No changes needed
- Current implementation already handles missing data correctly
- Location: `trader/internal/modules/scoring/scorers/diversification.go`
- Location: `trader/internal/evaluation/scoring.go`
- Returns neutral (0.5) when country/industry is missing
- **This is correct behavior** - ETFs/Mutual Funds are not excluded, just not prioritized for diversification
- ETFs are already diversified by design, so geographic/industry diversification is less relevant

## Implementation Priorities

### High Priority

1. **Product-Type-Aware Concentration Limits (Optimizer)**
   - Impact: Prevents over-concentration in individual stocks
   - Complexity: Low (read product type, apply different limit)
   - Files: `trader/internal/modules/optimization/constraints.go`

2. **Product-Type-Aware Scoring Weights (Planner)**
   - Impact: Better opportunity identification for ETFs
   - Complexity: Medium (add product type to scoring input, adjust weights)
   - Files: `trader/internal/modules/scoring/scorers/security.go`

### Medium Priority

3. **ETF-Specific Opportunity Scoring (Planner)**
   - Impact: Better value assessment for ETFs (less emphasis on P/E)
   - Complexity: Medium (modify opportunity scorer, pass product type)
   - Files: `trader/internal/modules/scoring/scorers/opportunity.go`

### Low Priority

4. **ETF-Specific Quality Gates (Planner)**
   - Impact: Better quality assessment for ETFs
   - Complexity: High (need tracking error, expense ratio data)
   - Files: New file `trader/internal/modules/scoring/scorers/etf_quality.go`
   - Status: Future enhancement (requires additional data)

5. **Broad-Market ETF Detection (Optimizer)**
   - Impact: Higher concentration limits for broad-market ETFs
   - Complexity: Medium (heuristic-based detection)
   - Files: `trader/internal/modules/optimization/constraints.go`
   - Status: Future enhancement

## Decision: Product-Type Diversification

### Analysis

**Question:** Should we add product-type diversification as a separate constraint/goal (similar to geographic/industry diversification)?

**Decision:** **NO** - Not needed

**Rationale:**
1. **Algorithms will naturally handle it:**
   - Optimizer's covariance matrix captures correlations
   - ETFs naturally show lower volatility
   - Optimization will prefer lower-risk assets when appropriate
   - No need to force a product-type mix

2. **Concentration limits will encourage mix:**
   - Stocks: 15-20% max → prevents over-concentration
   - ETFs: 30-40% max → allows larger positions
   - Natural diversification emerges from merit-based selection

3. **Opportunity identification will drive selection:**
   - Best opportunities rise to the top
   - ETFs and stocks compete on merit
   - System finds optimal mix based on actual opportunities

4. **Product type is a wrapper, not a risk factor:**
   - Geographic/industry diversification addresses actual risk factors
   - Product type is a structural difference, not a risk factor
   - Correlation matters more than product type

**Conclusion:**
The proposed improvements (concentration limits, scoring weights, opportunity scoring) will naturally guide the system toward good diversification without forcing a specific product-type mix. The optimizer and planner will find the optimal allocation based on risk, return, and opportunities.

## Implementation Plan

### Phase 0: Add Product Type UI & Manual Override

**Files to Modify:**
- `trader/frontend/src/components/modals/EditSecurityModal.jsx`
- `trader/internal/modules/universe/security_repository.go` (add product_type to editable fields)

**Changes:**
1. Add `product_type` dropdown to EditSecurityModal
   - Options: EQUITY, ETF, ETC, MUTUALFUND, UNKNOWN
   - Default: Use detected value from heuristics
   - User can override if heuristics are wrong
2. Add `product_type` to editable fields whitelist in backend
3. Update security repository to allow product_type updates

**Rationale:**
- Cannot rely on heuristics alone
- Manual override ensures accuracy
- Heuristics still run on initial detection, but user can correct

### Phase 0.5: Simplify Product Type Detection (Optional but Recommended)

**Files to Modify:**
- `trader/internal/modules/universe/product_type.go`

**Changes:**
1. Simplify `FromYahooQuoteType()` to only distinguish ETCs
2. Remove ETF detection in MUTUALFUND names (treat everything else as ETF)
3. Update comments to reflect simplified approach

**Rationale:**
- Aligns with decision to treat ETFs and Mutual Funds identically
- Simplifies code maintenance
- Reduces edge cases

**Note:** This is optional - current code works, but simplification makes it clearer.

### Phase 1: Optimizer Concentration Limits & Target Return Filtering

**Files to Modify:**
- `trader/internal/modules/optimization/constraints.go`
- `trader/internal/modules/optimization/returns.go` (add minimum return filtering)

**Changes:**
1. Add `getMaxConcentration(productType string) float64` method
2. Modify `calculateWeightBounds()` to read product type from `Security`
3. Apply different max concentration based on product type
4. **NEW**: Add minimum expected return filtering with absolute minimum guardrail
   - Filter out securities with expected return < (target * threshold_pct)
   - Target comes from `optimizer_target_return` setting (configurable, default 11%)
   - Threshold comes from `target_return_threshold_pct` setting (configurable, default 0.80 = 80%)
   - 80% of target provides proportional scaling with tighter guardrails (e.g., 11% → 8.8%, 15% → 12%)
   - **Absolute minimum**: Never allow securities below 6% or 50% of target (whichever is higher), regardless of quality
   - Or apply penalty: reduce expected return by 50% if below threshold
   - Location: `ReturnsCalculator.calculateSingle()`
   - **Critical**: Ensures ETFs/Mutual Funds below target are not chosen, with tighter control for retirement funds
   - **Note**: Threshold is dynamic and proportional to configured target return

**Files to Modify:**
- `trader/internal/modules/optimization/constraints.go`

**Changes:**
1. Add `getMaxConcentration(productType string) float64` method
2. Modify `calculateWeightBounds()` to read product type from `Security`
3. Apply different max concentration based on product type
4. **Verify**: Country/industry constraints already handle missing data (groups into "OTHER")
   - No changes needed - current behavior is correct
   - ETFs/Mutual Funds without country/industry are included but not constrained by geography/industry

**Testing:**
- Verify stocks (EQUITY) get 20% max limit
- Verify ETFs and Mutual Funds get 30% max limit (treated identically)
- Verify ETCs get 12% max limit (lower for retirement funds)
- Test with mixed portfolio
- **Verify missing country/industry handling:**
  - ETFs without country/industry are not excluded
  - They're grouped into "OTHER" for constraints
  - Optimization still includes them (just not constrained by geography/industry)
- **Verify target return filtering:**
  - Securities with expected return < (target * threshold_pct) are filtered out or penalized
  - Target comes from `optimizer_target_return` setting (default 11%)
  - Threshold comes from `target_return_threshold_pct` setting (default 0.80 = 80%, so threshold is 8.8%)
  - **Absolute minimum**: Securities below 6% or 50% of target are always excluded (hard filter)
  - ETFs/Mutual Funds with low CAGR are not chosen
  - Test with portfolio containing low-return ETFs
  - Test with different target return values to verify proportional scaling:
    - 11% target → 8.8% threshold (80% default)
    - 15% target → 12% threshold (80% default)
    - 8% target → 6.4% threshold (80% default), but absolute minimum is 6%
  - Test absolute minimum guardrail: Securities below 6% CAGR are excluded regardless of quality

### Phase 2: Planner Scoring Weights

**Files to Modify:**
- `trader/internal/modules/scoring/scorers/security.go`
- `trader/internal/modules/scoring/domain/models.go` (add ProductType to input)

**Changes:**
1. Add `ProductType` field to `ScoreSecurityInput`
2. Create `getScoreWeights(productType string)` method
3. Modify `ScoreSecurity()` to use adjusted weights for ETFs
4. Pass product type from scoring service

**Testing:**
- Verify ETFs and Mutual Funds get adjusted weights (35% long-term, 10% fundamentals)
- Verify stocks keep current weights
- Test scoring with mixed portfolio
- **Verify missing country/industry handling:**
  - ETFs without country/industry get neutral diversification scores (0.5)
  - They're not excluded from scoring
  - Diversification component is neutral, but other scores still apply

### Phase 3: ETF Opportunity Scoring

**Files to Modify:**
- `trader/internal/modules/scoring/scorers/opportunity.go`
- `trader/internal/modules/scoring/scorers/security.go` (pass product type)

**Changes:**
1. Add `productType` parameter to `CalculateWithQualityGate()`
2. Adjust P/E ratio weight for ETFs (25% vs 50%)
3. Adjust 52W high weight for ETFs (75% vs 50%)
4. Pass product type from `SecurityScorer`

**Testing:**
- Verify ETFs and Mutual Funds have lower P/E ratio weight (25% vs 50%)
- Verify ETFs and Mutual Funds have higher 52W high weight (75% vs 50%)
- Test opportunity scoring with mixed portfolio

## Open Questions for Discussion

1. **Product Type Selection (Manual Override):**
   - ✅ **Decision**: Add product type dropdown in EditSecurityModal
   - ✅ **Rationale**: Cannot rely on heuristics - manual override is more reliable
   - **Implementation**:
     - Add `product_type` dropdown to `EditSecurityModal.jsx`
     - Options: EQUITY, ETF, ETC, MUTUALFUND, UNKNOWN
     - Add `product_type` to editable fields whitelist in backend
     - Heuristics still run on initial detection, but user can override
   - **Future**: Could add "Broad-Market ETF" vs "Sector ETF" distinction if needed

2. **ETC Handling:**
   - ✅ **Decision**: Treat ETCs as commodities (different asset class)
   - **Recommendations**:
     - **Concentration Limit**: 12% max for retirement funds (lower than original 15% proposal) ✅
     - **Expected Returns**: Keep same formula (70% CAGR + 30% score)
       - Historical data should reflect commodity returns
       - No special adjustment needed if data is accurate
     - **Scoring**: Keep same weights as stocks (fundamentals still matter for commodity ETFs)
       - ETCs tracking physical commodities may have different fundamentals
       - But scoring approach can remain the same
     - **Opportunity Scoring**: Keep same as stocks (P/E ratios may not apply, but 52W high still relevant)
   - **Rationale**: ETCs are commodities, so they provide diversification but need careful allocation (12% limit is appropriate for retirement funds to reduce volatility exposure)

3. **Simplified Heuristics:**
   - ✅ Decision: Only distinguish ETCs (commodities) from everything else
   - ✅ ETFs and Mutual Funds treated identically (both are diversified products)
   - ✅ Simplified logic: Only need to detect ETCs, everything else in MUTUALFUND → ETF

4. **Scoring Weight Adjustments & Target Return:**
   - ✅ **Decision**: Proposed ETF weights (35% long-term, 10% fundamentals) seem reasonable
   - ⚠️ **Critical Concern**: Must ensure configured target return is respected while allowing flexibility
   - **Problem**: ETFs/Mutual Funds with low CAGR (< target) might still be chosen
   - **Solution**: **Flexible penalty system** (not hard filtering) that allows high-quality securities to overcome target return shortfall
     - **Philosophy**: A security at 80% of target return but with excellent long-term scores should still be considered (tighter guardrails for retirement funds)
     - **In Optimizer**: Already flexible - uses score-adjusted expected returns (70% CAGR + 30% score-adjusted target)
       - High-quality securities (high long-term + fundamentals scores) can boost expected return even if CAGR is lower
       - Location: `trader/internal/modules/optimization/returns.go::calculateSingle()`
       - Current implementation already allows quality to compensate for lower CAGR
     - **In Planner**: Apply flexible penalty to opportunity score if CAGR < (target * threshold_pct)
       - Target comes from `target_annual_return` setting (configurable)
       - Threshold: `target_return_threshold_pct` setting (configurable, default: 0.80 = 80%)
       - **Rationale**: 80% threshold (11% → 8.8%) provides tighter guardrails for retirement funds while still allowing flexibility
       - Penalty: Reduce opportunity score by penalty factor (0.0-0.3) based on how far below threshold
       - **Absolute minimum guardrail**: Never allow securities below 6% CAGR or 50% of target (whichever is higher), regardless of quality
       - Quality override:
         - If (long_term_score + fundamentals_score) / 2 > 0.80, reduce penalty by 35%
         - If (long_term_score + fundamentals_score) / 2 > 0.75, reduce penalty by 20%
         - **Rationale**: Only exceptional quality (0.80+) gets significant penalty reduction, tighter control for retirement funds
       - This allows high-quality securities to overcome the penalty, but with tighter guardrails
       - Location: `trader/internal/modules/opportunities/calculators/opportunity_buys.go`
       - **Implementation approach**:
         ```go
         // Get threshold from settings (configurable, default 0.80 = 80%)
         thresholdPct := config.TargetReturnThresholdPct // Default: 0.80
         minCAGRThreshold := targetAnnualReturn * thresholdPct

         // Absolute minimum: Never allow below 6% CAGR or 50% of target (whichever is higher)
         absoluteMinCAGR := math.Max(0.06, targetAnnualReturn * 0.50)
         if cagr < absoluteMinCAGR {
             // Hard filter: Exclude regardless of quality
             continue
         }

         // Calculate penalty for low CAGR (if below threshold)
         penalty := 0.0
         if cagr < minCAGRThreshold {
             // Penalty increases as CAGR gets further below threshold
             // Max penalty: 30% reduction
             shortfallRatio := (minCAGRThreshold - cagr) / minCAGRThreshold
             penalty = math.Min(0.3, shortfallRatio * 0.5) // Up to 30% penalty

             // Quality override: Only exceptional quality gets significant reduction
             qualityScore := (longTermScore + fundamentalsScore) / 2.0
             if qualityScore > 0.80 {
                 penalty *= 0.65 // Reduce penalty by 35% for exceptional quality (0.80+)
             } else if qualityScore > 0.75 {
                 penalty *= 0.80 // Reduce penalty by 20% for high quality (0.75-0.80)
             }
             // Quality below 0.75 gets no override (full penalty applies)
         }
         adjustedScore := score * (1.0 - penalty)
         ```
     - **Applies to all product types**: Stocks, ETFs, Mutual Funds, ETCs all use same flexible system
     - **Testing**: Verify that:
       - Low CAGR + low quality = penalized (may not be chosen)
       - Low CAGR + high quality = penalty reduced (can still be chosen)
       - High CAGR = no penalty (normal scoring)
   - **Note**:
     - Target return is configurable via Settings UI, default is 11%
     - Threshold percentage is configurable via `target_return_threshold_pct` setting (default: 0.80 = 80%)
     - Default threshold: 11% → 8.8% (80% of target)
     - **Rationale**: 80% threshold provides tighter guardrails for retirement funds (20% shortfall vs 25% at 75%)
   - **Proportional scaling**: Threshold adapts proportionally to target (e.g., 15% target → 12% threshold at 80%)
   - **Absolute minimum**: Never allow securities below 6% CAGR or 50% of target (whichever is higher), regardless of quality

5. **Quality Gates for ETFs:**
   - ✅ **Decision**: Keep it simple for now - use existing quality gates
   - **Current Approach**:
     - Use existing quality gates (fundamentals, consistency, long-term performance)
     - ETFs still need to meet minimum quality thresholds
     - Lower fundamentals weight (10% vs 20%) accounts for less relevance
   - **Future Enhancement** (if data becomes available):
     - **Tracking Error**: Lower is better (measures how well ETF tracks index)
     - **Expense Ratio**: Lower is better (fees reduce returns)
     - **AUM (Assets Under Management)**: Higher is better (liquidity, stability)
     - **Data Source**: Would need to fetch from ETF provider or financial data API
   - **For Now**:
     - Ensure ETFs meet minimum CAGR threshold (target * threshold_pct, default 80% as per #4 above)
     - Target comes from `target_annual_return` setting (configurable, default 11%)
     - Threshold comes from `target_return_threshold_pct` setting (configurable, default 0.80 = 80%)
     - Default threshold: 11% → 8.8% (80% of target, tighter for retirement funds)
     - Use existing quality gates (they still apply, just weighted less)
     - Focus on long-term performance (35% weight) which captures tracking quality
   - **Recommendation**: Start with existing gates, enhance later if we can get tracking error/expense ratio data

6. **Testing Strategy:**
   - How do we test that the changes improve portfolio outcomes?
   - Should we backtest with historical data?
   - Or monitor in production and adjust?

7. **Missing Country/Industry Data:**
   - ✅ Current behavior: Missing data → "OTHER" group (optimizer) or neutral score (planner)
   - ✅ Securities are NOT excluded, just not constrained by geography/industry
   - ✅ This is acceptable since ETFs are already diversified by design
   - **Question**: Should we enhance this? (e.g., try to infer country from ETF holdings, or use a special "DIVERSIFIED" category?)

## Summary

**Key Improvements:**
1. ✅ **Product Type UI**: Manual override dropdown in EditSecurityModal (cannot rely on heuristics)
2. ✅ Product-type-aware concentration limits (stocks: 20%, ETFs/Mutual Funds: 30%, ETCs: 12%)
3. ✅ **Target Return Penalty (Flexible)**: Apply penalty to securities with CAGR < (target * threshold_pct), but allow high-quality scores to overcome it
   - Target is configurable via `target_annual_return` setting (default: 11%)
   - Threshold is configurable via `target_return_threshold_pct` setting (default: 0.80 = 80%, threshold: 8.8%)
   - 80% of target provides proportional scaling with tighter guardrails (e.g., 11% → 8.8%, 15% → 12%)
   - **Flexible approach**: Securities at 80% of target but with excellent long-term scores can still be chosen
   - **Absolute minimum guardrail**: Never allow securities below 6% CAGR or 50% of target (whichever is higher), regardless of quality
   - Quality override:
     - If (long_term + fundamentals) / 2 > 0.80, penalty is reduced by 35% (exceptional quality)
     - If (long_term + fundamentals) / 2 > 0.75, penalty is reduced by 20% (high quality)
     - Tighter control for retirement funds
   - Applies to all product types (stocks, ETFs, Mutual Funds, ETCs)
4. ✅ Diversified product-specific scoring weights (35% long-term, 10% fundamentals) - applies to ETFs & Mutual Funds
5. ✅ Diversified product-specific opportunity scoring (less P/E emphasis) - applies to ETFs & Mutual Funds
6. ✅ Simplified heuristics (only distinguish ETCs, treat ETFs and Mutual Funds identically)
7. ✅ ETC handling: Treated as commodities (12% limit for retirement funds, same scoring as stocks)
8. ✅ Quality gates: Keep existing gates for now (future: tracking error, expense ratio if data available)
9. ❌ Product-type diversification constraint (not needed - algorithms handle it)

**Expected Outcomes:**
- Better risk management (tighter limits for stocks, higher limits for diversified products)
- Better opportunity identification (ETFs & Mutual Funds scored appropriately)
- Simplified logic (only distinguish commodities, treat diversified products the same)
- Natural diversification (merit-based selection)
- No forced allocations (system finds optimal mix)
- **Graceful handling of missing data**: ETFs/Mutual Funds without country/industry are included but not constrained by geography/industry (acceptable since they're already diversified)

**Implementation Status:**
✅ **COMPLETE** - All phases implemented and tested:
1. ✅ Phase 0: Product Type UI & Manual Override
2. ✅ Phase 1: Optimizer Changes (concentration limits, target return filtering)
3. ✅ Phase 2: Product-Type-Aware Scoring Weights
4. ✅ Phase 3: Product-Type-Aware Opportunity Scoring

**Next Steps:**
1. Deploy to Arduino Uno Q device
2. Monitor optimizer behavior with real portfolio
3. Verify product type detection accuracy
4. Adjust thresholds if needed based on production data
