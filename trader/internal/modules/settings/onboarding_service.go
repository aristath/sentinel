package settings

import (
	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/rs/zerolog"
)

// TradingServiceInterface defines the interface for trading service to avoid import cycles
type TradingServiceInterface interface {
	SyncFromTradernet() error
}

// PortfolioServiceInterface defines the interface for portfolio service
type PortfolioServiceInterface interface {
	SyncFromTradernet() error
}

// SyncServiceInterface defines the interface for sync service
type SyncServiceInterface interface {
	RebuildUniverseFromPortfolio() (int, error)
}

// OnboardingService orchestrates the first-time onboarding flow
type OnboardingService struct {
	portfolioService PortfolioServiceInterface
	syncService      SyncServiceInterface
	tradingService   TradingServiceInterface
	tradernetClient  *tradernet.Client
	log              zerolog.Logger
}

// NewOnboardingService creates a new onboarding service
func NewOnboardingService(
	portfolioService PortfolioServiceInterface,
	syncService SyncServiceInterface,
	tradingService TradingServiceInterface,
	tradernetClient *tradernet.Client,
	log zerolog.Logger,
) *OnboardingService {
	return &OnboardingService{
		portfolioService: portfolioService,
		syncService:      syncService,
		tradingService:   tradingService,
		tradernetClient:  tradernetClient,
		log:              log.With().Str("service", "onboarding").Logger(),
	}
}

// RunOnboarding executes the complete onboarding flow:
// 1. Sync portfolio from Tradernet
// 2. Rebuild universe from portfolio (adds securities + automatically fetches historical data and calculates scores)
// 3. Sync transactions
func (s *OnboardingService) RunOnboarding() error {
	s.log.Info().Msg("Starting onboarding flow")

	// Step 1: Sync portfolio from Tradernet
	s.log.Info().Msg("Step 1: Syncing portfolio from Tradernet")
	if s.portfolioService != nil {
		if err := s.portfolioService.SyncFromTradernet(); err != nil {
			s.log.Error().Err(err).Msg("Failed to sync portfolio from Tradernet")
			// Continue with remaining steps - non-fatal
		} else {
			s.log.Info().Msg("Portfolio sync completed")
		}
	} else {
		s.log.Warn().Msg("Portfolio service not available, skipping portfolio sync")
	}

	// Step 2: Rebuild universe from portfolio
	// This adds missing securities and automatically triggers:
	// - Historical data fetching (10 years initial seed)
	// - Score calculation
	s.log.Info().Msg("Step 2: Rebuilding universe from portfolio")
	if s.syncService != nil {
		addedCount, err := s.syncService.RebuildUniverseFromPortfolio()
		if err != nil {
			s.log.Error().Err(err).Msg("Failed to rebuild universe from portfolio")
			// Continue with remaining steps - non-fatal
		} else {
			s.log.Info().Int("securities_added", addedCount).Msg("Universe rebuild completed")
		}
	} else {
		s.log.Warn().Msg("Sync service not available, skipping universe rebuild")
	}

	// Step 3: Sync transactions
	s.log.Info().Msg("Step 3: Syncing transactions from Tradernet")
	if s.tradingService != nil {
		if err := s.tradingService.SyncFromTradernet(); err != nil {
			s.log.Error().Err(err).Msg("Failed to sync transactions from Tradernet")
			// Continue - non-fatal
		} else {
			s.log.Info().Msg("Transaction sync completed")
		}
	} else {
		s.log.Warn().Msg("Trading service not available, skipping transaction sync")
	}

	s.log.Info().Msg("Onboarding flow completed")
	return nil
}
