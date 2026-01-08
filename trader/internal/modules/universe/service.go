package universe

import (
	"fmt"

	"github.com/aristath/sentinel/internal/database"
	"github.com/rs/zerolog"
)

// UniverseService handles universe (securities) business logic and coordinates cleanup.
//
// This is a module-specific service that encapsulates universe domain logic.
// It manages security lifecycle operations and price synchronization.
//
// Responsibilities:
//   - Activate/deactivate securities
//   - Synchronize prices from external sources
//   - Coordinate cleanup operations
//
// Dependencies:
//   - SecurityRepositoryInterface: Security data access
//   - SyncServiceInterface: Price synchronization coordination
//   - database.DB: Database access for cleanup operations
//
// See internal/services/README.md for service architecture documentation.
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
// After migration: accepts symbol but uses ISIN internally
func (s *UniverseService) DeactivateSecurity(symbol string) error {
	s.log.Info().Str("symbol", symbol).Msg("Deactivating security")

	// Lookup ISIN from symbol
	security, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to lookup security: %w", err)
	}
	if security == nil {
		return fmt.Errorf("security not found: %s", symbol)
	}
	if security.ISIN == "" {
		return fmt.Errorf("security missing ISIN: %s", symbol)
	}

	// Mark security as inactive in universe.db (using ISIN)
	err = s.securityRepo.Update(security.ISIN, map[string]interface{}{
		"active": false,
	})
	if err != nil {
		return fmt.Errorf("failed to mark security as inactive: %w", err)
	}

	s.log.Info().Str("symbol", symbol).Str("isin", security.ISIN).Msg("Security deactivated successfully")

	return nil
}

// ReactivateSecurity reactivates a previously deactivated security
// After migration: accepts symbol but uses ISIN internally
func (s *UniverseService) ReactivateSecurity(symbol string) error {
	s.log.Info().Str("symbol", symbol).Msg("Reactivating security")

	// Lookup ISIN from symbol
	security, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to lookup security: %w", err)
	}
	if security == nil {
		return fmt.Errorf("security not found: %s", symbol)
	}
	if security.ISIN == "" {
		return fmt.Errorf("security missing ISIN: %s", symbol)
	}

	// Mark security as active in universe.db (using ISIN)
	err = s.securityRepo.Update(security.ISIN, map[string]interface{}{
		"active": true,
	})
	if err != nil {
		return fmt.Errorf("failed to mark security as active: %w", err)
	}

	s.log.Info().Str("symbol", symbol).Str("isin", security.ISIN).Msg("Security reactivated successfully")

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
