package universe

import (
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/clients/yahoo"
	"github.com/rs/zerolog"
)

// HistoricalSyncService handles synchronization of historical price data from Yahoo Finance
// Faithful translation from Python: app/jobs/securities_data_sync.py -> _sync_historical_for_symbol()
type HistoricalSyncService struct {
	yahooClient    *yahoo.Client
	securityRepo   *SecurityRepository
	historyDB      *HistoryDB
	rateLimitDelay time.Duration // External API rate limit delay
	log            zerolog.Logger
}

// NewHistoricalSyncService creates a new historical sync service
func NewHistoricalSyncService(
	yahooClient *yahoo.Client,
	securityRepo *SecurityRepository,
	historyDB *HistoryDB,
	rateLimitDelay time.Duration,
	log zerolog.Logger,
) *HistoricalSyncService {
	return &HistoricalSyncService{
		yahooClient:    yahooClient,
		securityRepo:   securityRepo,
		historyDB:      historyDB,
		rateLimitDelay: rateLimitDelay,
		log:            log.With().Str("service", "historical_sync").Logger(),
	}
}

// SyncHistoricalPrices synchronizes historical price data for a security
// Faithful translation from Python: app/jobs/securities_data_sync.py -> _sync_historical_for_symbol()
//
// Workflow:
// 1. Get security's yahoo_symbol from database
// 2. Check if monthly_prices has data (determines period)
// 3. Fetch from Yahoo Finance (10y initial seed, 1y ongoing updates)
// 4. Insert/replace daily_prices in transaction
// 5. Aggregate to monthly_prices
// 6. Rate limit delay
func (s *HistoricalSyncService) SyncHistoricalPrices(symbol string) error {
	s.log.Info().Str("symbol", symbol).Msg("Starting historical price sync")

	// Get security metadata
	security, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to get security: %w", err)
	}
	if security == nil {
		return fmt.Errorf("security not found: %s", symbol)
	}

	// Check if we have monthly data (indicates initial seeding was done)
	hasMonthly, err := s.historyDB.HasMonthlyData(symbol)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to check monthly data, assuming no data")
		hasMonthly = false
	}

	// Initial seed: 10 years for CAGR calculations
	// Ongoing updates: 1 year for daily charts
	period := "1y"
	if !hasMonthly {
		period = "10y"
		s.log.Info().Str("symbol", symbol).Msg("No monthly data found, performing 10-year initial seed")
	}

	// Fetch historical prices from Yahoo Finance
	yahooSymbolPtr := &security.YahooSymbol
	if security.YahooSymbol == "" {
		yahooSymbolPtr = nil
	}

	ohlcData, err := s.yahooClient.GetHistoricalPrices(symbol, yahooSymbolPtr, period)
	if err != nil {
		return fmt.Errorf("failed to fetch historical prices from Yahoo: %w", err)
	}

	if len(ohlcData) == 0 {
		s.log.Warn().Str("symbol", symbol).Msg("No price data from Yahoo Finance")
		return nil
	}

	s.log.Info().
		Str("symbol", symbol).
		Str("period", period).
		Int("count", len(ohlcData)).
		Msg("Fetched historical prices from Yahoo Finance")

	// Convert Yahoo HistoricalPrice to HistoryDB DailyPrice format
	dailyPrices := make([]DailyPrice, len(ohlcData))
	for i, yPrice := range ohlcData {
		volume := yPrice.Volume
		dailyPrices[i] = DailyPrice{
			Date:   yPrice.Date.Format("2006-01-02"),
			Open:   yPrice.Open,
			High:   yPrice.High,
			Low:    yPrice.Low,
			Close:  yPrice.Close,
			Volume: &volume,
		}
	}

	// Write to history database (transaction, daily + monthly aggregation)
	err = s.historyDB.SyncHistoricalPrices(symbol, dailyPrices)
	if err != nil {
		return fmt.Errorf("failed to sync historical prices to database: %w", err)
	}

	// Rate limit delay to avoid overwhelming Yahoo Finance
	if s.rateLimitDelay > 0 {
		s.log.Debug().
			Str("symbol", symbol).
			Dur("delay", s.rateLimitDelay).
			Msg("Rate limit delay")
		time.Sleep(s.rateLimitDelay)
	}

	s.log.Info().
		Str("symbol", symbol).
		Int("count", len(dailyPrices)).
		Msg("Historical price sync complete")

	return nil
}
