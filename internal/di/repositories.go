// Package di provides dependency injection for repository implementations.
package di

import (
	"fmt"

	"github.com/aristath/sentinel/internal/clientdata"
	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/aristath/sentinel/internal/modules/cash_flows"
	"github.com/aristath/sentinel/internal/modules/dividends"
	"github.com/aristath/sentinel/internal/modules/planning"
	planningrepo "github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/trading"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// InitializeRepositories creates all repositories and stores them in the container
func InitializeRepositories(container *Container, log zerolog.Logger) error {
	if container == nil {
		return fmt.Errorf("container cannot be nil")
	}

	// Override repository (needs universeDB) - must be created before SecurityRepository
	container.OverrideRepo = universe.NewOverrideRepository(
		container.UniverseDB.Conn(),
		log,
	)

	// Security repository (needs universeDB and OverrideRepo for override merging)
	container.SecurityRepo = universe.NewSecurityRepositoryWithOverrides(
		container.UniverseDB.Conn(),
		container.OverrideRepo,
		log,
	)

	// Security provider adapter (wraps SecurityRepo for PositionRepo)
	securityProvider := NewSecurityProviderAdapter(container.SecurityRepo)

	// Position repository (needs portfolioDB, universeDB, and securityProvider)
	container.PositionRepo = portfolio.NewPositionRepository(
		container.PortfolioDB.Conn(),
		container.UniverseDB.Conn(),
		securityProvider,
		log,
	)

	// Score repository (needs portfolioDB and securityProvider for GetBySymbol)
	scoreSecurityProvider := NewTradingSecurityProviderAdapter(container.SecurityRepo)
	container.ScoreRepo = universe.NewScoreRepositoryWithUniverse(
		container.PortfolioDB.Conn(),
		scoreSecurityProvider,
		log,
	)

	// Dividend repository (needs ledgerDB and security provider for ISIN lookup)
	dividendSecurityProvider := NewTradingSecurityProviderAdapter(container.SecurityRepo)
	container.DividendRepo = dividends.NewDividendRepository(
		container.LedgerDB.Conn(),
		dividendSecurityProvider,
		log,
	)

	// Cash repository (needs portfolioDB)
	container.CashRepo = cash_flows.NewCashRepository(
		container.PortfolioDB.Conn(),
		log,
	)

	// Trade repository (needs ledgerDB and security provider for ISIN lookup)
	tradingSecurityProvider := NewTradingSecurityProviderAdapter(container.SecurityRepo)
	container.TradeRepo = trading.NewTradeRepository(
		container.LedgerDB.Conn(),
		tradingSecurityProvider,
		log,
	)

	// Allocation repository (needs configDB and securityProvider)
	allocSecurityProvider := NewAllocationSecurityProviderAdapter(container.SecurityRepo)
	container.AllocRepo = allocation.NewRepository(
		container.ConfigDB.Conn(),
		allocSecurityProvider,
		log,
	)
	container.AllocRepo.SetUniverseDB(container.UniverseDB.Conn())

	// Settings repository (needs configDB)
	container.SettingsRepo = settings.NewRepository(
		container.ConfigDB.Conn(),
		log,
	)

	// Cash flows repository (needs ledgerDB)
	container.CashFlowsRepo = cash_flows.NewRepository(
		container.LedgerDB.Conn(),
		log,
	)

	// Planning recommendation repository (IN-MEMORY - ephemeral data)
	container.RecommendationRepo = planning.NewInMemoryRecommendationRepository(log)

	// Planner config repository (needs configDB)
	container.PlannerConfigRepo = planningrepo.NewConfigRepository(
		container.ConfigDB,
		log,
	)

	// Planner repository (IN-MEMORY - ephemeral sequences/evaluations/best_results)
	container.PlannerRepo = planningrepo.NewInMemoryPlannerRepository(log)

	// History DB client with price filter for read-time anomaly filtering
	priceFilter := universe.NewPriceFilter(log)
	container.HistoryDBClient = universe.NewHistoryDB(
		container.HistoryDB.Conn(),
		priceFilter,
		log,
	)

	// Client data repository (needs clientDataDB)
	container.ClientDataRepo = clientdata.NewRepository(
		container.ClientDataDB.Conn(),
	)

	log.Info().Msg("All repositories initialized")

	return nil
}
