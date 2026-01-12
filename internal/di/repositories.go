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

	// Position repository (needs portfolioDB and universeDB)
	container.PositionRepo = portfolio.NewPositionRepository(
		container.PortfolioDB.Conn(),
		container.UniverseDB.Conn(),
		log,
	)

	// Security repository (needs universeDB)
	container.SecurityRepo = universe.NewSecurityRepository(
		container.UniverseDB.Conn(),
		log,
	)

	// Score repository (needs portfolioDB and universeDB for GetBySymbol)
	container.ScoreRepo = universe.NewScoreRepositoryWithUniverse(
		container.PortfolioDB.Conn(),
		container.UniverseDB.Conn(),
		log,
	)

	// Dividend repository (needs ledgerDB)
	container.DividendRepo = dividends.NewDividendRepository(
		container.LedgerDB.Conn(),
		log,
	)

	// Cash repository (needs portfolioDB)
	container.CashRepo = cash_flows.NewCashRepository(
		container.PortfolioDB.Conn(),
		log,
	)

	// Trade repository (needs ledgerDB and universeDB for ISIN lookup)
	container.TradeRepo = trading.NewTradeRepository(
		container.LedgerDB.Conn(),
		container.UniverseDB.Conn(),
		log,
	)

	// Allocation repository (needs configDB)
	container.AllocRepo = allocation.NewRepository(
		container.ConfigDB.Conn(),
		log,
	)

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

	// Grouping repository (needs universeDB)
	container.GroupingRepo = allocation.NewGroupingRepository(
		container.UniverseDB.Conn(),
		log,
	)

	// History DB client (needs historyDB)
	container.HistoryDBClient = universe.NewHistoryDB(
		container.HistoryDB.Conn(),
		log,
	)

	// Client data repository (needs clientDataDB)
	container.ClientDataRepo = clientdata.NewRepository(
		container.ClientDataDB.Conn(),
	)

	// Dismissed filter repository (needs configDB - stores user-dismissed pre-filter reasons)
	container.DismissedFilterRepo = planningrepo.NewDismissedFilterRepository(
		container.ConfigDB,
		log,
	)

	log.Info().Msg("All repositories initialized")

	return nil
}
