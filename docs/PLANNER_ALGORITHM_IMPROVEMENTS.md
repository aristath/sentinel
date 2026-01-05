# Planner Algorithm Improvements

## Status: ✅ **IMPLEMENTED** (Phase 3 Complete)

All algorithm improvements have been implemented and integrated. See implementation details below.

## Executive Summary

Based on financial advisor review and requirements discussion, this document outlines concrete improvements to the planner algorithms for a 15-20 year retirement fund with emphasis on quality, dividends, and risk management.

**Implementation Status:**
- ✅ 1. Evaluation System Enhancement (Multi-objective evaluation)
- ✅ 2. Security Scoring Weights Adjustment (Quality-focused)
- ✅ 3. Opportunity Quality Gates (Value trap prevention)
- ✅ 4. CAGR Scoring Enhancement (Bubble detection)
- ✅ 5. Dividend Scoring Enhancement (Total return)
- ✅ 6. Optimizer-Planner Integration (End-to-end alignment)

## Key Requirements

- **Target Return**: 11% CAGR minimum (higher is better if quality)
- **Dividends**: Critical - total return = growth + dividend (e.g., 5% growth + 10% dividend = 15% total)
- **Quality vs Opportunity**: 85% quality + 15% opportunistic (configurable)
- **Diversification**: Never penalize - it's important for risk management
- **Risk Management**: Reduce risk in high-volatility regimes (regime detection exists)
- **Transaction Costs**: €2 fixed + 0.2% variable (from Tradernet)

---

## 1. Evaluation System Enhancement

### Current Problem

Evaluation only uses diversification score + transaction costs. Missing expected return, risk-adjusted return, and quality metrics.

### Proposed Solution

**Multi-objective evaluation that preserves diversification importance:**

```go
// Enhanced evaluation function
func EvaluateEndStateEnhanced(
    endContext models.PortfolioContext,
    sequence []models.ActionCandidate,
    transactionCostFixed float64,
    transactionCostPercent float64,
    costPenaltyFactor float64,
) float64 {
    // 1. Diversification Score (30%) - KEEP IMPORTANT
    divScore := CalculateDiversificationScore(endContext)
    
    // 2. Expected Return Score (30%)
    expectedReturnScore := calculateExpectedReturnScore(endContext)
    
    // 3. Risk-Adjusted Return Score (20%)
    riskAdjustedScore := calculateRiskAdjustedScore(endContext)
    
    // 4. Quality Score (20%)
    qualityScore := calculateQualityScore(endContext)
    
    // Combined score (all components important)
    endScore := divScore*0.30 + 
                expectedReturnScore*0.30 + 
                riskAdjustedScore*0.20 + 
                qualityScore*0.20
    
    // Transaction cost penalty (subtractive)
    totalCost := CalculateTransactionCost(sequence, transactionCostFixed, transactionCostPercent)
    if costPenaltyFactor > 0.0 && endContext.TotalValue > 0 {
        costPenalty := (totalCost / endContext.TotalValue) * costPenaltyFactor
        endScore = math.Max(0.0, endScore-costPenalty)
    }
    
    return math.Min(1.0, endScore)
}
```

**Key Points:**
- Diversification remains at 30% (important, not penalized)
- Expected return added at 30% (accounts for growth + dividends)
- Risk-adjusted return at 20% (Sharpe/Sortino at portfolio level)
- Quality at 20% (weighted average of security quality scores)

### Implementation

**New Functions Needed:**

```go
// calculateExpectedReturnScore calculates expected return for portfolio
// Accounts for BOTH growth (CAGR) AND dividends
func calculateExpectedReturnScore(ctx models.PortfolioContext) float64 {
    totalValue := ctx.TotalValue
    if totalValue <= 0 {
        return 0.5
    }
    
    weightedReturn := 0.0
    weightedDividend := 0.0
    
    for symbol, value := range ctx.Positions {
        weight := value / totalValue
        
        // Get expected CAGR (from security scores or optimizer)
        if expectedCAGR, ok := ctx.ExpectedReturns[symbol]; ok {
            weightedReturn += expectedCAGR * weight
        }
        
        // Get dividend yield
        if dividendYield, ok := ctx.SecurityDividends[symbol]; ok {
            weightedDividend += dividendYield * weight
        }
    }
    
    // Total return = growth + dividend
    totalReturn := weightedReturn + weightedDividend
    
    // Score based on target (11% minimum)
    // 11% = 0.8, 15% = 1.0, 20%+ = 1.0 (capped)
    if totalReturn >= 0.20 {
        return 1.0
    } else if totalReturn >= 0.15 {
        return 0.8 + (totalReturn-0.15)/0.05*0.2
    } else if totalReturn >= 0.11 {
        return 0.6 + (totalReturn-0.11)/0.04*0.2
    } else if totalReturn >= 0.05 {
        return 0.3 + (totalReturn-0.05)/0.06*0.3
    } else {
        return totalReturn / 0.05 * 0.3
    }
}

// calculateRiskAdjustedScore calculates portfolio-level Sharpe/Sortino
func calculateRiskAdjustedScore(ctx models.PortfolioContext) float64 {
    // Calculate portfolio Sharpe ratio
    // Use portfolio returns and volatility
    portfolioSharpe := calculatePortfolioSharpe(ctx)
    
    // Score based on Sharpe
    if portfolioSharpe >= 2.0 {
        return 1.0
    } else if portfolioSharpe >= 1.5 {
        return 0.8 + (portfolioSharpe-1.5)/0.5*0.2
    } else if portfolioSharpe >= 1.0 {
        return 0.6 + (portfolioSharpe-1.0)/0.5*0.2
    } else if portfolioSharpe >= 0.5 {
        return 0.4 + (portfolioSharpe-0.5)/0.5*0.2
    } else {
        return portfolioSharpe / 0.5 * 0.4
    }
}
```

---

## 2. Security Scoring Weights Adjustment ✅ **IMPLEMENTED**

### Implementation Status

**✅ COMPLETE** - Quality-focused weights implemented:
- Updated `ScoreWeights` in `security.go` to favor quality and dividends
- Long-term: 25% (↑ from 20%), Fundamentals: 20% (↑ from 15%), Dividends: 18% (↑ from 12%)
- Opportunity: 12% (↓ from 15%), Technicals: 7% (↓ from 10%), Opinion: 5% (↓ from 10%)
- Quality focus: Long-term + Fundamentals = 45% (vs 35% before)
- All tests passing

### Current Weights

```
Long-term:      20%
Fundamentals:   15%
Opportunity:    15%
Dividends:      12%
Short-term:     10%
Technicals:     10%
Opinion:        10%
Diversification: 8%
```

### Proposed Weights (Quality-Focused with Dividends)

```
Long-term:      25%  (↑ from 20%) - CAGR, Sortino, Sharpe
Fundamentals:   20%  (↑ from 15%) - Financial strength, Consistency
Dividends:      18%  (↑ from 12%) - Yield, Consistency, Growth
Opportunity:    12%  (↓ from 15%) - 52W high, P/E (filter, not primary)
Short-term:      8%  (↓ from 10%) - Momentum, Drawdown
Technicals:      7%  (↓ from 10%) - RSI, Bollinger, EMA
Opinion:         5%  (↓ from 10%) - Analyst recs, Targets
Diversification: 5%  (↓ from 8%) - Portfolio-level (moved to evaluation)
```

**Total: 100%**

**Rationale:**
- **Quality focus**: Long-term + Fundamentals = 45% (vs 35% before)
- **Dividend emphasis**: 18% (vs 12%) - accounts for your 5% growth + 10% dividend = 15% total example
- **Opportunity reduced**: 12% (vs 15%) - use as filter, not primary driver
- **Technicals reduced**: 7% (vs 10%) - less important for long-term
- **Opinion reduced**: 5% (vs 10%) - external forecasts less reliable

### Alternative: Two-Tier Approach (85/15 Quality/Opportunity)

If you want the 85/15 split to be more explicit:

```go
// Quality Score (85% of total)
qualityScore := (longTermScore * 0.30 + fundamentalsScore * 0.30 + dividendScore * 0.25) * 0.85

// Opportunity Score (15% of total)
opportunityScore := (opportunityScore * 0.40 + technicalScore * 0.35 + shortTermScore * 0.25) * 0.15

// Total
totalScore := qualityScore + opportunityScore + (opinionScore * 0.05) + (diversificationScore * 0.05)
```

**Recommendation**: Use the adjusted weights above (simpler, clearer).

---

## 3. Dividend Scoring Enhancement

### Current Issue

Dividend yield is normalized to 0-1 by capping at 10%, but doesn't account for total return (growth + dividend).

### Proposed Solution

**Enhanced dividend scoring that accounts for total return:**

```go
// Enhanced dividend scorer
func (ds *DividendScorer) CalculateEnhanced(
    dividendYield *float64,
    payoutRatio *float64,
    fiveYearAvgDivYield *float64,
    expectedCAGR float64, // Add CAGR to dividend calculation
) DividendScore {
    // Current dividend score (yield + consistency)
    baseScore := ds.Calculate(dividendYield, payoutRatio, fiveYearAvgDivYield)
    
    // Calculate total return = growth + dividend
    totalReturn := expectedCAGR
    if dividendYield != nil {
        totalReturn += *dividendYield
    }
    
    // Boost score for high total return
    // Example: 5% growth + 10% dividend = 15% total (excellent)
    totalReturnBoost := 0.0
    if totalReturn >= 0.15 {
        totalReturnBoost = 0.2 // 20% boost
    } else if totalReturn >= 0.12 {
        totalReturnBoost = 0.15
    } else if totalReturn >= 0.10 {
        totalReturnBoost = 0.10
    }
    
    // Enhanced score
    enhancedScore := baseScore.Score + totalReturnBoost
    enhancedScore = math.Min(1.0, enhancedScore)
    
    return DividendScore{
        Score:      round3(enhancedScore),
        Components: baseScore.Components, // Keep existing components
    }
}
```

**Key Points:**
- Rewards securities with high total return (growth + dividend)
- Your example: 5% growth + 10% dividend = 15% total gets boost
- Maintains existing dividend consistency scoring

---

## 4. CAGR Scoring: Bubble Detection Instead of Bell Curve

### Current Problem

Bell curve penalizes high CAGR (15% gets lower score than 11%), but you want to reward quality high CAGR while avoiding bubbles.

### Proposed Solution

**Risk-adjusted CAGR scoring with bubble detection:**

```go
// Enhanced CAGR scoring with bubble detection
func scoreCAGREnhanced(
    cagr float64,
    target float64,
    sharpeRatio *float64,
    sortinoRatio *float64,
    volatility *float64,
    fundamentalsScore float64,
) float64 {
    if cagr <= 0 {
        return scoring.BellCurveFloor
    }
    
    // Bubble detection: High CAGR with poor risk metrics = bubble
    isBubble := false
    if cagr > target*1.5 { // 16.5%+ for 11% target
        // Check risk metrics
        if sharpeRatio != nil && *sharpeRatio < 0.5 {
            isBubble = true // High return, low Sharpe = risky
        }
        if sortinoRatio != nil && *sortinoRatio < 0.5 {
            isBubble = true // High return, poor downside protection
        }
        if volatility != nil && *volatility > 0.40 {
            isBubble = true // High return, extreme volatility
        }
        if fundamentalsScore < 0.6 {
            isBubble = true // High return, weak fundamentals
        }
    }
    
    if isBubble {
        // Penalize bubbles: cap score at 0.6 even if CAGR is high
        return 0.6
    }
    
    // Quality high CAGR: reward it
    if cagr >= target {
        // Monotonic scoring above target (reward higher CAGR)
        excess := cagr - target
        // 11% = 0.8, 15% = 0.95, 20%+ = 1.0
        if excess >= 0.09 { // 20%+
            return 1.0
        } else if excess >= 0.04 { // 15%+
            return 0.8 + (excess-0.04)/0.05*0.15
        } else { // 11-15%
            return 0.8 + excess/target*0.1
        }
    }
    
    // Below target: use bell curve (penalize being too low)
    sigma := scoring.BellCurveSigmaLeft
    rawScore := math.Exp(-math.Pow(cagr-target, 2) / (2 * math.Pow(sigma, 2)))
    return scoring.BellCurveFloor + rawScore*(1-scoring.BellCurveFloor)
}
```

**Key Points:**
- **Above target**: Monotonic (higher CAGR = higher score) IF quality
- **Bubble detection**: High CAGR + poor risk metrics = cap at 0.6
- **Below target**: Bell curve (penalize being too low)
- **Quality gates**: Fundamentals, Sharpe, Sortino, volatility

---

## 5. Opportunity Scoring: Quality Gates

### Current Problem

Opportunity scoring can identify value traps (cheap but declining quality).

### Proposed Solution

**Add quality gates to opportunity tags:**

```go
// Enhanced opportunity scoring with quality gates
func (os *OpportunityScorer) CalculateWithQualityGate(
    dailyPrices []float64,
    peRatio *float64,
    forwardPE *float64,
    marketAvgPE float64,
    fundamentalsScore float64, // Add quality gate
    longTermScore float64,     // Add quality gate
) OpportunityScore {
    // Calculate base opportunity score
    baseScore := os.Calculate(dailyPrices, peRatio, forwardPE, marketAvgPE)
    
    // Quality gate: require minimum quality for value opportunities
    minQualityThreshold := 0.6 // Configurable
    minLongTermThreshold := 0.5
    
    // If opportunity score is high but quality is low, reduce score
    if baseScore.Score > 0.7 {
        if fundamentalsScore < minQualityThreshold || longTermScore < minLongTermThreshold {
            // Value trap detected - reduce opportunity score
            baseScore.Score = baseScore.Score * 0.7 // 30% penalty
            baseScore.Components["quality_penalty"] = 0.3
        }
    }
    
    return baseScore
}
```

**Value Trap Detection:**

```go
// Detect value traps: cheap but declining
func isValueTrap(
    peRatio *float64,
    marketAvgPE float64,
    fundamentalsScore float64,
    longTermScore float64,
    recentMomentum float64, // Negative momentum
) bool {
    // Cheap (low P/E)
    isCheap := peRatio != nil && *peRatio < marketAvgPE*0.8
    
    // But declining quality
    isDeclining := fundamentalsScore < 0.6 || longTermScore < 0.5
    
    // And negative momentum
    hasNegativeMomentum := recentMomentum < -0.05
    
    return isCheap && (isDeclining || hasNegativeMomentum)
}
```

**Recommendation**: Use quality threshold of 0.6 for fundamentals and 0.5 for long-term.

---

## 6. Optimizer-Planner Integration ✅ **IMPLEMENTED**

### Current Problem

Optimizer creates strategy, planner implements it, but no feedback loop or alignment.

### Implementation Status

**✅ COMPLETE** - End-to-end integration implemented:
- Added `OptimizerTargetWeights` to `PortfolioContext` in both evaluation models packages
- Implemented `calculateOptimizerAlignment()` function
- Updated `EvaluateEndStateEnhanced()` to include optimizer alignment (25% weight)
- Updated planner to pass `OpportunityContext` (with `TargetWeights`) to evaluation service
- Updated simulation code to preserve optimizer targets during sequence execution
- All tests passing

### Proposed Solution

**Three-layer architecture:**

1. **Optimizer** (Strategy Layer): Creates target allocations based on expected returns, risk constraints
2. **Planner** (Implementation Layer): Finds sequences to move toward targets
3. **Evaluation** (Alignment Layer): Scores sequences based on how well they achieve optimizer goals

**Enhanced Evaluation with Optimizer Alignment:**

```go
// EvaluateEndStateWithOptimizerAlignment
func EvaluateEndStateWithOptimizerAlignment(
    endContext models.PortfolioContext,
    optimizerTargets map[string]float64, // From optimizer
    sequence []models.ActionCandidate,
    transactionCostFixed float64,
    transactionCostPercent float64,
) float64 {
    // 1. Diversification (30%)
    divScore := CalculateDiversificationScore(endContext)
    
    // 2. Optimizer Alignment (25%) - NEW
    alignmentScore := calculateOptimizerAlignment(endContext, optimizerTargets)
    
    // 3. Expected Return (25%)
    expectedReturnScore := calculateExpectedReturnScore(endContext)
    
    // 4. Risk-Adjusted Return (10%)
    riskAdjustedScore := calculateRiskAdjustedScore(endContext)
    
    // 5. Quality (10%)
    qualityScore := calculateQualityScore(endContext)
    
    // Combined
    endScore := divScore*0.30 + 
                alignmentScore*0.25 + 
                expectedReturnScore*0.25 + 
                riskAdjustedScore*0.10 + 
                qualityScore*0.10
    
    // Transaction cost penalty
    totalCost := CalculateTransactionCost(sequence, transactionCostFixed, transactionCostPercent)
    if endContext.TotalValue > 0 {
        costPenalty := (totalCost / endContext.TotalValue) * 0.5 // 0.5 penalty factor
        endScore = math.Max(0.0, endScore-costPenalty)
    }
    
    return math.Min(1.0, endScore)
}

// calculateOptimizerAlignment scores how close portfolio is to optimizer targets
func calculateOptimizerAlignment(
    ctx models.PortfolioContext,
    targets map[string]float64,
) float64 {
    totalValue := ctx.TotalValue
    if totalValue <= 0 || len(targets) == 0 {
        return 0.5
    }
    
    var deviations []float64
    for symbol, targetWeight := range targets {
        currentValue, hasPosition := ctx.Positions[symbol]
        currentWeight := 0.0
        if hasPosition {
            currentWeight = currentValue / totalValue
        }
        
        deviation := math.Abs(currentWeight - targetWeight)
        deviations = append(deviations, deviation)
    }
    
    if len(deviations) == 0 {
        return 0.5
    }
    
    // Average deviation
    avgDeviation := sum(deviations) / float64(len(deviations))
    
    // Score: 0 deviation = 1.0, 10% avg deviation = 0.5, 20%+ = 0.0
    alignmentScore := math.Max(0.0, 1.0-avgDeviation/0.20)
    
    return alignmentScore
}
```

**Key Points:**
- Optimizer creates strategy (target allocations)
- Planner finds implementation (sequences)
- Evaluation scores sequences based on optimizer alignment (25% weight)
- Allows some deviation (not strict) but rewards alignment

---

## 7. Transaction Cost Enhancements

### Current

Fixed cost (€2) + percentage (0.2%) from Tradernet.

### Proposed Additions

**Spread Cost:**
- **What**: Difference between bid (sell) and ask (buy) prices
- **Example**: Stock trades at €100, but bid=€99.90, ask=€100.10
- **Cost**: (ask - bid) / 2 = €0.10 per share = 0.1% for €100 stock
- **Implementation**: Add 0.1% spread cost for liquid stocks, 0.2% for less liquid

**Slippage:**
- **What**: Price moves between order placement and execution
- **Example**: You want to buy at €100, but execution happens at €100.15
- **Cost**: 0.15% slippage
- **Implementation**: Add 0.1-0.2% slippage estimate based on trade size and volatility

**Market Impact:**
- **What**: Large trades move the market price
- **Example**: Buying 10,000 shares pushes price up by €0.50
- **Cost**: Depends on trade size relative to average daily volume
- **Implementation**: Add market impact cost for trades > 1% of daily volume

**Enhanced Transaction Cost Calculation:**

```go
func CalculateTransactionCostEnhanced(
    action models.ActionCandidate,
    transactionCostFixed float64,
    transactionCostPercent float64,
    spreadCostPercent float64,    // NEW: 0.001 (0.1%)
    slippagePercent float64,      // NEW: 0.0015 (0.15%)
    marketImpactPercent float64,  // NEW: calculated based on trade size
) float64 {
    // Base costs
    fixedCost := transactionCostFixed
    variableCost := math.Abs(action.ValueEUR) * transactionCostPercent
    
    // Spread cost (bid-ask spread)
    spreadCost := math.Abs(action.ValueEUR) * spreadCostPercent
    
    // Slippage (price movement)
    slippageCost := math.Abs(action.ValueEUR) * slippagePercent
    
    // Market impact (for large trades)
    impactCost := math.Abs(action.ValueEUR) * marketImpactPercent
    
    totalCost := fixedCost + variableCost + spreadCost + slippageCost + impactCost
    
    return totalCost
}
```

**Recommendation**: Start with spread (0.1%) and slippage (0.15%), add market impact later if needed.

---

## 8. Risk Management: Regime-Based Adjustments

### Current

Regime detection exists but may not be used in planner decisions.

### Proposed Solution

**Use regime detection to adjust risk and strategy:**

```go
// Adjust evaluation based on market regime
func EvaluateEndStateWithRegime(
    endContext models.PortfolioContext,
    sequence []models.ActionCandidate,
    regime portfolio.MarketRegime, // Add regime parameter
    transactionCostFixed float64,
    transactionCostPercent float64,
) float64 {
    // Base evaluation
    baseScore := EvaluateEndStateEnhanced(endContext, sequence, transactionCostFixed, transactionCostPercent, 0.5)
    
    // Regime adjustments
    switch regime {
    case portfolio.MarketRegimeBear:
        // Bear market: Reduce risk, favor quality, increase cash
        // Penalize high-volatility positions
        volatilityPenalty := calculateVolatilityPenalty(endContext)
        baseScore = baseScore * (1.0 - volatilityPenalty*0.2) // Up to 20% penalty
        
        // Boost quality score
        qualityBoost := calculateQualityBoost(endContext)
        baseScore = baseScore + qualityBoost*0.1 // Up to 10% boost
        
    case portfolio.MarketRegimeBull:
        // Bull market: Allow more risk, favor growth
        // Slight boost for growth positions
        growthBoost := calculateGrowthBoost(endContext)
        baseScore = baseScore + growthBoost*0.05 // Up to 5% boost
        
    case portfolio.MarketRegimeSideways:
        // Sideways: Neutral, favor value opportunities
        valueBoost := calculateValueBoost(endContext)
        baseScore = baseScore + valueBoost*0.05 // Up to 5% boost
    }
    
    return math.Min(1.0, baseScore)
}
```

**Key Points:**
- **Bear market**: Reduce risk, favor quality, penalize volatility
- **Bull market**: Allow more growth, slight boost for growth positions
- **Sideways**: Neutral, favor value opportunities
- Regime detection already exists, just needs integration

---

## 9. Implementation Priority

### Phase 1: High Impact, Quick Wins (Week 1)

1. **CAGR Scoring Enhancement** (bubble detection)
   - Replace bell curve with risk-adjusted monotonic scoring
   - Add bubble detection logic
   - **Impact**: Prevents bubble chasing, rewards quality high CAGR

2. **Dividend Scoring Enhancement** (total return)
   - Add total return calculation (growth + dividend)
   - Boost score for high total return
   - **Impact**: Rewards your 5% growth + 10% dividend = 15% total example

3. **Opportunity Quality Gates**
   - Add quality thresholds to opportunity scoring
   - Add value trap detection
   - **Impact**: Prevents buying value traps

### Phase 2: Core Improvements (Week 2-3)

4. **Evaluation System Enhancement**
   - Add expected return score (30%)
   - Add risk-adjusted return score (20%)
   - Keep diversification at 30% (important)
   - **Impact**: Comprehensive evaluation, no longer just diversification

5. **Security Scoring Weights Adjustment**
   - Increase long-term to 25%
   - Increase fundamentals to 20%
   - Increase dividends to 18%
   - Reduce opportunity to 12%
   - **Impact**: Quality-focused scoring aligned with retirement fund

### Phase 3: Integration (Week 4)

6. **Optimizer-Planner Integration**
   - Add optimizer alignment score (25%)
   - Calculate alignment with optimizer targets
   - **Impact**: Planner implements optimizer strategy better

7. **Regime-Based Risk Adjustments**
   - Integrate regime detection into evaluation
   - Adjust risk based on market conditions
   - **Impact**: Reduces risk in bear markets, allows growth in bull markets

### Phase 4: Polish (Week 5)

8. **Transaction Cost Enhancements**
   - Add spread cost (0.1%)
   - Add slippage (0.15%)
   - **Impact**: More realistic cost estimation

---

## 10. Configuration

### New Configuration Options

```go
type PlannerConfiguration struct {
    // ... existing fields ...
    
    // Quality vs Opportunity ratio (default 0.85 = 85% quality)
    QualityOpportunityRatio float64 `json:"quality_opportunity_ratio"` // 0.0-1.0
    
    // Minimum quality thresholds
    MinFundamentalsForOpportunity float64 `json:"min_fundamentals_for_opportunity"` // Default 0.6
    MinLongTermForOpportunity     float64 `json:"min_long_term_for_opportunity"`     // Default 0.5
    
    // CAGR bubble detection thresholds
    BubbleDetectionEnabled        bool    `json:"bubble_detection_enabled"`         // Default true
    MinSharpeForHighCAGR          float64 `json:"min_sharpe_for_high_cagr"`         // Default 0.5
    MinSortinoForHighCAGR         float64 `json:"min_sortino_for_high_cagr"`        // Default 0.5
    MaxVolatilityForHighCAGR      float64 `json:"max_volatility_for_high_cagr"`     // Default 0.40
    
    // Transaction cost enhancements
    SpreadCostPercent    float64 `json:"spread_cost_percent"`    // Default 0.001 (0.1%)
    SlippagePercent      float64 `json:"slippage_percent"`        // Default 0.0015 (0.15%)
    MarketImpactEnabled  bool    `json:"market_impact_enabled"`   // Default false
}
```

---

## Summary

These improvements will:

1. **Preserve diversification importance** (30% weight, never penalized)
2. **Reward total return** (growth + dividend, not just growth)
3. **Focus on quality** (85% quality + 15% opportunity, configurable)
4. **Prevent bubbles** (risk-adjusted CAGR scoring with bubble detection)
5. **Avoid value traps** (quality gates on opportunity scoring)
6. **Align with optimizer** (planner implements optimizer strategy)
7. **Adapt to market regime** (reduce risk in bear markets)
8. **Realistic costs** (spread, slippage, market impact)

**Expected Outcome**: Better risk-adjusted returns, fewer bad trades, better alignment with optimizer strategy, and adaptation to market conditions.

