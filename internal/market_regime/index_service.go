package market_regime

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/rs/zerolog"
)

// MarketIndex represents a market index configuration
type MarketIndex struct {
	Symbol string  // e.g., "SPX.US"
	Name   string  // e.g., "S&P 500"
	Weight float64 // Portfolio allocation weight (0.20 for US)
	Region string  // "US", "EU", "ASIA"
	ISIN   string  // ISIN identifier (if available)
}

// MarketIndexService manages market index tracking for regime detection
type MarketIndexService struct {
	universeDB *sql.DB
	historyDB  *sql.DB
	tradernet  interface{} // Tradernet client (will be properly typed later)
	log        zerolog.Logger
}

// NewMarketIndexService creates a new market index service
func NewMarketIndexService(
	universeDB *sql.DB,
	historyDB *sql.DB,
	tradernet interface{},
	log zerolog.Logger,
) *MarketIndexService {
	return &MarketIndexService{
		universeDB: universeDB,
		historyDB:  historyDB,
		tradernet:  tradernet,
		log:        log.With().Str("component", "market_index_service").Logger(),
	}
}

// GetDefaultIndices returns the default market indices matching portfolio allocation
func (s *MarketIndexService) GetDefaultIndices() []MarketIndex {
	return []MarketIndex{
		{
			Symbol: "SPX.US",
			Name:   "S&P 500",
			Weight: 0.20, // 20% US allocation
			Region: "US",
			ISIN:   "", // Will be resolved when added to universe
		},
		{
			Symbol: "STOXX600.EU",
			Name:   "STOXX Europe 600",
			Weight: 0.50, // 50% EU allocation
			Region: "EU",
			ISIN:   "",
		},
		{
			Symbol: "MSCIASIA.ASIA",
			Name:   "MSCI Asia",
			Weight: 0.30, // 30% Asia allocation
			Region: "ASIA",
			ISIN:   "",
		},
	}
}

// EnsureIndicesExist ensures all market indices exist in the universe
// Creates them as non-tradeable securities if they don't exist
func (s *MarketIndexService) EnsureIndicesExist() error {
	indices := s.GetDefaultIndices()

	for _, idx := range indices {
		// Check if index already exists
		var exists bool
		err := s.universeDB.QueryRow(`
			SELECT COUNT(*) > 0 FROM securities
			WHERE symbol = ? AND product_type = 'INDEX'
		`, idx.Symbol).Scan(&exists)
		if err != nil {
			return fmt.Errorf("failed to check index existence: %w", err)
		}

		if exists {
			s.log.Debug().Str("symbol", idx.Symbol).Msg("Index already exists")
			continue
		}

		// Create index as non-tradeable security
		// Use a placeholder ISIN (indices may not have ISINs)
		isin := fmt.Sprintf("INDEX-%s", idx.Symbol)

		_, err = s.universeDB.Exec(`
			INSERT INTO securities
			(isin, symbol, name, product_type, active, allow_buy, allow_sell, created_at, updated_at)
			VALUES (?, ?, ?, 'INDEX', 1, 0, 0, ?, ?)
		`, isin, idx.Symbol, idx.Name, time.Now().Format(time.RFC3339), time.Now().Format(time.RFC3339))
		if err != nil {
			return fmt.Errorf("failed to create index %s: %w", idx.Symbol, err)
		}

		s.log.Info().
			Str("symbol", idx.Symbol).
			Str("name", idx.Name).
			Msg("Created market index in universe")
	}

	return nil
}

// GetCompositeReturns calculates weighted composite returns from market indices
// Returns daily returns for the last N days
func (s *MarketIndexService) GetCompositeReturns(days int) ([]float64, error) {
	indices := s.GetDefaultIndices()

	// Get returns for each index
	allIndexReturns := make(map[string][]float64)
	totalWeight := 0.0

	for _, idx := range indices {
		returns, err := s.getIndexReturns(idx.Symbol, days)
		if err != nil {
			s.log.Warn().Err(err).Str("symbol", idx.Symbol).Msg("Failed to get index returns, skipping")
			continue
		}

		if len(returns) == 0 {
			continue
		}

		allIndexReturns[idx.Symbol] = returns
		totalWeight += idx.Weight
	}

	if len(allIndexReturns) == 0 {
		return nil, fmt.Errorf("no index data available")
	}

	if totalWeight == 0 {
		return nil, fmt.Errorf("total weight is zero")
	}

	// Normalize weights (in case some indices are missing)
	normalizedWeights := make(map[string]float64)
	for _, idx := range indices {
		if _, ok := allIndexReturns[idx.Symbol]; ok {
			normalizedWeights[idx.Symbol] = idx.Weight / totalWeight
		}
	}

	// Find minimum length (all indices should have same number of days)
	minLen := days
	for _, returns := range allIndexReturns {
		if len(returns) < minLen {
			minLen = len(returns)
		}
	}

	if minLen == 0 {
		return nil, fmt.Errorf("insufficient data: need at least 1 day")
	}

	// Calculate weighted composite returns
	compositeReturns := make([]float64, minLen)
	for i := 0; i < minLen; i++ {
		composite := 0.0
		for _, idx := range indices {
			if returns, ok := allIndexReturns[idx.Symbol]; ok && i < len(returns) {
				weight := normalizedWeights[idx.Symbol]
				composite += returns[i] * weight
			}
		}
		compositeReturns[i] = composite
	}

	return compositeReturns, nil
}

// GetMarketReturns returns market returns for regime detection
// This is a convenience method that wraps GetCompositeReturns
func (s *MarketIndexService) GetMarketReturns(days int) ([]float64, error) {
	return s.GetCompositeReturns(days)
}

// getIndexReturns gets daily returns for a specific index
// Note: Market indices are stored with ISIN = "INDEX-SYMBOL" format in daily_prices.isin column
func (s *MarketIndexService) getIndexReturns(symbol string, days int) ([]float64, error) {
	// Lookup ISIN from securities table (indices have ISIN = "INDEX-SYMBOL")
	var isin string
	err := s.universeDB.QueryRow(`
		SELECT isin FROM securities
		WHERE symbol = ? AND product_type = 'INDEX'
	`, symbol).Scan(&isin)
	if err != nil {
		return nil, fmt.Errorf("failed to get ISIN for index %s: %w", symbol, err)
	}
	if isin == "" {
		return nil, fmt.Errorf("no ISIN found for index %s", symbol)
	}

	// Query daily_prices using ISIN
	query := `
		SELECT date, close
		FROM daily_prices
		WHERE isin = ?
		ORDER BY date DESC
		LIMIT ?
	`

	rows, err := s.historyDB.Query(query, isin, days+1) // +1 to calculate returns
	if err != nil {
		return nil, fmt.Errorf("failed to query prices: %w", err)
	}
	defer rows.Close()

	var prices []struct {
		Date  string
		Close float64
	}

	for rows.Next() {
		var dateUnix int64
		var close float64

		if err := rows.Scan(&dateUnix, &close); err != nil {
			return nil, fmt.Errorf("failed to scan price: %w", err)
		}

		// Convert Unix timestamp to YYYY-MM-DD string format
		date := time.Unix(dateUnix, 0).UTC().Format("2006-01-02")

		prices = append(prices, struct {
			Date  string
			Close float64
		}{
			Date:  date,
			Close: close,
		})
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating prices: %w", err)
	}

	if len(prices) < 2 {
		return nil, fmt.Errorf("insufficient data for %s: need at least 2 days", symbol)
	}

	// Reverse to get chronological order (oldest first)
	// Then calculate returns
	returns := make([]float64, 0, len(prices)-1)
	for i := len(prices) - 1; i > 0; i-- {
		if prices[i-1].Close != 0 {
			dailyReturn := (prices[i].Close - prices[i-1].Close) / prices[i-1].Close
			returns = append(returns, dailyReturn)
		}
	}

	return returns, nil
}
