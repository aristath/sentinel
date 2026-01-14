package universe

import (
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/rs/zerolog"
)

// HistoricalDataFetcher defines the interface for fetching historical price data.
// This interface is implemented by services.DataFetcherService.
type HistoricalDataFetcher interface {
	// GetHistoricalPrices fetches historical prices with automatic fallback between data sources.
	// Returns prices, the source that was used, and any error.
	GetHistoricalPrices(tradernetSymbol string, yahooSymbol string, years int) ([]HistoricalPriceData, string, error)
}

// HistoricalPriceData represents historical price data from any source.
type HistoricalPriceData struct {
	Date   time.Time
	Open   float64
	High   float64
	Low    float64
	Close  float64
	Volume int64
}

// HistoricalSyncService handles synchronization of historical price data.
// Uses HistoricalDataFetcher for configurable multi-source fetching with fallback,
// or falls back to direct broker client if no fetcher is set.
type HistoricalSyncService struct {
	brokerClient   domain.BrokerClient
	dataFetcher    HistoricalDataFetcher // Optional - if set, uses multi-source fetching
	securityRepo   SecurityLookupInterface
	historyDB      HistoryDBInterface
	priceValidator *PriceValidator // Validates and interpolates abnormal prices
	rateLimitDelay time.Duration   // API rate limit delay
	log            zerolog.Logger
}

// SecurityLookupInterface defines minimal security lookup for HistoricalSyncService
// Used by HistoricalSyncService to enable testing with mocks
type SecurityLookupInterface interface {
	GetBySymbol(symbol string) (*Security, error)
}

// HistoryDBInterface defines the contract for history database operations
// Used by HistoricalSyncService to enable testing with mocks
type HistoryDBInterface interface {
	HasMonthlyData(isin string) (bool, error)
	SyncHistoricalPrices(isin string, prices []DailyPrice) error
	GetRecentPrices(isin string, days int) ([]DailyPrice, error)
}

// NewHistoricalSyncService creates a new historical sync service.
// If DataFetcherService is later set via SetDataFetcher, it will use multi-source
// fetching with automatic fallback. Otherwise, it uses the broker client directly.
func NewHistoricalSyncService(
	brokerClient domain.BrokerClient,
	securityRepo SecurityLookupInterface,
	historyDB HistoryDBInterface,
	priceValidator *PriceValidator,
	rateLimitDelay time.Duration,
	log zerolog.Logger,
) *HistoricalSyncService {
	return &HistoricalSyncService{
		brokerClient:   brokerClient,
		securityRepo:   securityRepo,
		historyDB:      historyDB,
		priceValidator: priceValidator,
		rateLimitDelay: rateLimitDelay,
		log:            log.With().Str("service", "historical_sync").Logger(),
	}
}

// SetDataFetcher sets the data fetcher for multi-source fetching.
// When set, the service will use configurable data source priorities with automatic fallback.
func (s *HistoricalSyncService) SetDataFetcher(fetcher HistoricalDataFetcher) {
	s.dataFetcher = fetcher
}

// SyncHistoricalPrices synchronizes historical price data for a security.
// If DataFetcherService is configured, uses multi-source fetching with automatic fallback.
// Otherwise, falls back to direct Tradernet fetching.
//
// Workflow:
// 1. Get security metadata from database
// 2. Check if monthly_prices has data (determines date range)
// 3. Fetch historical data (via DataFetcherService or direct broker call)
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

	// Extract ISIN - required for history database operations
	if security.ISIN == "" {
		return fmt.Errorf("security %s has no ISIN, cannot sync historical prices", symbol)
	}
	isin := security.ISIN

	// Check if we have monthly data (indicates initial seeding was done)
	hasMonthly, err := s.historyDB.HasMonthlyData(isin)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", symbol).Str("isin", isin).Msg("Failed to check monthly data, assuming no data")
		hasMonthly = false
	}

	// Initial seed: 10 years for CAGR calculations
	// Ongoing updates: 1 year for daily charts
	var years int
	if hasMonthly {
		years = 1
		s.log.Debug().Str("symbol", symbol).Msg("Monthly data exists, fetching 1-year update")
	} else {
		years = 10
		s.log.Info().Str("symbol", symbol).Msg("No monthly data found, performing 10-year initial seed")
	}

	// Fetch historical prices using DataFetcher if available
	var dailyPrices []DailyPrice
	var source string

	if s.dataFetcher != nil {
		// Use multi-source fetching with automatic fallback
		prices, usedSource, err := s.dataFetcher.GetHistoricalPrices(security.Symbol, security.YahooSymbol, years)
		if err != nil {
			return fmt.Errorf("failed to fetch historical prices: %w", err)
		}
		source = usedSource

		// Convert to DailyPrice format
		dailyPrices = make([]DailyPrice, len(prices))
		for i, p := range prices {
			volume := p.Volume
			dailyPrices[i] = DailyPrice{
				Date:   p.Date.Format("2006-01-02"),
				Open:   p.Open,
				High:   p.High,
				Low:    p.Low,
				Close:  p.Close,
				Volume: &volume,
			}
		}
	} else {
		// Fallback to direct broker client
		if s.brokerClient == nil {
			return fmt.Errorf("no data source available (neither DataFetcherService nor broker client)")
		}
		source = "tradernet"

		now := time.Now()
		dateFrom := now.AddDate(-years, 0, 0)

		ohlcData, err := s.brokerClient.GetHistoricalPrices(security.Symbol, dateFrom.Unix(), now.Unix(), 86400)
		if err != nil {
			return fmt.Errorf("failed to fetch historical prices from Tradernet: %w", err)
		}

		// Convert to DailyPrice format
		dailyPrices = make([]DailyPrice, len(ohlcData))
		for i, ohlc := range ohlcData {
			volume := ohlc.Volume
			dailyPrices[i] = DailyPrice{
				Date:   time.Unix(ohlc.Timestamp, 0).Format("2006-01-02"),
				Open:   ohlc.Open,
				High:   ohlc.High,
				Low:    ohlc.Low,
				Close:  ohlc.Close,
				Volume: &volume,
			}
		}
	}

	if len(dailyPrices) == 0 {
		s.log.Warn().Str("symbol", symbol).Str("source", source).Msg("No price data returned")
		return nil
	}

	s.log.Info().
		Str("symbol", symbol).
		Str("source", source).
		Int("count", len(dailyPrices)).
		Msg("Fetched historical prices")

	// Validate and interpolate abnormal prices before storing
	if s.priceValidator != nil {
		// Fetch recent prices from database for context
		context, err := s.historyDB.GetRecentPrices(isin, 30)
		if err != nil {
			s.log.Warn().
				Err(err).
				Str("symbol", symbol).
				Str("isin", isin).
				Msg("Failed to fetch recent prices for context, proceeding without validation")
			context = []DailyPrice{}
		}

		// Validate and interpolate
		validatedPrices, interpolationLogs, err := s.priceValidator.ValidateAndInterpolate(dailyPrices, context)
		if err != nil {
			s.log.Error().
				Err(err).
				Str("symbol", symbol).
				Msg("Price validation failed, using original prices")
			validatedPrices = dailyPrices
		} else {
			// Log interpolation summary
			if len(interpolationLogs) > 0 {
				s.log.Warn().
					Str("symbol", symbol).
					Int("interpolated_count", len(interpolationLogs)).
					Msg("Interpolated abnormal prices")
				for _, log := range interpolationLogs {
					s.log.Info().
						Str("symbol", symbol).
						Str("isin", isin).
						Str("date", log.Date).
						Float64("original_close", log.OriginalClose).
						Float64("interpolated_close", log.InterpolatedClose).
						Str("method", log.Method).
						Str("reason", log.Reason).
						Msg("Price interpolation")
				}
			}
			dailyPrices = validatedPrices
		}
	}

	// Write to history database (transaction, daily + monthly aggregation)
	err = s.historyDB.SyncHistoricalPrices(isin, dailyPrices)
	if err != nil {
		return fmt.Errorf("failed to sync historical prices to database: %w", err)
	}

	// Rate limit delay to avoid overwhelming the API
	if s.rateLimitDelay > 0 {
		s.log.Debug().
			Str("symbol", symbol).
			Dur("delay", s.rateLimitDelay).
			Msg("Rate limit delay")
		time.Sleep(s.rateLimitDelay)
	}

	s.log.Info().
		Str("symbol", symbol).
		Str("isin", isin).
		Str("source", source).
		Int("count", len(dailyPrices)).
		Msg("Historical price sync complete")

	return nil
}
