package analytics

import (
	"github.com/rs/zerolog"
)

// FactorExposureTracker calculates portfolio factor exposures (value, quality, momentum, size).
type FactorExposureTracker struct {
	log zerolog.Logger
}

// NewFactorExposureTracker creates a new factor exposure tracker.
func NewFactorExposureTracker(log zerolog.Logger) *FactorExposureTracker {
	if log.GetLevel() == zerolog.Disabled {
		log = zerolog.Nop()
	}
	return &FactorExposureTracker{
		log: log.With().Str("component", "factor_exposure").Logger(),
	}
}

// FactorExposure represents exposure to a single factor.
type FactorExposure struct {
	FactorName    string             // "value", "quality", "momentum", "size"
	Exposure      float64            // Factor loading
	Contributions map[string]float64 // Security contributions
}

// CalculateFactorExposures calculates portfolio factor exposures.
func (fet *FactorExposureTracker) CalculateFactorExposures(
	weights map[string]float64,
	securityMetrics map[string]SecurityMetrics,
) (map[string]FactorExposure, error) {
	exposures := make(map[string]FactorExposure)

	// Calculate each factor
	valueExp := fet.calculateValueFactor(weights, securityMetrics)
	qualityExp := fet.calculateQualityFactor(weights, securityMetrics)
	momentumExp := fet.calculateMomentumFactor(weights, securityMetrics)
	sizeExp := fet.calculateSizeFactor(weights, securityMetrics)

	exposures["value"] = valueExp
	exposures["quality"] = qualityExp
	exposures["momentum"] = momentumExp
	exposures["size"] = sizeExp

	return exposures, nil
}

// SecurityMetrics contains metrics needed for factor calculation.
type SecurityMetrics struct {
	PE            float64 // Price-to-earnings (low = value)
	PB            float64 // Price-to-book (low = value)
	DividendYield float64 // Dividend yield (high = value)
	ProfitMargin  float64 // Profit margin (high = quality)
	ROE           float64 // Return on equity (high = quality)
	DebtEquity    float64 // Debt-to-equity (low = quality)
	Return12M     float64 // 12-month return (momentum)
	Return6M      float64 // 6-month return (momentum)
	MarketCap     float64 // Market capitalization (size)
}

// calculateValueFactor calculates value factor exposure.
// Value = low P/E, low P/B, high dividend yield
func (fet *FactorExposureTracker) calculateValueFactor(
	weights map[string]float64,
	metrics map[string]SecurityMetrics,
) FactorExposure {
	contributions := make(map[string]float64)
	totalExposure := 0.0

	for symbol, weight := range weights {
		metric, hasMetric := metrics[symbol]
		if !hasMetric {
			continue
		}

		// Value score: inverse of P/E and P/B, plus dividend yield
		valueScore := 0.0
		if metric.PE > 0 {
			valueScore += 1.0 / metric.PE // Lower P/E = higher value
		}
		if metric.PB > 0 {
			valueScore += 1.0 / metric.PB // Lower P/B = higher value
		}
		valueScore += metric.DividendYield * 10 // Scale dividend yield

		// Normalize (rough approximation)
		valueScore = valueScore / 3.0

		exposure := weight * valueScore
		contributions[symbol] = exposure
		totalExposure += exposure
	}

	return FactorExposure{
		FactorName:    "value",
		Exposure:      totalExposure,
		Contributions: contributions,
	}
}

// calculateQualityFactor calculates quality factor exposure.
// Quality = high profit margin, high ROE, low debt/equity
func (fet *FactorExposureTracker) calculateQualityFactor(
	weights map[string]float64,
	metrics map[string]SecurityMetrics,
) FactorExposure {
	contributions := make(map[string]float64)
	totalExposure := 0.0

	for symbol, weight := range weights {
		metric, hasMetric := metrics[symbol]
		if !hasMetric {
			continue
		}

		// Quality score: profit margin + ROE - debt/equity
		qualityScore := metric.ProfitMargin + metric.ROE - metric.DebtEquity*0.1

		// Normalize to 0-1 range (rough approximation)
		qualityScore = qualityScore / 0.5
		if qualityScore > 1.0 {
			qualityScore = 1.0
		}
		if qualityScore < 0.0 {
			qualityScore = 0.0
		}

		exposure := weight * qualityScore
		contributions[symbol] = exposure
		totalExposure += exposure
	}

	return FactorExposure{
		FactorName:    "quality",
		Exposure:      totalExposure,
		Contributions: contributions,
	}
}

// calculateMomentumFactor calculates momentum factor exposure.
// Momentum = high 12M and 6M returns
func (fet *FactorExposureTracker) calculateMomentumFactor(
	weights map[string]float64,
	metrics map[string]SecurityMetrics,
) FactorExposure {
	contributions := make(map[string]float64)
	totalExposure := 0.0

	for symbol, weight := range weights {
		metric, hasMetric := metrics[symbol]
		if !hasMetric {
			continue
		}

		// Momentum score: average of 12M and 6M returns
		momentumScore := (metric.Return12M + metric.Return6M) / 2.0

		// Normalize to 0-1 range (assume returns in -1.0 to 1.0 range)
		momentumScore = (momentumScore + 1.0) / 2.0
		if momentumScore > 1.0 {
			momentumScore = 1.0
		}
		if momentumScore < 0.0 {
			momentumScore = 0.0
		}

		exposure := weight * momentumScore
		contributions[symbol] = exposure
		totalExposure += exposure
	}

	return FactorExposure{
		FactorName:    "momentum",
		Exposure:      totalExposure,
		Contributions: contributions,
	}
}

// calculateSizeFactor calculates size factor exposure.
// Size = market cap (small vs large)
func (fet *FactorExposureTracker) calculateSizeFactor(
	weights map[string]float64,
	metrics map[string]SecurityMetrics,
) FactorExposure {
	contributions := make(map[string]float64)
	totalExposure := 0.0

	// Calculate average market cap for normalization
	avgMarketCap := 0.0
	count := 0
	for _, metric := range metrics {
		if metric.MarketCap > 0 {
			avgMarketCap += metric.MarketCap
			count++
		}
	}
	if count > 0 {
		avgMarketCap = avgMarketCap / float64(count)
	}

	for symbol, weight := range weights {
		metric, hasMetric := metrics[symbol]
		if !hasMetric || metric.MarketCap <= 0 {
			continue
		}

		// Size score: smaller = higher score (small cap tilt)
		// Normalize by average market cap
		if avgMarketCap > 0 {
			sizeScore := 1.0 - (metric.MarketCap/avgMarketCap)/2.0
			if sizeScore < 0.0 {
				sizeScore = 0.0
			}
			if sizeScore > 1.0 {
				sizeScore = 1.0
			}

			exposure := weight * sizeScore
			contributions[symbol] = exposure
			totalExposure += exposure
		}
	}

	return FactorExposure{
		FactorName:    "size",
		Exposure:      totalExposure,
		Contributions: contributions,
	}
}
