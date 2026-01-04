package universe

import (
	"fmt"

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

// DeactivateSecurity marks a security as inactive
// Historical data will be cleaned up by the cleanup job if the symbol becomes orphaned
func (s *UniverseService) DeactivateSecurity(symbol string) error {
	s.log.Info().Str("symbol", symbol).Msg("Deactivating security")

	// Mark security as inactive in universe.db
	err := s.securityRepo.Update(symbol, map[string]interface{}{
		"active": false,
	})
	if err != nil {
		return fmt.Errorf("failed to mark security as inactive: %w", err)
	}

	s.log.Info().Str("symbol", symbol).Msg("Security deactivated successfully")

	return nil
}

// ReactivateSecurity reactivates a previously deactivated security
func (s *UniverseService) ReactivateSecurity(symbol string) error {
	s.log.Info().Str("symbol", symbol).Msg("Reactivating security")

	// Mark security as active in universe.db
	err := s.securityRepo.Update(symbol, map[string]interface{}{
		"active": true,
	})
	if err != nil {
		return fmt.Errorf("failed to mark security as active: %w", err)
	}

	s.log.Info().Str("symbol", symbol).Msg("Security reactivated successfully")

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
