package filters

import (
	"math"

	"github.com/aristath/arduino-trader/internal/modules/optimization"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// CovarianceBuilder is an interface for building covariance matrices and correlation data.
type CovarianceBuilder interface {
	BuildCovarianceMatrix(symbols []string, lookbackDays int) ([][]float64, map[string][]float64, []optimization.CorrelationPair, error)
}

type CorrelationAwareFilter struct {
	*BaseFilter
	riskBuilder CovarianceBuilder
}

func NewCorrelationAwareFilter(log zerolog.Logger, riskBuilder CovarianceBuilder) *CorrelationAwareFilter {
	return &CorrelationAwareFilter{
		BaseFilter:  NewBaseFilter(log, "correlation_aware"),
		riskBuilder: riskBuilder,
	}
}

func (f *CorrelationAwareFilter) Name() string {
	return "correlation_aware"
}

func (f *CorrelationAwareFilter) Filter(sequences []domain.ActionSequence, params map[string]interface{}) ([]domain.ActionSequence, error) {
	if len(sequences) == 0 {
		return sequences, nil
	}

	// Extract parameters
	threshold := 0.7
	if val, ok := params["correlation_threshold"].(float64); ok {
		threshold = val
	}

	lookbackDays := 252
	if val, ok := params["lookback_days"].(float64); ok {
		lookbackDays = int(val)
	} else if val, ok := params["lookback_days"].(int); ok {
		lookbackDays = val
	}

	// Check if correlation matrix is pre-provided (for testing/caching)
	var correlationMap map[string]float64
	if matrix, ok := params["correlation_matrix"].(map[string]float64); ok {
		correlationMap = matrix
		f.log.Debug().Msg("Using pre-provided correlation matrix")
	} else {
		// Build correlation map from sequences
		var err error
		correlationMap, err = f.buildCorrelationMap(sequences, lookbackDays, threshold)
		if err != nil {
			f.log.Warn().Err(err).Msg("Failed to build correlation data, passing all sequences through")
			return sequences, nil // Graceful degradation
		}
	}

	// If no correlation data available, pass through all sequences
	if len(correlationMap) == 0 {
		f.log.Debug().Msg("No correlation data available, returning all sequences")
		return sequences, nil
	}

	// Filter sequences based on correlations
	filtered := make([]domain.ActionSequence, 0, len(sequences))
	filteredCount := 0

	for _, seq := range sequences {
		buySymbols := extractBuySymbols(seq)

		// Single or no buys can't be correlated
		if len(buySymbols) < 2 {
			filtered = append(filtered, seq)
			continue
		}

		// Check if any pair has high correlation
		if hasHighCorrelation(buySymbols, correlationMap, threshold) {
			filteredCount++
			f.log.Debug().
				Str("sequence_hash", seq.SequenceHash).
				Strs("buy_symbols", buySymbols).
				Msg("Filtered sequence due to high correlation")
		} else {
			filtered = append(filtered, seq)
		}
	}

	if filteredCount > 0 {
		f.log.Info().
			Int("before", len(sequences)).
			Int("after", len(filtered)).
			Int("removed", filteredCount).
			Float64("threshold", threshold).
			Msg("Correlation filtering complete")
	}

	return filtered, nil
}

// buildCorrelationMap fetches price history and builds correlation map for all BUY symbols.
func (f *CorrelationAwareFilter) buildCorrelationMap(sequences []domain.ActionSequence, lookbackDays int, threshold float64) (map[string]float64, error) {
	// Extract all unique BUY symbols from all sequences
	symbols := extractAllBuySymbols(sequences)

	if len(symbols) < 2 {
		// Need at least 2 symbols to calculate correlations
		return make(map[string]float64), nil
	}

	f.log.Debug().
		Int("symbols", len(symbols)).
		Int("lookback_days", lookbackDays).
		Float64("threshold", threshold).
		Msg("Building correlation matrix for symbols")

	// Use RiskModelBuilder to calculate covariance matrix
	// This will fetch price history and calculate correlations
	_, _, correlationPairs, err := f.riskBuilder.BuildCovarianceMatrix(symbols, lookbackDays)
	if err != nil {
		return nil, err
	}

	// Convert to map for efficient lookup
	correlationMap := optimization.BuildCorrelationMap(correlationPairs)

	f.log.Debug().
		Int("correlation_pairs", len(correlationPairs)).
		Msg("Built correlation matrix")

	return correlationMap, nil
}

// extractAllBuySymbols extracts all unique BUY symbols from all sequences.
func extractAllBuySymbols(sequences []domain.ActionSequence) []string {
	symbolSet := make(map[string]bool)

	for _, seq := range sequences {
		for _, action := range seq.Actions {
			if action.Side == "BUY" {
				symbolSet[action.Symbol] = true
			}
		}
	}

	symbols := make([]string, 0, len(symbolSet))
	for symbol := range symbolSet {
		symbols = append(symbols, symbol)
	}

	return symbols
}

// extractBuySymbols extracts BUY symbols from a single sequence.
func extractBuySymbols(seq domain.ActionSequence) []string {
	symbols := make([]string, 0)
	for _, action := range seq.Actions {
		if action.Side == "BUY" {
			symbols = append(symbols, action.Symbol)
		}
	}
	return symbols
}

// hasHighCorrelation checks if any pair of symbols has correlation above threshold.
func hasHighCorrelation(symbols []string, correlationMap map[string]float64, threshold float64) bool {
	for i := 0; i < len(symbols); i++ {
		for j := i + 1; j < len(symbols); j++ {
			// Check both key orderings (SYMBOL1:SYMBOL2 and SYMBOL2:SYMBOL1)
			key1 := symbols[i] + ":" + symbols[j]
			key2 := symbols[j] + ":" + symbols[i]

			corr, ok1 := correlationMap[key1]
			if !ok1 {
				corr, ok1 = correlationMap[key2]
			}

			if ok1 {
				// Check absolute value (high positive or negative correlation)
				if math.Abs(corr) > threshold {
					return true
				}
			}
		}
	}
	return false
}
