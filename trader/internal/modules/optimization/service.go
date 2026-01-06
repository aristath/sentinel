package optimization

import (
	"fmt"
	"math"
	"sort"
	"time"

	"github.com/rs/zerolog"
)

// Constants for optimization
const (
	OptimizerWeightCutoff       = 0.001 // Minimum weight to keep (0.1%)
	GradualAdjustmentThreshold  = 0.30  // 30% max deviation triggers gradual adjustment
	GradualAdjustmentStep       = 0.50  // Move 50% toward target per cycle
	DefaultBlend                = 0.5   // 50% MV, 50% HRP
	DefaultMinCashReserve       = 500.0 // EUR
	DefaultTransactionCostFixed = 2.0   // EUR per trade
	DefaultTransactionCostPct   = 0.002 // 0.2%
)

// AdaptiveBlendProvider interface for getting adaptive blend
type AdaptiveBlendProvider interface {
	CalculateAdaptiveBlend(regimeScore float64) float64
}

// RegimeScoreProvider provides access to current regime score
type RegimeScoreProvider interface {
	GetCurrentRegimeScore() (float64, error)
}

// OptimizerService orchestrates the complete portfolio optimization process.
type OptimizerService struct {
	mvOptimizer         *MVOptimizer
	hrpOptimizer        *HRPOptimizer
	constraintsMgr      *ConstraintsManager
	returnsCalc         *ReturnsCalculator
	riskBuilder         *RiskModelBuilder
	adaptiveService     AdaptiveBlendProvider // Optional: adaptive market service
	regimeScoreProvider RegimeScoreProvider   // Optional: regime score provider
	log                 zerolog.Logger
}

// NewOptimizerService creates a new optimizer service.
func NewOptimizerService(
	constraintsMgr *ConstraintsManager,
	returnsCalc *ReturnsCalculator,
	riskBuilder *RiskModelBuilder,
	log zerolog.Logger,
) *OptimizerService {
	return &OptimizerService{
		mvOptimizer:    NewMVOptimizer(),
		hrpOptimizer:   NewHRPOptimizer(),
		constraintsMgr: constraintsMgr,
		returnsCalc:    returnsCalc,
		riskBuilder:    riskBuilder,
		log:            log.With().Str("component", "optimizer_service").Logger(),
	}
}

// SetAdaptiveService sets the adaptive market service for dynamic blend
func (os *OptimizerService) SetAdaptiveService(service AdaptiveBlendProvider) {
	os.adaptiveService = service
}

// SetRegimeScoreProvider sets the regime score provider for getting current regime
func (os *OptimizerService) SetRegimeScoreProvider(provider RegimeScoreProvider) {
	os.regimeScoreProvider = provider
}

// Optimize runs the complete portfolio optimization process.
func (os *OptimizerService) Optimize(state PortfolioState, settings Settings) (*Result, error) {
	timestamp := time.Now()

	os.log.Info().
		Int("num_securities", len(state.Securities)).
		Int("num_positions", len(state.Positions)).
		Float64("portfolio_value", state.PortfolioValue).
		Float64("cash_balance", state.CashBalance).
		Float64("blend", settings.Blend).
		Msg("Starting portfolio optimization")

	// Filter to active securities
	activeSecurities := append([]Security{}, state.Securities...)

	if len(activeSecurities) == 0 {
		return os.errorResult(timestamp, settings.Blend, "No active securities"), nil
	}

	symbols := make([]string, len(activeSecurities))
	for i, sec := range activeSecurities {
		symbols[i] = sec.Symbol
	}

	// 1. Calculate expected returns
	// Get current regime for returns calculation
	regime := "sideways" // Default
	if os.regimeScoreProvider != nil {
		regimeScore, err := os.regimeScoreProvider.GetCurrentRegimeScore()
		if err == nil {
			// Convert continuous score to discrete regime
			if regimeScore <= -0.33 {
				regime = "bear"
			} else if regimeScore >= 0.33 {
				regime = "bull"
			} else {
				regime = "sideways"
			}
		}
	}

	os.log.Info().Str("regime", regime).Msg("Calculating expected returns")
	expectedReturns, err := os.returnsCalc.CalculateExpectedReturns(
		activeSecurities,
		regime,
		state.DividendBonuses,
		settings.TargetReturn,
		settings.TargetReturnThresholdPct,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate expected returns: %w", err)
	}

	if len(expectedReturns) == 0 {
		return os.errorResult(timestamp, settings.Blend, "No expected returns data"), nil
	}

	os.log.Info().
		Int("securities_with_returns", len(expectedReturns)).
		Msg("Calculated expected returns")

	// 2. Adjust expected returns for transaction costs
	expectedReturns = os.adjustReturnsForTransactionCosts(
		expectedReturns,
		state.Positions,
		state.PortfolioValue,
		settings.TransactionCostPct,
	)

	// 3. Build covariance matrix
	os.log.Info().Msg("Building covariance matrix")
	covMatrix, returns, correlations, err := os.riskBuilder.BuildCovarianceMatrix(symbols, DefaultLookbackDays)
	if err != nil {
		return nil, fmt.Errorf("failed to build covariance matrix: %w", err)
	}

	os.log.Info().
		Int("matrix_size", len(covMatrix)).
		Int("high_correlations", len(correlations)).
		Msg("Built covariance matrix")

	// 4. Build constraints
	os.log.Info().Msg("Building constraints")
	constraints, err := os.constraintsMgr.BuildConstraints(
		activeSecurities,
		state.Positions,
		state.CountryTargets,
		state.IndustryTargets,
		state.PortfolioValue,
		state.CurrentPrices,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to build constraints: %w", err)
	}

	// Validate constraints
	if err := os.constraintsMgr.ValidateConstraints(constraints); err != nil {
		os.log.Warn().Err(err).Msg("Constraint validation warning")
	}

	constraintsSummary := os.constraintsMgr.GetConstraintSummary(constraints)
	os.log.Info().
		Int("securities_with_bounds", constraintsSummary.SecuritiesWithBounds).
		Int("country_constraints", constraintsSummary.CountryConstraints).
		Int("industry_constraints", constraintsSummary.IndustryConstraints).
		Msg("Built constraints")

	// 5. Run Mean-Variance optimization
	os.log.Info().Msg("Running Mean-Variance optimization")
	mvWeights, fallbackUsed, err := os.runMeanVariance(
		expectedReturns,
		covMatrix,
		constraints,
		settings.TargetReturn,
	)
	if err != nil {
		os.log.Warn().Err(err).Msg("MV optimization failed, will try HRP")
	}

	// 6. Run HRP optimization
	os.log.Info().Msg("Running HRP optimization")
	hrpWeights, hrpErr := os.runHRP(returns, symbols)
	if hrpErr != nil {
		os.log.Warn().Err(hrpErr).Msg("HRP optimization failed")
	}

	// Clamp HRP weights to bounds
	if hrpWeights != nil {
		hrpWeights = os.clampWeightsToBounds(hrpWeights, constraints)
	}

	// 7. Blend weights
	// Use adaptive blend if available, otherwise use settings.Blend
	blend := settings.Blend
	if os.adaptiveService != nil {
		// Get current regime score if provider is available, otherwise use neutral (0.0)
		regimeScore := 0.0
		if os.regimeScoreProvider != nil {
			currentScore, err := os.regimeScoreProvider.GetCurrentRegimeScore()
			if err == nil {
				regimeScore = currentScore
			}
		}
		blend = os.adaptiveService.CalculateAdaptiveBlend(regimeScore)
		os.log.Info().
			Float64("adaptive_blend", blend).
			Float64("regime_score", regimeScore).
			Msg("Using adaptive blend for optimization")
	}

	var targetWeights map[string]float64
	if mvWeights != nil && hrpWeights != nil {
		targetWeights = os.blendWeights(mvWeights, hrpWeights, blend)
		// Clamp blended weights to bounds
		targetWeights = os.clampWeightsToBounds(targetWeights, constraints)
		os.log.Info().Msg("Using blended MV + HRP weights")
	} else if mvWeights != nil {
		targetWeights = mvWeights
		os.log.Warn().Msg("Using pure MV weights (HRP failed)")
	} else if hrpWeights != nil {
		targetWeights = hrpWeights
		fallbackUsed = stringPtr("hrp")
		os.log.Warn().Msg("Using pure HRP weights (MV failed)")
	} else {
		return os.errorResult(timestamp, settings.Blend, "Both MV and HRP failed"), nil
	}

	// 8. Apply weight cutoff (remove tiny allocations)
	targetWeights = os.applyWeightCutoff(targetWeights, OptimizerWeightCutoff)

	// 9. Normalize weights to investable fraction
	investableFraction := 1.0
	if state.PortfolioValue > 0 {
		investableFraction = 1.0 - (settings.MinCashReserve / state.PortfolioValue)
	}
	targetWeights = os.normalizeWeights(targetWeights, investableFraction)

	// Clamp weights to bounds again (normalization can violate bounds)
	targetWeights = os.clampWeightsToBounds(targetWeights, constraints)

	// 10. Apply gradual adjustment if portfolio is very unbalanced
	targetWeights = os.applyGradualAdjustment(
		targetWeights,
		state.Positions,
		state.PortfolioValue,
		state.CurrentPrices,
	)

	// 11. Calculate weight changes
	weightChanges := os.calculateWeightChanges(targetWeights, state.Positions, state.PortfolioValue)

	// 12. Calculate achieved expected return
	achievedReturn := 0.0
	for symbol, weight := range targetWeights {
		if expRet, ok := expectedReturns[symbol]; ok {
			achievedReturn += expRet * weight
		}
	}

	os.log.Info().
		Int("num_target_weights", len(targetWeights)).
		Float64("achieved_return", achievedReturn).
		Int("weight_changes", len(weightChanges)).
		Msg("Optimization completed successfully")

	return &Result{
		Timestamp:              timestamp,
		TargetReturn:           settings.TargetReturn,
		AchievedExpectedReturn: &achievedReturn,
		BlendUsed:              blend,
		FallbackUsed:           fallbackUsed,
		TargetWeights:          targetWeights,
		WeightChanges:          weightChanges,
		HighCorrelations:       correlations[:min(5, len(correlations))], // Top 5
		ConstraintsSummary:     constraintsSummary,
		Success:                true,
		Error:                  nil,
	}, nil
}

// runMeanVariance runs Mean-Variance optimization using native Go implementation.
func (os *OptimizerService) runMeanVariance(
	expectedReturns map[string]float64,
	covMatrix [][]float64,
	constraints Constraints,
	targetReturn float64,
) (map[string]float64, *string, error) {
	// Try strategies in order: efficient_return → min_volatility → max_sharpe → efficient_risk
	strategies := []string{"efficient_return", "min_volatility", "max_sharpe", "efficient_risk"}
	var lastErr error

	for _, strategy := range strategies {
		var targetRet *float64
		var targetVol *float64

		if strategy == "efficient_return" {
			targetRet = &targetReturn
		} else if strategy == "efficient_risk" {
			// Use a reasonable default volatility target (15%)
			defaultVol := 0.15
			targetVol = &defaultVol
		}

		weights, achievedReturn, err := os.mvOptimizer.Optimize(
			expectedReturns,
			covMatrix,
			constraints.Symbols,
			constraints.WeightBounds,
			constraints.SectorConstraints,
			strategy,
			targetRet,
			targetVol,
		)

		if err == nil {
			os.log.Info().
				Str("strategy_used", strategy).
				Msg("MV optimization succeeded")

			var fallback *string
			if strategy != "efficient_return" {
				fallback = &strategy
			}

			// Return weights and achieved return
			// Note: achievedReturn is ignored in return signature but logged
			_ = achievedReturn

			return weights, fallback, nil
		}

		lastErr = err
		os.log.Debug().
			Str("strategy", strategy).
			Err(err).
			Msg("Strategy failed, trying next")
	}

	return nil, nil, fmt.Errorf("all MV optimization strategies failed: %w", lastErr)
}

// runHRP runs Hierarchical Risk Parity optimization using native Go implementation.
func (os *OptimizerService) runHRP(
	returns map[string][]float64,
	symbols []string,
) (map[string]float64, error) {
	// Filter returns to requested symbols
	filteredReturns := make(map[string][]float64)
	for _, symbol := range symbols {
		if ret, ok := returns[symbol]; ok {
			filteredReturns[symbol] = ret
		}
	}

	if len(filteredReturns) < 2 {
		return nil, fmt.Errorf("HRP needs at least 2 symbols, got %d", len(filteredReturns))
	}

	// Call native HRP optimizer
	weights, err := os.hrpOptimizer.Optimize(filteredReturns, symbols)
	if err != nil {
		return nil, fmt.Errorf("HRP optimization failed: %w", err)
	}

	os.log.Info().
		Int("num_symbols", len(weights)).
		Msg("HRP optimization succeeded")

	return weights, nil
}

// blendWeights blends MV and HRP weights.
func (os *OptimizerService) blendWeights(
	mvWeights map[string]float64,
	hrpWeights map[string]float64,
	blend float64,
) map[string]float64 {
	// blend = 0.0 means pure MV, blend = 1.0 means pure HRP
	// blended[s] = blend * hrp + (1 - blend) * mv

	allSymbols := make(map[string]bool)
	for s := range mvWeights {
		allSymbols[s] = true
	}
	for s := range hrpWeights {
		allSymbols[s] = true
	}

	blended := make(map[string]float64)
	for symbol := range allSymbols {
		mvW := mvWeights[symbol]
		hrpW := hrpWeights[symbol]
		blended[symbol] = blend*hrpW + (1-blend)*mvW
	}

	os.log.Debug().
		Int("num_symbols", len(blended)).
		Float64("blend", blend).
		Msg("Blended MV and HRP weights")

	return blended
}

// clampWeightsToBounds clamps weights to their constraint bounds.
func (os *OptimizerService) clampWeightsToBounds(
	weights map[string]float64,
	constraints Constraints,
) map[string]float64 {
	clamped := make(map[string]float64)

	// Build symbol -> index map
	symbolIndex := make(map[string]int)
	for i, symbol := range constraints.Symbols {
		symbolIndex[symbol] = i
	}

	for symbol, weight := range weights {
		if idx, ok := symbolIndex[symbol]; ok {
			bounds := constraints.WeightBounds[idx]
			lower := bounds[0]
			upper := bounds[1]
			clamped[symbol] = math.Max(lower, math.Min(upper, weight))
		} else {
			clamped[symbol] = weight
		}
	}

	return clamped
}

// normalizeWeights normalizes weights to sum to target.
func (os *OptimizerService) normalizeWeights(
	weights map[string]float64,
	targetSum float64,
) map[string]float64 {
	total := 0.0
	for _, w := range weights {
		total += w
	}

	if total == 0 {
		return weights
	}

	factor := targetSum / total
	normalized := make(map[string]float64)
	for symbol, weight := range weights {
		normalized[symbol] = weight * factor
	}

	return normalized
}

// applyWeightCutoff removes weights below the cutoff threshold.
func (os *OptimizerService) applyWeightCutoff(
	weights map[string]float64,
	cutoff float64,
) map[string]float64 {
	filtered := make(map[string]float64)
	for symbol, weight := range weights {
		if weight >= cutoff {
			filtered[symbol] = weight
		}
	}
	return filtered
}

// adjustReturnsForTransactionCosts adjusts expected returns to account for transaction costs.
func (os *OptimizerService) adjustReturnsForTransactionCosts(
	expectedReturns map[string]float64,
	positions map[string]Position,
	portfolioValue float64,
	transactionCostPct float64,
) map[string]float64 {
	adjusted := make(map[string]float64)

	// Minimum trade value where cost = 1% of value
	minTradeValue := DefaultTransactionCostFixed / (0.01 - transactionCostPct)

	for symbol, expReturn := range expectedReturns {
		// Get current position value
		pos, hasPos := positions[symbol]
		currentValue := 0.0
		if hasPos {
			currentValue = pos.ValueEUR
		}

		// Estimate potential trade value
		var estimatedTradeValue float64
		if currentValue == 0 {
			// New position: assume minimum trade size
			estimatedTradeValue = minTradeValue
		} else {
			// Existing position: assume rebalancing trade (5% of portfolio or 50% of position)
			estimatedTradeValue = math.Min(portfolioValue*0.05, currentValue*0.5)
		}

		// Calculate transaction cost as percentage of trade value
		var costRatio float64
		if estimatedTradeValue > 0 {
			cost := DefaultTransactionCostFixed + estimatedTradeValue*transactionCostPct
			costRatio = cost / estimatedTradeValue
		} else {
			costRatio = 0.01 // Default 1%
		}

		// Reduce expected return by transaction cost (cap at 2%)
		costReduction := math.Min(costRatio, 0.02)
		adjustedReturn := expReturn - costReduction

		adjusted[symbol] = adjustedReturn
	}

	return adjusted
}

// applyGradualAdjustment applies gradual adjustment toward targets when portfolio is unbalanced.
func (os *OptimizerService) applyGradualAdjustment(
	targetWeights map[string]float64,
	positions map[string]Position,
	portfolioValue float64,
	currentPrices map[string]float64,
) map[string]float64 {
	// Calculate current weights
	currentWeights := make(map[string]float64)
	if portfolioValue > 0 {
		for symbol, pos := range positions {
			currentWeights[symbol] = pos.ValueEUR / portfolioValue
		}
	}

	// Calculate maximum deviation
	maxDeviation := 0.0
	allSymbols := make(map[string]bool)
	for s := range targetWeights {
		allSymbols[s] = true
	}
	for s := range currentWeights {
		allSymbols[s] = true
	}

	for symbol := range allSymbols {
		current := currentWeights[symbol]
		target := targetWeights[symbol]
		deviation := math.Abs(target - current)
		if deviation > maxDeviation {
			maxDeviation = deviation
		}
	}

	// If max deviation > 30%, apply gradual adjustment
	if maxDeviation > GradualAdjustmentThreshold {
		os.log.Info().
			Float64("max_deviation", maxDeviation).
			Float64("step", GradualAdjustmentStep).
			Msg("Portfolio very unbalanced, applying gradual adjustment")

		adjusted := make(map[string]float64)
		for symbol := range allSymbols {
			current := currentWeights[symbol]
			target := targetWeights[symbol]

			// Move incrementally toward target
			adjustment := (target - current) * GradualAdjustmentStep
			adjustedWeight := current + adjustment

			// Only include if significant
			if adjustedWeight >= OptimizerWeightCutoff {
				adjusted[symbol] = math.Max(0.0, adjustedWeight)
			}
		}

		// Normalize to maintain sum
		targetSum := 0.0
		for _, w := range targetWeights {
			targetSum += w
		}
		adjusted = os.normalizeWeights(adjusted, targetSum)

		return adjusted
	}

	// Portfolio is reasonably balanced, use full targets
	return targetWeights
}

// calculateWeightChanges calculates weight changes from current to target.
func (os *OptimizerService) calculateWeightChanges(
	targetWeights map[string]float64,
	positions map[string]Position,
	portfolioValue float64,
) []WeightChange {
	changes := make([]WeightChange, 0)

	// Get all symbols
	allSymbols := make(map[string]bool)
	for s := range targetWeights {
		allSymbols[s] = true
	}
	for s := range positions {
		allSymbols[s] = true
	}

	for symbol := range allSymbols {
		// Current weight
		current := 0.0
		if pos, ok := positions[symbol]; ok && portfolioValue > 0 {
			current = pos.ValueEUR / portfolioValue
		}

		// Target weight
		target := targetWeights[symbol]

		// Change
		change := target - current

		if math.Abs(change) > 0.001 { // Ignore tiny changes
			changes = append(changes, WeightChange{
				Symbol:        symbol,
				CurrentWeight: round(current, 4),
				TargetWeight:  round(target, 4),
				Change:        round(change, 4),
				Reason:        nil,
			})
		}
	}

	// Sort by absolute change (largest first)
	sort.Slice(changes, func(i, j int) bool {
		return math.Abs(changes[i].Change) > math.Abs(changes[j].Change)
	})

	return changes
}

// errorResult creates an error result.
func (os *OptimizerService) errorResult(timestamp time.Time, blend float64, error string) *Result {
	os.log.Error().Str("error", error).Msg("Optimization failed")
	errorStr := error
	return &Result{
		Timestamp:              timestamp,
		TargetReturn:           OptimizerTargetReturn,
		AchievedExpectedReturn: nil,
		BlendUsed:              blend,
		FallbackUsed:           nil,
		TargetWeights:          make(map[string]float64),
		WeightChanges:          []WeightChange{},
		HighCorrelations:       []CorrelationPair{},
		ConstraintsSummary:     ConstraintsSummary{},
		Success:                false,
		Error:                  &errorStr,
	}
}

// Helper functions

func round(value float64, decimals int) float64 {
	multiplier := math.Pow(10, float64(decimals))
	return math.Round(value*multiplier) / multiplier
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func stringPtr(s string) *string {
	return &s
}
