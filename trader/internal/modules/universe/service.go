package universe

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/rs/zerolog"
)

// UniverseService handles universe (securities) business logic and coordinates cleanup
type UniverseService struct {
	securityRepo SecurityRepositoryInterface
	historyDB    *database.DB
	portfolioDB  *database.DB
	syncService  SyncServiceInterface
	log          zerolog.Logger
}

// NewUniverseService creates a new universe service
func NewUniverseService(
	securityRepo SecurityRepositoryInterface,
	historyDB *database.DB,
	portfolioDB *database.DB,
	syncService SyncServiceInterface,
	log zerolog.Logger,
) *UniverseService {
	return &UniverseService{
		securityRepo: securityRepo,
		historyDB:    historyDB,
		portfolioDB:  portfolioDB,
		syncService:  syncService,
		log:          log.With().Str("service", "universe").Logger(),
	}
}

// DeactivateSecurity marks a security as inactive and initiates grace period for cleanup
// Implements 30-day grace period as specified in architecture plan
func (s *UniverseService) DeactivateSecurity(symbol string, gracePeriodDays int) error {
	s.log.Info().
		Str("symbol", symbol).
		Int("grace_period_days", gracePeriodDays).
		Msg("Deactivating security")

	// Default grace period
	if gracePeriodDays <= 0 {
		gracePeriodDays = 30
	}

	// Step 1: Mark security as inactive in universe.db
	err := s.securityRepo.Update(symbol, map[string]interface{}{
		"active": false,
	})
	if err != nil {
		return fmt.Errorf("failed to mark security as inactive: %w", err)
	}

	// Step 2: Mark for removal in history.db (30-day grace period)
	err = s.markForRemoval(symbol, gracePeriodDays)
	if err != nil {
		return fmt.Errorf("failed to mark for removal: %w", err)
	}

	// Step 3: Portfolio and positions are kept during grace period to allow reactivation

	s.log.Info().
		Str("symbol", symbol).
		Int("grace_period_days", gracePeriodDays).
		Msg("Security deactivated successfully - grace period started")

	return nil
}

// ReactivateSecurity cancels deactivation during grace period
func (s *UniverseService) ReactivateSecurity(symbol string) error {
	s.log.Info().Str("symbol", symbol).Msg("Reactivating security")

	// Step 1: Mark security as active in universe.db
	err := s.securityRepo.Update(symbol, map[string]interface{}{
		"active": true,
	})
	if err != nil {
		return fmt.Errorf("failed to mark security as active: %w", err)
	}

	// Step 2: Remove from symbol_removals to cancel cleanup
	err = s.cancelRemoval(symbol)
	if err != nil {
		return fmt.Errorf("failed to cancel removal: %w", err)
	}

	s.log.Info().Str("symbol", symbol).Msg("Security reactivated - cleanup cancelled")

	return nil
}

// markForRemoval adds symbol to symbol_removals table with grace period
func (s *UniverseService) markForRemoval(symbol string, gracePeriodDays int) error {
	// Count rows that will be deleted for logging
	var rowCount int
	err := s.historyDB.Conn().QueryRow(
		"SELECT COUNT(*) FROM daily_prices WHERE symbol = ?",
		symbol,
	).Scan(&rowCount)
	if err != nil && err != sql.ErrNoRows {
		return fmt.Errorf("failed to count rows: %w", err)
	}

	// Insert into symbol_removals
	_, err = s.historyDB.Conn().Exec(`
		INSERT OR REPLACE INTO symbol_removals (symbol, removed_at, grace_period_days, row_count, marked_by)
		VALUES (?, ?, ?, ?, ?)
	`, symbol, time.Now().Unix(), gracePeriodDays, rowCount, "universe_service")

	if err != nil {
		return fmt.Errorf("failed to insert into symbol_removals: %w", err)
	}

	s.log.Debug().
		Str("symbol", symbol).
		Int("grace_period_days", gracePeriodDays).
		Int("row_count", rowCount).
		Msg("Symbol marked for removal")

	return nil
}

// cancelRemoval removes symbol from symbol_removals table
func (s *UniverseService) cancelRemoval(symbol string) error {
	result, err := s.historyDB.Conn().Exec(
		"DELETE FROM symbol_removals WHERE symbol = ?",
		symbol,
	)
	if err != nil {
		return fmt.Errorf("failed to delete from symbol_removals: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		s.log.Debug().
			Str("symbol", symbol).
			Msg("Symbol was not marked for removal")
	} else {
		s.log.Debug().
			Str("symbol", symbol).
			Msg("Removal cancelled successfully")
	}

	return nil
}

// SyncPrices synchronizes current prices for all active securities
func (s *UniverseService) SyncPrices() error {
	if s.syncService == nil {
		s.log.Warn().Msg("SyncService not available, skipping price sync")
		return nil
	}

	updated, err := s.syncService.SyncAllPrices()
	if err != nil {
		return fmt.Errorf("price sync failed: %w", err)
	}

	s.log.Info().Int("updated", updated).Msg("Price sync completed")
	return nil
}

// SyncPricesForExchanges syncs prices only for securities on specified exchanges
func (s *UniverseService) SyncPricesForExchanges(exchangeNames []string) error {
	if s.syncService == nil {
		s.log.Warn().Msg("SyncService not available, skipping price sync")
		return nil
	}

	if len(exchangeNames) == 0 {
		s.log.Debug().Msg("No exchanges provided, skipping price sync")
		return nil
	}

	s.log.Info().
		Int("exchanges", len(exchangeNames)).
		Strs("exchange_names", exchangeNames).
		Msg("Starting market-aware price sync")

	// Get all securities grouped by exchange
	grouped, err := s.securityRepo.GetGroupedByExchange()
	if err != nil {
		return fmt.Errorf("failed to group securities: %w", err)
	}

	// Build symbol map for only the open exchanges
	exchangeSet := make(map[string]bool)
	for _, name := range exchangeNames {
		exchangeSet[name] = true
	}

	symbolMap := make(map[string]*string)
	totalSecurities := 0

	for exchange, securities := range grouped {
		if !exchangeSet[exchange] {
			s.log.Debug().
				Str("exchange", exchange).
				Int("securities", len(securities)).
				Msg("Skipping securities on closed exchange")
			continue
		}

		for _, security := range securities {
			var yahooSymbolPtr *string
			if security.YahooSymbol != "" {
				yahooSymbol := security.YahooSymbol
				yahooSymbolPtr = &yahooSymbol
			}
			symbolMap[security.Symbol] = yahooSymbolPtr
			totalSecurities++
		}
	}

	s.log.Info().
		Int("securities", totalSecurities).
		Int("open_exchanges", len(exchangeNames)).
		Msg("Syncing prices for securities on open exchanges")

	// Sync prices for filtered symbols
	updated, err := s.syncService.SyncPricesForSymbols(symbolMap)
	if err != nil {
		return fmt.Errorf("filtered price sync failed: %w", err)
	}

	s.log.Info().Int("updated", updated).Msg("Market-aware price sync completed")
	return nil
}
