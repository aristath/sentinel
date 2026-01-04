package universe

import (
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/rs/zerolog"
)

// SyncService handles data synchronization for securities
// Faithful translation from Python: app/jobs/securities_data_sync.py
type SyncService struct {
	securityRepo    *SecurityRepository
	historicalSync  *HistoricalSyncService
	yahooClient     YahooClientInterface
	scoreCalculator ScoreCalculator
	tradernetClient *tradernet.Client
	setupService    *SecuritySetupService
	db              DBExecutor
	log             zerolog.Logger
}

// NewSyncService creates a new sync service
func NewSyncService(
	securityRepo *SecurityRepository,
	historicalSync *HistoricalSyncService,
	yahooClient YahooClientInterface,
	scoreCalculator ScoreCalculator,
	tradernetClient *tradernet.Client,
	setupService *SecuritySetupService,
	db DBExecutor,
	log zerolog.Logger,
) *SyncService {
	return &SyncService{
		securityRepo:    securityRepo,
		historicalSync:  historicalSync,
		yahooClient:     yahooClient,
		scoreCalculator: scoreCalculator,
		tradernetClient: tradernetClient,
		setupService:    setupService,
		db:              db,
		log:             log.With().Str("service", "sync").Logger(),
	}
}

// SetScoreCalculator sets the score calculator (for deferred wiring)
func (s *SyncService) SetScoreCalculator(calculator ScoreCalculator) {
	s.scoreCalculator = calculator
}

// SyncThresholdHours is how old last_synced must be to require processing (24 hours)
const SyncThresholdHours = 24

// SyncSecuritiesData runs the securities data sync for all securities needing sync
// Faithful translation from Python: app/jobs/securities_data_sync.py -> run_securities_data_sync()
//
// This is the main entry point called by the scheduler every hour.
// It processes securities that haven't been synced in 24 hours.
func (s *SyncService) SyncSecuritiesData() (int, int, error) {
	s.log.Info().Msg("Starting securities data sync")

	securities, err := s.getSecuritiesNeedingSync()
	if err != nil {
		return 0, 0, fmt.Errorf("failed to get securities needing sync: %w", err)
	}

	if len(securities) == 0 {
		s.log.Info().Msg("All securities are up to date, no processing needed")
		return 0, 0, nil
	}

	s.log.Info().Int("count", len(securities)).Msg("Processing securities needing sync")

	processed := 0
	errors := 0

	for _, security := range securities {
		err := s.processSingleSecurity(security.Symbol)
		if err != nil {
			s.log.Error().Err(err).Str("symbol", security.Symbol).Msg("Pipeline failed for security")
			errors++
		} else {
			processed++
		}
	}

	s.log.Info().
		Int("processed", processed).
		Int("errors", errors).
		Msg("Securities data sync complete")

	return processed, errors, nil
}

// RefreshSingleSecurity force refreshes a single security's data
// Faithful translation from Python: app/jobs/securities_data_sync.py -> refresh_single_security()
//
// This bypasses the last_synced check and immediately processes the security.
// Used by the API endpoint for manual refreshes.
func (s *SyncService) RefreshSingleSecurity(symbol string) error {
	s.log.Info().Str("symbol", symbol).Msg("Force refreshing data for security")

	// Run the full pipeline for this security
	err := s.processSingleSecurity(symbol)
	if err != nil {
		return fmt.Errorf("force refresh failed: %w", err)
	}

	s.log.Info().Str("symbol", symbol).Msg("Force refresh complete")
	return nil
}

// processSingleSecurity processes a single security through the full data pipeline
// Faithful translation from Python: app/jobs/securities_data_sync.py -> _process_single_security()
//
// Steps:
// 1. Sync historical prices from Yahoo
// 2. Detect and update country/exchange from Yahoo Finance
// 3. Detect and update industry from Yahoo Finance
// 4. Refresh security score
// 5. Update last_synced timestamp
func (s *SyncService) processSingleSecurity(symbol string) error {
	s.log.Info().Str("symbol", symbol).Msg("Processing security")

	// Step 1: Sync historical prices
	if s.historicalSync != nil {
		err := s.historicalSync.SyncHistoricalPrices(symbol)
		if err != nil {
			return fmt.Errorf("failed to sync historical prices: %w", err)
		}
	}

	// Step 2: Detect and update country/exchange from Yahoo Finance
	err := s.detectAndUpdateCountryAndExchange(symbol)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to update country/exchange")
		// Continue - not fatal
	}

	// Step 3: Detect and update industry from Yahoo Finance
	err = s.detectAndUpdateIndustry(symbol)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to update industry")
		// Continue - not fatal
	}

	// Step 4: Refresh score
	security, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to get security: %w", err)
	}
	if security == nil {
		return fmt.Errorf("security not found: %s", symbol)
	}

	if s.scoreCalculator != nil {
		err = s.scoreCalculator.CalculateAndSaveScore(
			symbol,
			security.YahooSymbol,
			security.Country,
			security.Industry,
		)
		if err != nil {
			s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to refresh score")
			// Continue - not fatal
		}
	}

	// Step 5: Mark as synced
	err = s.updateLastSynced(symbol)
	if err != nil {
		return fmt.Errorf("failed to update last_synced: %w", err)
	}

	s.log.Info().Str("symbol", symbol).Msg("Pipeline complete for security")
	return nil
}

// getSecuritiesNeedingSync gets all active securities that need to be synced
// Faithful translation from Python: app/jobs/securities_data_sync.py -> _get_securities_needing_sync()
//
// A security needs sync if:
// - last_synced is NULL (never synced)
// - last_synced is older than SYNC_THRESHOLD_HOURS
func (s *SyncService) getSecuritiesNeedingSync() ([]Security, error) {
	allSecurities, err := s.securityRepo.GetAllActive()
	if err != nil {
		return nil, fmt.Errorf("failed to get active securities: %w", err)
	}

	threshold := time.Now().Add(-SyncThresholdHours * time.Hour)

	var securitiesNeedingSync []Security
	for _, security := range allSecurities {
		if security.LastSynced == "" {
			// Never synced
			securitiesNeedingSync = append(securitiesNeedingSync, security)
		} else {
			// Try to parse last_synced
			lastSynced, err := time.Parse(time.RFC3339, security.LastSynced)
			if err != nil {
				// Invalid date format, treat as needing sync
				s.log.Warn().
					Err(err).
					Str("symbol", security.Symbol).
					Str("last_synced", security.LastSynced).
					Msg("Invalid last_synced format, treating as needing sync")
				securitiesNeedingSync = append(securitiesNeedingSync, security)
			} else if lastSynced.Before(threshold) {
				// Synced more than 24 hours ago
				securitiesNeedingSync = append(securitiesNeedingSync, security)
			}
		}
	}

	return securitiesNeedingSync, nil
}

// detectAndUpdateIndustry detects and updates industry from Yahoo Finance
// Faithful translation from Python: app/jobs/securities_data_sync.py -> _detect_and_update_industry()
//
// Only updates if the field is empty/NULL to preserve user-edited values
func (s *SyncService) detectAndUpdateIndustry(symbol string) error {
	security, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to get security: %w", err)
	}
	if security == nil {
		return fmt.Errorf("security not found: %s", symbol)
	}

	// Only update if industry is not already set (preserve user-edited values)
	if security.Industry != "" {
		s.log.Debug().Str("symbol", symbol).Msg("Industry already set, skipping Yahoo detection")
		return nil
	}

	// Detect industry from Yahoo Finance
	yahooSymbolPtr := &security.YahooSymbol
	if security.YahooSymbol == "" {
		yahooSymbolPtr = nil
	}

	industry, err := s.yahooClient.GetSecurityIndustry(symbol, yahooSymbolPtr)
	if err != nil {
		return fmt.Errorf("failed to get industry from Yahoo: %w", err)
	}

	if industry == nil || *industry == "" {
		s.log.Debug().Str("symbol", symbol).Msg("No industry detected from Yahoo Finance")
		return nil
	}

	// Update the security's industry in the database
	err = s.securityRepo.Update(symbol, map[string]interface{}{
		"industry": *industry,
	})
	if err != nil {
		return fmt.Errorf("failed to update industry: %w", err)
	}

	s.log.Info().Str("symbol", symbol).Str("industry", *industry).Msg("Updated empty industry")
	return nil
}

// detectAndUpdateCountryAndExchange detects and updates country and exchange from Yahoo Finance
// Faithful translation from Python: app/jobs/securities_data_sync.py -> _detect_and_update_country_and_exchange()
//
// Only updates fields that are empty/NULL to preserve user-edited values
func (s *SyncService) detectAndUpdateCountryAndExchange(symbol string) error {
	security, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to get security: %w", err)
	}
	if security == nil {
		return fmt.Errorf("security not found: %s", symbol)
	}

	// Detect country and exchange from Yahoo Finance
	yahooSymbolPtr := &security.YahooSymbol
	if security.YahooSymbol == "" {
		yahooSymbolPtr = nil
	}

	country, fullExchangeName, err := s.yahooClient.GetSecurityCountryAndExchange(symbol, yahooSymbolPtr)
	if err != nil {
		return fmt.Errorf("failed to get country/exchange from Yahoo: %w", err)
	}

	// Only update fields that are empty/NULL (preserve user-edited values)
	updates := make(map[string]interface{})
	if country != nil && *country != "" && security.Country == "" {
		updates["country"] = *country
	}
	if fullExchangeName != nil && *fullExchangeName != "" && security.FullExchangeName == "" {
		updates["fullExchangeName"] = *fullExchangeName
	}

	if len(updates) == 0 {
		if country != nil || fullExchangeName != nil {
			s.log.Debug().Str("symbol", symbol).Msg("Country/exchange already set, skipping Yahoo detection")
		} else {
			s.log.Debug().Str("symbol", symbol).Msg("No country/exchange detected from Yahoo Finance")
		}
		return nil
	}

	// Update the security's country and fullExchangeName in the database
	err = s.securityRepo.Update(symbol, updates)
	if err != nil {
		return fmt.Errorf("failed to update country/exchange: %w", err)
	}

	s.log.Info().Str("symbol", symbol).Interface("updates", updates).Msg("Updated empty country/exchange")
	return nil
}

// updateLastSynced updates the last_synced timestamp for a security
// Faithful translation from Python: app/jobs/securities_data_sync.py -> _update_last_synced()
func (s *SyncService) updateLastSynced(symbol string) error {
	now := time.Now().Format(time.RFC3339)

	err := s.securityRepo.Update(symbol, map[string]interface{}{
		"last_synced": now,
	})
	if err != nil {
		return fmt.Errorf("failed to update last_synced: %w", err)
	}

	return nil
}

// SyncAllPrices syncs current prices for all active securities
// Faithful translation from Python: app/jobs/daily_sync.py -> sync_prices()
//
// This gets current quotes from Yahoo Finance and updates position prices.
func (s *SyncService) SyncAllPrices() (int, error) {
	s.log.Info().Msg("Starting price sync for all active securities")

	// 1. Get all active securities
	securities, err := s.securityRepo.GetAllActive()
	if err != nil {
		return 0, fmt.Errorf("failed to get active securities: %w", err)
	}

	if len(securities) == 0 {
		s.log.Info().Msg("No securities to sync prices for")
		return 0, nil
	}

	// 2. Build symbol map (tradernet_symbol -> yahoo_override)
	symbolMap := make(map[string]*string)
	for _, security := range securities {
		var yahooSymbolPtr *string
		if security.YahooSymbol != "" {
			// Create new string to avoid range variable issues
			yahooSymbol := security.YahooSymbol
			yahooSymbolPtr = &yahooSymbol
		}
		symbolMap[security.Symbol] = yahooSymbolPtr
	}

	// 3. Fetch batch quotes from Yahoo
	quotes, err := s.yahooClient.GetBatchQuotes(symbolMap)
	if err != nil {
		return 0, fmt.Errorf("failed to fetch batch quotes: %w", err)
	}

	// 4. Update position prices in state.db
	updated := 0
	now := time.Now()

	for symbol, price := range quotes {
		if price == nil {
			s.log.Warn().Str("symbol", symbol).Msg("No price data received")
			continue
		}

		// Update positions table
		result, err := s.db.Exec(`
			UPDATE positions
			SET current_price = ?,
				market_value_eur = quantity * ? / currency_rate,
				last_updated = ?
			WHERE symbol = ?
		`, *price, *price, now, symbol)

		if err != nil {
			s.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to update position price")
			continue
		}

		rowsAffected, _ := result.RowsAffected()
		if rowsAffected > 0 {
			updated++
		}
	}

	s.log.Info().
		Int("total", len(securities)).
		Int("updated", updated).
		Msg("Price sync complete")

	return updated, nil
}

// SyncAllHistoricalData syncs historical price data for all active securities
// Faithful translation from Python: app/jobs/historical_data_sync.py -> sync_historical_data()
//
// This syncs historical prices for all securities (not just those needing sync).
func (s *SyncService) SyncAllHistoricalData() (int, int, error) {
	s.log.Info().Msg("Starting historical data sync for all securities")

	securities, err := s.securityRepo.GetAllActive()
	if err != nil {
		return 0, 0, fmt.Errorf("failed to get active securities: %w", err)
	}

	if len(securities) == 0 {
		s.log.Info().Msg("No securities to sync")
		return 0, 0, nil
	}

	s.log.Info().Int("count", len(securities)).Msg("Syncing historical data for all securities")

	processed := 0
	errors := 0

	for _, security := range securities {
		if s.historicalSync != nil {
			err := s.historicalSync.SyncHistoricalPrices(security.Symbol)
			if err != nil {
				s.log.Error().Err(err).Str("symbol", security.Symbol).Msg("Failed to sync historical prices")
				errors++
			} else {
				processed++
			}
		}
	}

	s.log.Info().
		Int("processed", processed).
		Int("errors", errors).
		Msg("Historical data sync complete")

	return processed, errors, nil
}

// RebuildUniverseFromPortfolio rebuilds the universe from current portfolio positions
// Faithful translation from Python: app/modules/system/api/status.py -> rebuild_universe_from_portfolio()
//
// This gets all securities from the portfolio and adds any missing ones to the universe.
func (s *SyncService) RebuildUniverseFromPortfolio() (int, error) {
	s.log.Info().Msg("Rebuilding universe from portfolio")

	// Step 1: Check tradernet client availability
	if s.tradernetClient == nil {
		return 0, fmt.Errorf("tradernet client not available")
	}

	// Step 2: Fetch current portfolio positions
	positions, err := s.tradernetClient.GetPortfolio()
	if err != nil {
		return 0, fmt.Errorf("failed to fetch portfolio: %w", err)
	}

	s.log.Info().Int("positions", len(positions)).Msg("Fetched portfolio positions")

	// Step 3: Identify missing securities
	missingSymbols := []string{}
	for _, pos := range positions {
		existing, err := s.securityRepo.GetBySymbol(pos.Symbol)
		if err != nil {
			s.log.Error().Err(err).Str("symbol", pos.Symbol).Msg("Failed to check security")
			continue
		}
		if existing == nil {
			missingSymbols = append(missingSymbols, pos.Symbol)
		}
	}

	if len(missingSymbols) == 0 {
		s.log.Info().Msg("All portfolio securities are already in universe")
		return 0, nil
	}

	// Step 4: Add missing securities using SecuritySetupService
	if s.setupService == nil {
		return 0, fmt.Errorf("setup service not available")
	}

	added := 0
	failed := 0

	for _, symbol := range missingSymbols {
		s.log.Info().Str("symbol", symbol).Msg("Adding missing security to universe")

		// Use AddSecurityByIdentifier (handles full data pipeline)
		security, err := s.setupService.AddSecurityByIdentifier(
			symbol, // identifier
			1,      // minLot
			true,   // allowBuy
			true,   // allowSell
		)

		if err != nil {
			s.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to add security")
			failed++
			continue
		}

		yahooSymbol := security.YahooSymbol
		if yahooSymbol == "" {
			yahooSymbol = "<none>"
		}

		s.log.Info().
			Str("symbol", security.Symbol).
			Str("isin", security.ISIN).
			Str("yahoo_symbol", yahooSymbol).
			Msg("Successfully added security to universe")
		added++
	}

	s.log.Info().
		Int("added", added).
		Int("failed", failed).
		Int("total_missing", len(missingSymbols)).
		Msg("Universe rebuild complete")

	return added, nil
}

// SyncPricesForSymbols syncs prices for a filtered set of symbols
// Similar to SyncAllPrices but accepts a pre-filtered symbol map
func (s *SyncService) SyncPricesForSymbols(symbolMap map[string]*string) (int, error) {
	s.log.Info().Int("symbols", len(symbolMap)).Msg("Starting filtered price sync")

	if len(symbolMap) == 0 {
		s.log.Info().Msg("No symbols to sync prices for")
		return 0, nil
	}

	// Fetch batch quotes from Yahoo
	quotes, err := s.yahooClient.GetBatchQuotes(symbolMap)
	if err != nil {
		return 0, fmt.Errorf("failed to fetch batch quotes: %w", err)
	}

	// Update position prices in state.db
	updated := 0
	now := time.Now()

	for symbol, price := range quotes {
		if price == nil {
			s.log.Warn().Str("symbol", symbol).Msg("No price data received")
			continue
		}

		// Update positions table
		result, err := s.db.Exec(`
			UPDATE positions
			SET current_price = ?,
				market_value_eur = quantity * ? / currency_rate,
				last_updated = ?
			WHERE symbol = ?
		`, *price, *price, now, symbol)

		if err != nil {
			s.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to update position price")
			continue
		}

		rowsAffected, _ := result.RowsAffected()
		if rowsAffected > 0 {
			updated++
		}
	}

	s.log.Info().
		Int("requested", len(symbolMap)).
		Int("updated", updated).
		Msg("Filtered price sync complete")

	return updated, nil
}
