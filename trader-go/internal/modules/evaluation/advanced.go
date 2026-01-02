package evaluation

import (
	"fmt"
	"math"
	"math/rand"
	"sort"

	"gonum.org/v1/gonum/floats"
	"gonum.org/v1/gonum/stat"
)

// EvaluateMonteCarlo performs Monte Carlo simulation on a sequence using random price paths
// Returns statistical distribution of scores across multiple stochastic paths
func EvaluateMonteCarlo(req MonteCarloRequest) MonteCarloResult {
	if req.Paths <= 0 {
		req.Paths = 100 // Default to 100 paths
	}

	// Extract symbols from sequence
	symbolsSet := make(map[string]bool)
	for _, action := range req.Sequence {
		symbolsSet[action.Symbol] = true
	}
	symbols := make([]string, 0, len(symbolsSet))
	for symbol := range symbolsSet {
		symbols = append(symbols, symbol)
	}

	// Channel for collecting path results
	type pathResult struct {
		pathIdx int
		score   float64
	}
	results := make(chan pathResult, req.Paths)

	// Launch goroutines for parallel path evaluation
	for i := 0; i < req.Paths; i++ {
		go func(pathIdx int) {
			// Generate random price adjustments for this path
			priceAdj := generateRandomPrices(symbols, req.SymbolVolatilities)

			// Simulate sequence with adjusted prices
			endContext, _ := SimulateSequence(
				req.Sequence,
				req.EvaluationContext.PortfolioContext,
				req.EvaluationContext.AvailableCashEUR,
				req.EvaluationContext.Securities,
				priceAdj,
			)

			// Evaluate end state
			endScore := EvaluateEndState(
				endContext,
				req.Sequence,
				req.EvaluationContext.TransactionCostFixed,
				req.EvaluationContext.TransactionCostPercent,
				0.0, // No cost penalty for Monte Carlo
			)

			results <- pathResult{pathIdx: pathIdx, score: endScore}
		}(i)
	}

	// Collect all scores
	pathScores := make([]float64, req.Paths)
	for i := 0; i < req.Paths; i++ {
		res := <-results
		pathScores[res.pathIdx] = res.score
	}
	close(results)

	// Sort for percentile calculations
	sort.Float64s(pathScores)

	// Calculate statistics
	avgScore := stat.Mean(pathScores, nil)
	worstScore := floats.Min(pathScores)
	bestScore := floats.Max(pathScores)

	// Calculate percentiles
	p10Score := stat.Quantile(0.10, stat.Empirical, pathScores, nil)
	p90Score := stat.Quantile(0.90, stat.Empirical, pathScores, nil)

	// Conservative final score (matches Python implementation)
	finalScore := worstScore*0.4 + p10Score*0.3 + avgScore*0.3

	return MonteCarloResult{
		PathsEvaluated: req.Paths,
		AvgScore:       avgScore,
		WorstScore:     worstScore,
		BestScore:      bestScore,
		P10Score:       p10Score,
		P90Score:       p90Score,
		FinalScore:     finalScore,
	}
}

// generateRandomPrices generates random price multipliers using geometric Brownian motion
func generateRandomPrices(symbols []string, volatilities map[string]float64) map[string]float64 {
	adjustments := make(map[string]float64)

	for _, symbol := range symbols {
		// Get volatility for this symbol (default 20% if not provided)
		vol := 0.2
		if v, ok := volatilities[symbol]; ok && v > 0 {
			vol = v
		}

		// Convert annual volatility to daily: annual / sqrt(252 trading days)
		dailyVol := vol / math.Sqrt(252)

		// Generate random normal (mean=0, stddev=1)
		// Using math/rand is acceptable for Monte Carlo simulation (not crypto)
		//nolint:gosec // G404: Monte Carlo simulation doesn't require crypto-grade randomness
		randomNormal := rand.NormFloat64()

		// Price multiplier: exp(daily_vol * random_normal)
		// This follows geometric Brownian motion: S(t+dt) = S(t) * exp(sigma * sqrt(dt) * Z)
		multiplier := math.Exp(dailyVol * randomNormal)

		// Clamp to reasonable range [0.5x, 2.0x] to avoid extreme outliers
		adjustments[symbol] = math.Max(0.5, math.Min(2.0, multiplier))
	}

	return adjustments
}

// EvaluateStochastic evaluates a sequence under multiple fixed price scenarios
// Returns weighted average score across scenarios
func EvaluateStochastic(req StochasticRequest) StochasticResult {
	// Default shifts if not provided
	if len(req.Shifts) == 0 {
		req.Shifts = []float64{-0.10, -0.05, 0.0, 0.05, 0.10}
	}

	// Default weights if not provided (base scenario 40%, others 15% each)
	if len(req.Weights) == 0 {
		req.Weights = map[string]float64{
			"0":     0.40,
			"-0.1":  0.15,
			"-0.05": 0.15,
			"0.05":  0.15,
			"0.1":   0.15,
		}
	}

	// Extract symbols from sequence
	symbolsSet := make(map[string]bool)
	for _, action := range req.Sequence {
		symbolsSet[action.Symbol] = true
	}
	symbols := make([]string, 0, len(symbolsSet))
	for symbol := range symbolsSet {
		symbols = append(symbols, symbol)
	}

	// Channel for collecting scenario results
	type scenarioResult struct {
		shift float64
		score float64
	}
	results := make(chan scenarioResult, len(req.Shifts))

	// Launch goroutines for parallel scenario evaluation
	for _, shift := range req.Shifts {
		go func(s float64) {
			// Create fixed price adjustments for this scenario
			// e.g., shift=-0.10 means all prices reduced by 10%
			priceAdj := make(map[string]float64)
			for _, symbol := range symbols {
				priceAdj[symbol] = 1.0 + s // e.g., 0.90 for -10%, 1.10 for +10%
			}

			// Simulate sequence with scenario prices
			endContext, _ := SimulateSequence(
				req.Sequence,
				req.EvaluationContext.PortfolioContext,
				req.EvaluationContext.AvailableCashEUR,
				req.EvaluationContext.Securities,
				priceAdj,
			)

			// Evaluate end state
			endScore := EvaluateEndState(
				endContext,
				req.Sequence,
				req.EvaluationContext.TransactionCostFixed,
				req.EvaluationContext.TransactionCostPercent,
				0.0, // No cost penalty for stochastic
			)

			results <- scenarioResult{shift: s, score: endScore}
		}(shift)
	}

	// Collect results
	scenarioScores := make(map[string]float64)
	var baseScore, worstCase, bestCase float64

	for i := 0; i < len(req.Shifts); i++ {
		res := <-results
		shiftStr := formatShift(res.shift)
		scenarioScores[shiftStr] = res.score

		// Track special scenarios
		if res.shift == 0.0 {
			baseScore = res.score
		}
		if res.shift == -0.10 {
			worstCase = res.score
		}
		if res.shift == 0.10 {
			bestCase = res.score
		}
	}
	close(results)

	// Calculate weighted average
	weightedScore := 0.0
	for shiftStr, score := range scenarioScores {
		weight := req.Weights[shiftStr]
		weightedScore += score * weight
	}

	return StochasticResult{
		ScenariosEvaluated: len(req.Shifts),
		BaseScore:          baseScore,
		WorstCase:          worstCase,
		BestCase:           bestCase,
		WeightedScore:      weightedScore,
		ScenarioScores:     scenarioScores,
	}
}

// formatShift converts a float shift to a string key for the weights map
func formatShift(shift float64) string {
	// Handle exact matches for common values
	switch shift {
	case 0.0:
		return "0"
	case -0.10:
		return "-0.1"
	case -0.05:
		return "-0.05"
	case 0.05:
		return "0.05"
	case 0.10:
		return "0.1"
	default:
		return fmt.Sprintf("%.2f", shift)
	}
}

