/**
 * Package di provides dependency injection for planning service initialization.
 *
 * Step 9: Initialize Planning Services
 * Planning services handle opportunity identification, sequence generation, and evaluation.
 */
package di

import (
	"github.com/aristath/sentinel/internal/modules/opportunities"
	"github.com/aristath/sentinel/internal/modules/optimization"
	planningconstraints "github.com/aristath/sentinel/internal/modules/planning/constraints"
	planningevaluation "github.com/aristath/sentinel/internal/modules/planning/evaluation"
	planninghash "github.com/aristath/sentinel/internal/modules/planning/hash"
	planningplanner "github.com/aristath/sentinel/internal/modules/planning/planner"
	planningstatemonitor "github.com/aristath/sentinel/internal/modules/planning/state_monitor"
	"github.com/aristath/sentinel/internal/modules/sequences"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/internal/services"
	"github.com/rs/zerolog"
)

// initializePlanningServices initializes planning-related services.
func initializePlanningServices(container *Container, log zerolog.Logger) error {
	// Opportunities service (with unified calculators - tag-based optimization controlled by config)
	// Identifies trading opportunities using various calculators (profit-taking, averaging-down, etc.)
	// Tag-based filtering can be enabled/disabled via planner config
	// After removing domain.Security: universe.SecurityRepository directly implements opportunities.SecurityRepository
	tagFilter := opportunities.NewTagBasedFilter(container.SecurityRepo, log)
	container.OpportunitiesService = opportunities.NewService(tagFilter, container.SecurityRepo, log)

	// Risk builder (needed for sequences service)
	// Builds risk models (covariance matrices) for portfolio optimization
	// Use TradingSecurityProviderAdapter for ISIN lookups
	optimizationSecurityProvider := NewTradingSecurityProviderAdapter(container.SecurityRepo)
	container.RiskBuilder = optimization.NewRiskModelBuilder(container.HistoryDBClient, optimizationSecurityProvider, container.ConfigDB.Conn(), log)

	// Constraint enforcer for sequences service
	// Enforces per-security constraints (allow_buy, allow_sell) during sequence generation
	// Uses security lookup to check per-security allow_buy/allow_sell constraints
	securityLookup := func(symbol, isin string) (*universe.Security, bool) {
		if isin != "" {
			sec, err := container.SecurityRepo.GetByISIN(isin)
			if err == nil && sec != nil {
				return sec, true
			}
		}
		if symbol != "" {
			sec, err := container.SecurityRepo.GetBySymbol(symbol)
			if err == nil && sec != nil {
				return sec, true
			}
		}
		return nil, false
	}
	sequencesEnforcer := planningconstraints.NewEnforcer(log, securityLookup)

	// Sequences service
	// Generates trade sequences (ordered lists of trades) for portfolio optimization
	container.SequencesService = sequences.NewService(log, container.RiskBuilder, sequencesEnforcer)

	// Evaluation service (4 workers)
	// Evaluates trade sequences using in-process worker pool
	// Calculates portfolio scores, transaction costs, and other metrics
	container.EvaluationService = planningevaluation.NewService(4, log)
	// Wire settings service for temperament-aware scoring
	// Evaluation weights adjust based on user's investment temperament
	container.EvaluationService.SetSettingsService(container.SettingsService)

	// Planner service (core planner)
	// Core planning logic: generates opportunities, creates sequences, evaluates them
	container.PlannerService = planningplanner.NewPlanner(
		container.OpportunitiesService,
		container.SequencesService,
		container.EvaluationService,
		container.SecurityRepo,
		container.CurrencyExchangeService,
		container.BrokerClient,
		log,
	)

	// State hash service (calculates unified state hash for change detection)
	// Calculates a hash of the entire portfolio state (positions, scores, cash, settings, allocation)
	// Used to detect when portfolio state changes and trigger re-planning
	container.StateHashService = planninghash.NewStateHashService(
		container.PositionRepo,
		container.SecurityRepo,
		container.ScoreRepo,
		container.CashManager,
		container.SettingsRepo,
		container.SettingsService,
		container.AllocRepo,
		container.CurrencyExchangeService,
		container.BrokerClient,
		log,
	)
	log.Info().Msg("State hash service initialized")

	// State monitor (monitors unified state hash and emits events on changes)
	// Periodically checks state hash and emits PORTFOLIO_CHANGED events when state changes
	// NOTE: Not started here - will be started in main.go after all services initialized
	container.StateMonitor = planningstatemonitor.NewStateMonitor(
		container.StateHashService,
		container.EventManager,
		log,
	)
	log.Info().Msg("State monitor initialized (not started yet)")

	// Returns calculator - moved here to be available for OpportunityContextBuilder
	// Calculates expected returns for securities based on historical data
	// This is the SINGLE source of truth for expected return calculations (applies multipliers, regime adjustment, etc.)
	container.ReturnsCalc = optimization.NewReturnsCalculator(
		container.PortfolioDB.Conn(),
		optimizationSecurityProvider,
		log,
	)

	// Opportunity Context Builder - unified context building for opportunities, planning, and rebalancing
	// Builds comprehensive context objects for opportunity calculators, planning, and rebalancing
	// Context includes positions, securities, allocation, recent trades, scores, settings, regime, cash, prices
	// Uses ReturnsCalc for unified expected return calculations (same as optimizer)
	// Note: Repositories are used directly (they implement the service interfaces via Go's structural typing)
	container.OpportunityContextBuilder = services.NewOpportunityContextBuilder(
		container.PositionRepo, // Direct use - implements services.PositionRepository
		container.SecurityRepo, // Direct use - implements services.SecurityRepository
		container.AllocRepo,    // Direct use - implements services.AllocationRepository
		container.TradeRepo,    // Direct use - implements services.TradeRepository
		&ocbScoresRepoAdapter{db: container.PortfolioDB.Conn()},
		&ocbSettingsRepoAdapter{repo: container.SettingsRepo, configRepo: container.PlannerConfigRepo},
		&ocbRegimeRepoAdapter{adapter: container.RegimeScoreProvider},
		&ocbCashManagerAdapter{manager: container.CashManager},
		&brokerPriceClientAdapter{client: container.BrokerClient},
		container.PriceConversionService,
		&ocbBrokerClientAdapter{client: container.BrokerClient},
		container.ReturnsCalc, // Unified expected returns calculator
		log,
	)
	log.Info().Msg("Opportunity context builder initialized")

	return nil
}
