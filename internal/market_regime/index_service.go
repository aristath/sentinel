package market_regime

import (
	"fmt"

	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// SecurityProvider provides read-only access to securities for ISIN lookups.
type SecurityProvider interface {
	GetISINBySymbol(symbol string) (string, error)
}

// MarketIndex represents a market index configuration
type MarketIndex struct {
	Symbol     string // Tradernet symbol (e.g., "SP500.IDX")
	Name       string // Human-readable name (e.g., "S&P 500")
	MarketCode string // Tradernet market code (FIX, EU, HKEX)
	Region     string // Region: US, EU, ASIA
	IndexType  string // PRICE or VOLATILITY (VIX excluded from composite)
	Enabled    bool   // Whether to use for regime detection
	CreatedAt  int64  // Unix timestamp (for DB persistence)
	UpdatedAt  int64  // Unix timestamp (for DB persistence)
}

// MarketIndexService manages market index tracking for regime detection
type MarketIndexService struct {
	securityProvider SecurityProvider
	historyDBClient  universe.HistoryDBInterface // Filtered and cached price access
	tradernet        interface{}                 // Tradernet client (will be properly typed later)
	log              zerolog.Logger
}

// NewMarketIndexService creates a new market index service
func NewMarketIndexService(
	securityProvider SecurityProvider,
	historyDBClient universe.HistoryDBInterface,
	tradernet interface{},
	log zerolog.Logger,
) *MarketIndexService {
	return &MarketIndexService{
		securityProvider: securityProvider,
		historyDBClient:  historyDBClient,
		tradernet:        tradernet,
		log:              log.With().Str("component", "market_index_service").Logger(),
	}
}

// GetMarketReturns returns composite market returns for regime detection.
// Calculates equally-weighted composite returns across all regions with available data.
func (s *MarketIndexService) GetMarketReturns(days int) ([]float64, error) {
	// Get returns for all regions
	regionReturns, err := s.GetReturnsForAllRegions(days)
	if err != nil {
		return nil, err
	}

	if len(regionReturns) == 0 {
		return nil, fmt.Errorf("no index data available for any region")
	}

	// Find the minimum length across all regions
	minLen := days
	for _, returns := range regionReturns {
		if len(returns) < minLen {
			minLen = len(returns)
		}
	}

	if minLen == 0 {
		return nil, fmt.Errorf("insufficient data: all regions have 0 returns")
	}

	// Calculate equally-weighted composite returns across all regions
	numRegions := float64(len(regionReturns))
	compositeReturns := make([]float64, minLen)
	for i := 0; i < minLen; i++ {
		sum := 0.0
		for _, returns := range regionReturns {
			if i < len(returns) {
				sum += returns[i]
			}
		}
		compositeReturns[i] = sum / numRegions
	}

	s.log.Debug().
		Int("regions_count", len(regionReturns)).
		Int("days", minLen).
		Msg("Calculated composite market returns across all regions")

	return compositeReturns, nil
}

// getIndexReturns gets daily returns for a specific index
// Note: Market indices are stored with ISIN = "INDEX-SYMBOL" format in daily_prices.isin column
func (s *MarketIndexService) getIndexReturns(symbol string, days int) ([]float64, error) {
	// Lookup ISIN from securities table via provider
	isin, err := s.securityProvider.GetISINBySymbol(symbol)
	if err != nil {
		return nil, fmt.Errorf("failed to get ISIN for index %s: %w", symbol, err)
	}
	if isin == "" {
		return nil, fmt.Errorf("no ISIN found for index %s", symbol)
	}

	// Get filtered prices using HistoryDB (cached and filtered)
	dailyPrices, err := s.historyDBClient.GetDailyPrices(isin, days+1) // +1 to calculate returns
	if err != nil {
		return nil, fmt.Errorf("failed to get prices for %s: %w", symbol, err)
	}

	if len(dailyPrices) < 2 {
		return nil, fmt.Errorf("insufficient data for %s: need at least 2 days", symbol)
	}

	// dailyPrices comes in DESC order (newest first) from HistoryDB
	// Calculate returns in chronological order (oldest to newest)
	// Return = (newer - older) / older
	returns := make([]float64, 0, len(dailyPrices)-1)
	for i := len(dailyPrices) - 1; i > 0; i-- {
		// dailyPrices[i] is older, dailyPrices[i-1] is newer
		if dailyPrices[i].Close != 0 {
			dailyReturn := (dailyPrices[i-1].Close - dailyPrices[i].Close) / dailyPrices[i].Close
			returns = append(returns, dailyReturn)
		}
	}

	return returns, nil
}

// ============================================================================
// Per-Region Methods
// ============================================================================

// GetPriceIndicesForRegion returns enabled PRICE-type indices for a specific region.
// Uses the known indices from index_discovery.go, filtering by region.
// VIX and other VOLATILITY indices are excluded.
func (s *MarketIndexService) GetPriceIndicesForRegion(region string) []KnownIndex {
	return GetPriceIndicesForRegion(region)
}

// GetReturnsForRegion calculates equally-weighted composite returns for a region's indices.
// Returns daily returns for the last N days.
// Only includes PRICE indices (not VOLATILITY like VIX).
func (s *MarketIndexService) GetReturnsForRegion(region string, days int) ([]float64, error) {
	indices := s.GetPriceIndicesForRegion(region)
	if len(indices) == 0 {
		return nil, fmt.Errorf("no indices available for region %s", region)
	}

	// Get returns for each index
	allIndexReturns := make(map[string][]float64)
	for _, idx := range indices {
		returns, err := s.getIndexReturns(idx.Symbol, days)
		if err != nil {
			s.log.Warn().Err(err).
				Str("symbol", idx.Symbol).
				Str("region", region).
				Msg("Failed to get index returns, skipping")
			continue
		}

		if len(returns) == 0 {
			continue
		}

		allIndexReturns[idx.Symbol] = returns
	}

	if len(allIndexReturns) == 0 {
		return nil, fmt.Errorf("no index data available for region %s", region)
	}

	// Find minimum length (all indices should have same number of days)
	minLen := days
	for _, returns := range allIndexReturns {
		if len(returns) < minLen {
			minLen = len(returns)
		}
	}

	if minLen == 0 {
		return nil, fmt.Errorf("insufficient data for region %s: need at least 1 day", region)
	}

	// Calculate equally-weighted composite returns
	numIndices := float64(len(allIndexReturns))
	compositeReturns := make([]float64, minLen)
	for i := 0; i < minLen; i++ {
		sum := 0.0
		for _, returns := range allIndexReturns {
			if i < len(returns) {
				sum += returns[i]
			}
		}
		compositeReturns[i] = sum / numIndices
	}

	s.log.Debug().
		Str("region", region).
		Int("indices_count", len(allIndexReturns)).
		Int("days", minLen).
		Msg("Calculated composite returns for region")

	return compositeReturns, nil
}

// GetReturnsForAllRegions calculates returns for all regions that have indices.
// Returns a map of region -> returns.
func (s *MarketIndexService) GetReturnsForAllRegions(days int) (map[string][]float64, error) {
	regions := GetAllRegionsWithIndices()
	results := make(map[string][]float64)

	for _, region := range regions {
		returns, err := s.GetReturnsForRegion(region, days)
		if err != nil {
			s.log.Warn().Err(err).Str("region", region).Msg("Failed to get returns for region")
			continue
		}
		results[region] = returns
	}

	if len(results) == 0 {
		return nil, fmt.Errorf("no index data available for any region")
	}

	return results, nil
}
