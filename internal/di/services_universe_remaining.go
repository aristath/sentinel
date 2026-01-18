/**
 * Package di provides dependency injection for remaining universe service initialization.
 *
 * Step 8: Initialize Remaining Universe Services
 * Additional universe services (sync, tagging, scoring).
 */
package di

import (
	"github.com/aristath/sentinel/internal/modules/scoring/scorers"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/internal/services"
	"github.com/rs/zerolog"
)

// initializeRemainingUniverseServices initializes remaining universe-related services.
func initializeRemainingUniverseServices(container *Container, log zerolog.Logger) error {
	// Sync service (scoreCalculator will be set later)
	// Syncs security data (prices, scores) from broker API
	// scoreCalculator will be wired later after SecurityScorer is created
	container.SyncService = universe.NewSyncService(
		container.SecurityRepo,
		container.HistoricalSyncService,
		nil, // scoreCalculator - will be set later
		container.BrokerClient,
		container.SetupService,
		container.PortfolioDB.Conn(),
		log,
	)

	// Universe service with cleanup coordination
	// Manages security universe with cleanup of orphaned data
	container.UniverseService = universe.NewUniverseService(
		container.SecurityRepo,
		container.HistoryDB,
		container.PortfolioDB,
		container.SyncService,
		log,
	)

	// Tag assigner for auto-tagging securities
	// Automatically assigns tags to securities based on their characteristics
	// (e.g., high-quality, value-opportunity, dividend-income)
	container.TagAssigner = universe.NewTagAssigner(log)
	// Wire settings service for temperament-aware tag thresholds
	// Tag thresholds adjust based on user's investment temperament
	tagSettingsAdapterInstance := &tagSettingsAdapter{service: container.SettingsService}
	container.TagAssigner.SetSettingsService(tagSettingsAdapterInstance)

	// Security scorer (used by handlers)
	// Calculates security scores (total score, component scores)
	container.SecurityScorer = scorers.NewSecurityScorer()

	// Security service - loads complete Security data from all sources
	// Single entry point for getting a complete Security with all data (basic, scores, position, tags, price)
	// Create price client adapter for broker quotes (same adapter used by OpportunityContextBuilder)
	priceClientAdapter := &brokerPriceClientAdapter{client: container.BrokerClient}
	container.SecurityService = services.NewSecurityService(
		container.SecurityRepo,
		container.ScoreRepo,
		container.PositionRepo,
		container.HistoryDBClient,
		priceClientAdapter, // Optional - can be nil, price loading will be skipped
		log,
	)

	return nil
}
