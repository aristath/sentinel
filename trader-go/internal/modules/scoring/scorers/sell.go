package scorers

import (
	"math"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/scoring"
	"github.com/aristath/arduino-trader/internal/modules/scoring/domain"
)

// SellScorer calculates sell priority scores for positions
// Faithful translation from Python: app/modules/scoring/domain/sell.py
type SellScorer struct{}

// NewSellScorer creates a new sell scorer
func NewSellScorer() *SellScorer {
	return &SellScorer{}
}

// CalculateSellScore calculates complete sell score for a position
// Returns SellScore with all components and recommendations
func (ss *SellScorer) CalculateSellScore(
	symbol string,
	quantity float64,
	avgPrice float64,
	currentPrice float64,
	minLot int,
	allowSell bool,
	firstBoughtAt *time.Time,
	lastTransactionAt *time.Time,
	country string,
	industry string,
	totalPortfolioValue float64,
	countryAllocations map[string]float64,
	indAllocations map[string]float64,
	currentVolatility float64,
	historicalVolatility float64,
	distanceFromMA200 float64,
	minHoldDays int,
	sellCooldownDays int,
	maxLossThreshold float64,
	minSellValue float64,
) domain.SellScore {
	// Calculate position value and profit
	positionValue := quantity * currentPrice
	profitPct := 0.0
	if avgPrice > 0 {
		profitPct = (currentPrice - avgPrice) / avgPrice
	}

	// Check eligibility
	eligible, blockReason := checkSellEligibility(
		allowSell,
		profitPct,
		lastTransactionAt,
		maxLossThreshold,
		minHoldDays,
		sellCooldownDays,
	)

	// Calculate days held
	daysHeld := 365 // Default assumption
	if firstBoughtAt != nil {
		daysHeld = int(time.Since(*firstBoughtAt).Hours() / 24)
	}

	// If not eligible, return early
	if !eligible {
		return domain.SellScore{
			Symbol:                symbol,
			Eligible:              false,
			BlockReason:           blockReason,
			UnderperformanceScore: 0,
			TimeHeldScore:         0,
			PortfolioBalanceScore: 0,
			InstabilityScore:      0,
			TotalScore:            0,
			SuggestedSellPct:      0,
			SuggestedSellQuantity: 0,
			SuggestedSellValue:    0,
			ProfitPct:             profitPct,
			DaysHeld:              daysHeld,
		}
	}

	// Calculate component scores
	underperformanceScore := calculateUnderperformanceScore(currentPrice, avgPrice, daysHeld, maxLossThreshold)
	timeHeldScore := calculateTimeHeldScore(firstBoughtAt, minHoldDays)
	portfolioBalanceScore := calculatePortfolioBalanceScore(
		positionValue,
		totalPortfolioValue,
		country,
		industry,
		countryAllocations,
		indAllocations,
	)
	instabilityScore := calculateInstabilityScore(
		profitPct,
		daysHeld,
		currentVolatility,
		historicalVolatility,
		distanceFromMA200,
	)

	// Calculate total score with weights
	totalScore := (underperformanceScore * 0.35) +
		(timeHeldScore * 0.18) +
		(portfolioBalanceScore * 0.18) +
		(instabilityScore * 0.14) +
		(0.15 * 0.5) // Drawdown component (simplified to 0.5 for now)

	// Determine sell quantity
	sellQuantity, sellPct := determineSellQuantity(
		totalScore,
		quantity,
		float64(minLot),
		currentPrice,
		minSellValue,
	)
	sellValue := sellQuantity * currentPrice

	finalEligible := sellQuantity > 0
	finalBlockReason := (*string)(nil)
	if !finalEligible {
		reason := "Below minimum sell value"
		finalBlockReason = &reason
	}

	return domain.SellScore{
		Symbol:                symbol,
		Eligible:              finalEligible,
		BlockReason:           finalBlockReason,
		UnderperformanceScore: round3(underperformanceScore),
		TimeHeldScore:         round3(timeHeldScore),
		PortfolioBalanceScore: round3(portfolioBalanceScore),
		InstabilityScore:      round3(instabilityScore),
		TotalScore:            round3(totalScore),
		SuggestedSellPct:      round3(sellPct),
		SuggestedSellQuantity: int(sellQuantity),
		SuggestedSellValue:    round3(sellValue),
		ProfitPct:             round4(profitPct),
		DaysHeld:              daysHeld,
	}
}

// checkSellEligibility checks if selling is allowed based on hard blocks
func checkSellEligibility(
	allowSell bool,
	profitPct float64,
	lastTransactionAt *time.Time,
	maxLossThreshold float64,
	minHoldDays int,
	sellCooldownDays int,
) (bool, *string) {
	if !allowSell {
		reason := "allow_sell=false"
		return false, &reason
	}

	// Check loss threshold
	if profitPct < maxLossThreshold {
		reason := "Loss exceeds threshold"
		return false, &reason
	}

	// Check minimum hold time
	if lastTransactionAt != nil {
		daysSince := int(time.Since(*lastTransactionAt).Hours() / 24)
		if daysSince < minHoldDays {
			reason := "Held less than minimum days"
			return false, &reason
		}
		if daysSince < sellCooldownDays {
			reason := "Sell cooldown period active"
			return false, &reason
		}
	}

	return true, nil
}

// calculateUnderperformanceScore calculates score based on annualized return vs target
// Higher score = more reason to sell (underperforming or extreme outperforming)
func calculateUnderperformanceScore(currentPrice, avgPrice float64, daysHeld int, maxLossThreshold float64) float64 {
	if avgPrice <= 0 || daysHeld <= 0 {
		return 0.5
	}

	profitPct := (currentPrice - avgPrice) / avgPrice
	yearsHeld := float64(daysHeld) / 365.0

	// Calculate annualized return (CAGR)
	annualizedReturn := profitPct
	if yearsHeld >= 0.25 {
		annualizedReturn = math.Pow(currentPrice/avgPrice, 1/yearsHeld) - 1
	}

	// Score based on return vs target (8-15% annual ideal)
	if profitPct < maxLossThreshold {
		return 0.0 // BLOCKED - loss too big
	} else if annualizedReturn < -0.05 {
		return 0.9 // Loss of -5% to -20%: high sell priority
	} else if annualizedReturn < 0 {
		return 0.7 // Small loss: stagnant, free up capital
	} else if annualizedReturn < scoring.TargetReturnMin {
		return 0.5 // 0-8%: underperforming target
	} else if annualizedReturn <= scoring.TargetReturnMax {
		return 0.1 // 8-15%: ideal range, don't sell
	} else {
		return 0.3 // >15%: exceeding target, consider profits
	}
}

// calculateTimeHeldScore calculates time held score
// Longer hold with underperformance = higher sell priority
func calculateTimeHeldScore(firstBoughtAt *time.Time, minHoldDays int) float64 {
	if firstBoughtAt == nil {
		return 0.6 // Unknown - assume long enough
	}

	daysHeld := int(time.Since(*firstBoughtAt).Hours() / 24)

	if daysHeld < minHoldDays {
		return 0.0 // BLOCKED - held less than 3 months
	} else if daysHeld < 180 {
		return 0.3 // 3-6 months
	} else if daysHeld < 365 {
		return 0.6 // 6-12 months
	} else if daysHeld < 730 {
		return 0.8 // 12-24 months
	} else {
		return 1.0 // 24+ months
	}
}

// calculatePortfolioBalanceScore calculates portfolio balance score
// Overweight positions score higher
func calculatePortfolioBalanceScore(
	positionValue float64,
	totalPortfolioValue float64,
	country string,
	industry string,
	countryAllocations map[string]float64,
	indAllocations map[string]float64,
) float64 {
	if totalPortfolioValue <= 0 {
		return 0.5
	}

	score := 0.0

	// Country overweight (50%)
	countryAlloc := countryAllocations[country]
	countryScore := math.Min(1.0, countryAlloc/0.5) // Normalize to ~1.0 at 50%
	score += countryScore * 0.5

	// Industry overweight (30%)
	indScore := 0.5
	if industry != "" {
		// Handle multiple industries (comma-separated)
		indAlloc := indAllocations[industry]
		indScore = math.Min(1.0, indAlloc/0.3) // Normalize to ~1.0 at 30%
	}
	score += indScore * 0.3

	// Concentration risk (20%)
	positionPct := positionValue / totalPortfolioValue
	concScore := positionPct / 0.10
	if positionPct > 0.10 {
		concScore = math.Min(1.0, positionPct/0.15)
	}
	score += concScore * 0.2

	return score
}

// calculateInstabilityScore detects potential instability/bubble conditions
// High score = signs of unsustainable gains
func calculateInstabilityScore(
	profitPct float64,
	daysHeld int,
	currentVolatility float64,
	historicalVolatility float64,
	distanceFromMA200 float64,
) float64 {
	// Rate of gain (40%)
	rateScore := calculateRateOfGainScore(profitPct, daysHeld)

	// Volatility spike (30%)
	volScore := calculateVolatilitySpikeScore(currentVolatility, historicalVolatility)

	// Valuation stretch (30%)
	valuationScore := calculateValuationStretchScore(distanceFromMA200)

	score := rateScore*0.40 + volScore*0.30 + valuationScore*0.30

	// Apply profit floor
	if profitPct > 1.0 {
		score = math.Max(score, 0.2) // >100% gain
	} else if profitPct > 0.75 {
		score = math.Max(score, 0.1) // >75% gain
	}

	return score
}

// calculateRateOfGainScore calculates rate of gain component
func calculateRateOfGainScore(profitPct float64, daysHeld int) float64 {
	if daysHeld <= 30 {
		return 0.5 // Too early
	}

	years := float64(daysHeld) / 365.0
	annualized := profitPct
	if years > 0 {
		annualized = math.Pow(1+profitPct, 1/years) - 1
	}

	if annualized > scoring.InstabilityRateVeryHot { // >50%
		return 1.0
	} else if annualized > scoring.InstabilityRateHot { // >30%
		return 0.7
	} else if annualized > scoring.InstabilityRateWarm { // >20%
		return 0.4
	} else {
		return 0.1 // Sustainable
	}
}

// calculateVolatilitySpikeScore calculates volatility spike component
func calculateVolatilitySpikeScore(currentVolatility, historicalVolatility float64) float64 {
	if historicalVolatility <= 0 {
		return 0.3 // No historical data
	}

	volRatio := currentVolatility / historicalVolatility

	if volRatio > scoring.VolatilitySpikeHigh { // Vol doubled
		return 1.0
	} else if volRatio > scoring.VolatilitySpikeMed { // Vol up 50%
		return 0.7
	} else if volRatio > scoring.VolatilitySpikeLow { // Vol up 20%
		return 0.4
	} else {
		return 0.1 // Normal
	}
}

// calculateValuationStretchScore calculates valuation stretch component
func calculateValuationStretchScore(distanceFromMA200 float64) float64 {
	if distanceFromMA200 > scoring.ValuationStretchHigh { // >30% above MA
		return 1.0
	} else if distanceFromMA200 > scoring.ValuationStretchMed { // >20% above MA
		return 0.7
	} else if distanceFromMA200 > scoring.ValuationStretchLow { // >10% above MA
		return 0.4
	} else {
		return 0.1 // Near or below MA
	}
}

// determineSellQuantity determines how much to sell based on score
func determineSellQuantity(
	sellScore float64,
	quantity float64,
	minLot float64,
	currentPrice float64,
	minSellValue float64,
) (float64, float64) {
	// Calculate sell percentage (10% to 50%)
	sellPct := math.Max(scoring.MinSellPct, math.Min(scoring.MaxSellPct, scoring.MinSellPct+(sellScore*0.40)))

	// Calculate raw quantity
	rawQuantity := quantity * sellPct

	// Round to min_lot
	sellQuantity := roundToLots(rawQuantity, minLot)

	// Don't sell everything (keep at least 1 lot)
	maxSell := quantity - minLot
	if sellQuantity >= maxSell {
		sellQuantity = roundToLots(maxSell, minLot)
	}

	// Ensure minimum
	if sellQuantity < minLot {
		return 0, 0
	}

	// Check minimum value
	sellValue := sellQuantity * currentPrice
	if sellValue < minSellValue {
		return 0, 0
	}

	// Recalculate actual percentage
	actualSellPct := sellQuantity / quantity
	if quantity == 0 {
		actualSellPct = 0
	}

	return sellQuantity, actualSellPct
}

// roundToLots rounds quantity to nearest lot size
func roundToLots(quantity, lotSize float64) float64 {
	if lotSize <= 0 {
		return quantity
	}
	return math.Floor(quantity/lotSize) * lotSize
}
