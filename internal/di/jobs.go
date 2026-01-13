// Package di provides dependency injection for scheduler jobs.
package di

import (
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/clientdata"
	"github.com/aristath/sentinel/internal/config"
	"github.com/aristath/sentinel/internal/database"
	"github.com/aristath/sentinel/internal/deployment"
	"github.com/aristath/sentinel/internal/modules/cleanup"
	"github.com/aristath/sentinel/internal/modules/display"
	"github.com/aristath/sentinel/internal/modules/symbolic_regression"
	"github.com/aristath/sentinel/internal/queue"
	"github.com/aristath/sentinel/internal/reliability"
	"github.com/aristath/sentinel/internal/scheduler"
	"github.com/rs/zerolog"
)

// RegisterJobs registers all jobs with the queue system
// Returns JobInstances for manual triggering via API
// deploymentManager is optional (can be nil if deployment is disabled)
func RegisterJobs(container *Container, cfg *config.Config, displayManager *display.StateManager, deploymentManager interface{}, log zerolog.Logger) (*JobInstances, error) {
	if container == nil {
		return nil, fmt.Errorf("container cannot be nil")
	}

	instances := &JobInstances{}

	// ==========================================
	// Register Event Listeners
	// ==========================================
	queue.RegisterListeners(container.EventBus, container.QueueManager, container.JobRegistry, log)

	// ==========================================
	// INDIVIDUAL HEALTH CHECK JOBS (created first, then used by composite job)
	// ==========================================
	// Note: Individual health check jobs will be created later, composite job created at end

	// ==========================================
	// INDIVIDUAL SYNC JOBS (created first, then used by composite jobs)
	// ==========================================
	balanceAdapter := scheduler.NewBalanceAdapter(container.CashManager, log)

	// ==========================================
	// COMPOSITE DIVIDEND REINVESTMENT JOB (orchestrates individual dividend jobs)
	// ==========================================
	// Note: Individual dividend jobs must be created first (see below)

	// ==========================================
	// COMPOSITE PLANNER BATCH JOB (orchestrates individual planning jobs)
	// ==========================================
	// Note: Individual planning jobs must be created first (see below)

	// ==========================================
	// Job 5: Event-Based Trading
	// ==========================================
	eventBasedTrading := scheduler.NewEventBasedTradingJob(scheduler.EventBasedTradingConfig{
		Log:                log,
		RecommendationRepo: container.RecommendationRepo,
		TradingService:     container.TradingService,
		EventManager:       container.EventManager,
	})
	container.JobRegistry.Register(queue.JobTypeEventBasedTrading, queue.JobToHandler(eventBasedTrading))
	instances.EventBasedTrading = eventBasedTrading

	// ==========================================
	// Job 6: Tag Update
	// ==========================================
	tagUpdateJob := scheduler.NewTagUpdateJob(scheduler.TagUpdateConfig{
		Log:          log,
		SecurityRepo: container.SecurityRepo,
		ScoreRepo:    container.ScoreRepo,
		TagAssigner:  container.TagAssigner,
		YahooClient:  container.YahooClient,
		HistoryDB:    container.HistoryDBClient,
		PortfolioDB:  container.PortfolioDB.Conn(),
		PositionRepo: container.PositionRepo,
	})
	container.JobRegistry.Register(queue.JobTypeTagUpdate, queue.JobToHandler(tagUpdateJob))
	instances.TagUpdate = tagUpdateJob

	// ==========================================
	// RELIABILITY JOBS
	// ==========================================

	// Job 7: History Cleanup
	historyCleanup := cleanup.NewHistoryCleanupJob(
		container.HistoryDB,
		container.PortfolioDB,
		container.UniverseDB,
		log,
	)
	container.JobRegistry.Register(queue.JobTypeHistoryCleanup, queue.JobToHandler(historyCleanup))
	instances.HistoryCleanup = historyCleanup

	// Job 8: Recommendation Garbage Collection (24h TTL)
	recommendationGC := scheduler.NewRecommendationGCJob(
		container.RecommendationRepo,
		24*time.Hour, // Max age: 24 hours
		log,
	)
	container.JobRegistry.Register(queue.JobTypeRecommendationGC, queue.JobToHandler(recommendationGC))
	instances.RecommendationGC = recommendationGC

	// Job 8b: Client Data Cleanup (removes expired API cache entries)
	clientDataCleanup := clientdata.NewCleanupJob(container.ClientDataRepo, log)
	container.JobRegistry.Register(queue.JobTypeClientDataCleanup, queue.JobToHandler(clientDataCleanup))
	instances.ClientDataCleanup = clientDataCleanup

	// Job 9: Hourly Backup
	hourlyBackup := reliability.NewHourlyBackupJob(container.BackupService)
	container.JobRegistry.Register(queue.JobTypeHourlyBackup, queue.JobToHandler(hourlyBackup))
	instances.HourlyBackup = hourlyBackup

	// Job 9: Daily Backup
	dailyBackup := reliability.NewDailyBackupJob(container.BackupService)
	container.JobRegistry.Register(queue.JobTypeDailyBackup, queue.JobToHandler(dailyBackup))
	instances.DailyBackup = dailyBackup

	// Job 10: Daily Maintenance
	dataDir := cfg.DataDir
	backupDir := dataDir + "/backups"
	databases := map[string]*database.DB{
		"universe":  container.UniverseDB,
		"config":    container.ConfigDB,
		"ledger":    container.LedgerDB,
		"portfolio": container.PortfolioDB,
		// "agents": removed - sequences/evaluations now in-memory
		"history":     container.HistoryDB,
		"cache":       container.CacheDB,
		"client_data": container.ClientDataDB,
	}
	dailyMaintenance := reliability.NewDailyMaintenanceJob(databases, container.HealthServices, backupDir, log)
	container.JobRegistry.Register(queue.JobTypeDailyMaintenance, queue.JobToHandler(dailyMaintenance))
	instances.DailyMaintenance = dailyMaintenance

	// Job 11: Weekly Backup
	weeklyBackup := reliability.NewWeeklyBackupJob(container.BackupService)
	container.JobRegistry.Register(queue.JobTypeWeeklyBackup, queue.JobToHandler(weeklyBackup))
	instances.WeeklyBackup = weeklyBackup

	// Job 12: Weekly Maintenance
	weeklyMaintenance := reliability.NewWeeklyMaintenanceJob(databases, container.HistoryDB, log)
	container.JobRegistry.Register(queue.JobTypeWeeklyMaintenance, queue.JobToHandler(weeklyMaintenance))
	instances.WeeklyMaintenance = weeklyMaintenance

	// Job 13: Monthly Backup
	monthlyBackup := reliability.NewMonthlyBackupJob(container.BackupService)
	container.JobRegistry.Register(queue.JobTypeMonthlyBackup, queue.JobToHandler(monthlyBackup))
	instances.MonthlyBackup = monthlyBackup

	// Job 14: Monthly Maintenance
	monthlyMaintenance := reliability.NewMonthlyMaintenanceJob(databases, container.HealthServices, backupDir, log)
	container.JobRegistry.Register(queue.JobTypeMonthlyMaintenance, queue.JobToHandler(monthlyMaintenance))
	instances.MonthlyMaintenance = monthlyMaintenance

	// ==========================================
	// R2 CLOUD BACKUP JOBS (optional - only if configured)
	// ==========================================

	if container.R2BackupService != nil {
		// Job 15: R2 Backup
		r2BackupJob := scheduler.NewR2BackupJob(scheduler.R2BackupJobConfig{
			Log:             log,
			Service:         container.R2BackupService,
			SettingsService: container.SettingsService,
		})
		container.JobRegistry.Register(queue.JobTypeR2Backup, queue.JobToHandler(r2BackupJob))
		instances.R2Backup = r2BackupJob

		// Job 16: R2 Backup Rotation
		r2RotationJob := scheduler.NewR2BackupRotationJob(scheduler.R2BackupRotationJobConfig{
			Log:             log,
			Service:         container.R2BackupService,
			SettingsService: container.SettingsService,
		})
		container.JobRegistry.Register(queue.JobTypeR2BackupRotation, queue.JobToHandler(r2RotationJob))
		instances.R2BackupRotation = r2RotationJob

		log.Info().Msg("R2 backup jobs registered")
	} else {
		log.Debug().Msg("R2 backup service not available - R2 jobs not registered")
	}

	// ==========================================
	// ADAPTIVE MARKET HYPOTHESIS (AMH) SYSTEM
	// ==========================================

	// Job 15: Adaptive Market Check
	adaptiveMarketJob := scheduler.NewAdaptiveMarketJob(scheduler.AdaptiveMarketJobConfig{
		Log:                 log,
		RegimeDetector:      container.RegimeDetector,
		RegimePersistence:   container.RegimePersistence,
		AdaptiveService:     container.AdaptiveMarketService,
		AdaptationThreshold: 0.1,
		ConfigDB:            container.ConfigDB.Conn(),
	})
	container.JobRegistry.Register(queue.JobTypeAdaptiveMarket, queue.JobToHandler(adaptiveMarketJob))
	instances.AdaptiveMarketJob = adaptiveMarketJob

	// ==========================================
	// Job 16: Formula Discovery
	// ==========================================
	formulaStorage := symbolic_regression.NewFormulaStorage(container.ConfigDB.Conn(), log)
	dataPrep := symbolic_regression.NewDataPrep(
		container.HistoryDB.Conn(),
		container.PortfolioDB.Conn(),
		container.ConfigDB.Conn(),
		container.UniverseDB.Conn(),
		log,
	)
	discoveryService := symbolic_regression.NewDiscoveryService(dataPrep, formulaStorage, log)
	formulaScheduler := symbolic_regression.NewScheduler(discoveryService, dataPrep, formulaStorage, log)
	formulaDiscovery := scheduler.NewFormulaDiscoveryJob(scheduler.FormulaDiscoveryConfig{
		Scheduler:      formulaScheduler,
		Log:            log,
		IntervalMonths: 1,
		ForwardMonths:  6,
	})
	container.JobRegistry.Register(queue.JobTypeFormulaDiscovery, queue.JobToHandler(formulaDiscovery))
	instances.FormulaDiscovery = formulaDiscovery

	// ==========================================
	// INDIVIDUAL SYNC JOBS
	// ==========================================

	// Sync Trades Job
	tradingServiceAdapter := scheduler.NewTradingServiceAdapter(container.TradingService)
	syncTrades := scheduler.NewSyncTradesJob(scheduler.SyncTradesConfig{
		Log:            log,
		TradingService: tradingServiceAdapter,
	})
	container.JobRegistry.Register(queue.JobTypeSyncTrades, queue.JobToHandler(syncTrades))
	instances.SyncTrades = syncTrades

	// Sync Cash Flows Job
	cashFlowsServiceAdapter := scheduler.NewCashFlowsServiceAdapter(container.CashFlowsService)
	syncCashFlows := scheduler.NewSyncCashFlowsJob(scheduler.SyncCashFlowsConfig{
		Log:              log,
		CashFlowsService: cashFlowsServiceAdapter,
	})
	container.JobRegistry.Register(queue.JobTypeSyncCashFlows, queue.JobToHandler(syncCashFlows))
	instances.SyncCashFlows = syncCashFlows

	// Sync Portfolio Job
	portfolioServiceAdapter := scheduler.NewPortfolioServiceAdapter(container.PortfolioService)
	syncPortfolio := scheduler.NewSyncPortfolioJob(scheduler.SyncPortfolioConfig{
		Log:              log,
		PortfolioService: portfolioServiceAdapter,
	})
	container.JobRegistry.Register(queue.JobTypeSyncPortfolio, queue.JobToHandler(syncPortfolio))
	instances.SyncPortfolio = syncPortfolio

	// Sync Prices Job
	universeServiceAdapter := scheduler.NewUniverseServiceAdapter(container.UniverseService)
	syncPrices := scheduler.NewSyncPricesJob(scheduler.SyncPricesConfig{
		Log:             log,
		UniverseService: universeServiceAdapter,
	})
	container.JobRegistry.Register(queue.JobTypeSyncPrices, queue.JobToHandler(syncPrices))
	instances.SyncPrices = syncPrices

	// Sync Exchange Rates Job
	syncExchangeRates := scheduler.NewSyncExchangeRatesJob(scheduler.SyncExchangeRatesConfig{
		Log:                      log,
		ExchangeRateCacheService: container.ExchangeRateCacheService,
	})
	container.JobRegistry.Register(queue.JobTypeSyncExchangeRates, queue.JobToHandler(syncExchangeRates))
	instances.SyncExchangeRates = syncExchangeRates

	// Check Negative Balances Job
	checkNegativeBalances := scheduler.NewCheckNegativeBalancesJob(scheduler.CheckNegativeBalancesConfig{
		Log:                log,
		BalanceService:     balanceAdapter,
		EmergencyRebalance: container.EmergencyRebalance,
	})
	container.JobRegistry.Register(queue.JobTypeCheckNegativeBalances, queue.JobToHandler(checkNegativeBalances))
	instances.CheckNegativeBalances = checkNegativeBalances

	// Update Display Ticker Job
	updateDisplayTicker := scheduler.NewUpdateDisplayTickerJob(scheduler.UpdateDisplayTickerConfig{
		Log:                 log,
		UpdateDisplayTicker: container.UpdateDisplayTicker,
	})
	container.JobRegistry.Register(queue.JobTypeUpdateDisplayTicker, queue.JobToHandler(updateDisplayTicker))
	instances.UpdateDisplayTicker = updateDisplayTicker

	// Retry Trades Job (processes pending trade retries with 7-hour interval)
	retryTrades := scheduler.NewRetryTradesJob(scheduler.RetryTradesConfig{
		Log:                   log,
		TradeRepo:             container.TradeRepo,
		TradeExecutionService: container.TradeExecutionService,
	})
	container.JobRegistry.Register(queue.JobTypeRetryTrades, queue.JobToHandler(retryTrades))
	instances.RetryTrades = retryTrades

	// ==========================================
	// COMPOSITE SYNC CYCLE JOB (orchestrates individual sync jobs)
	// ==========================================
	syncCycle := scheduler.NewSyncCycleJob(scheduler.SyncCycleConfig{
		Log:                      log,
		DisplayManager:           displayManager,
		EventManager:             container.EventManager,
		SyncTradesJob:            syncTrades,
		SyncCashFlowsJob:         syncCashFlows,
		SyncPortfolioJob:         syncPortfolio,
		SyncPricesJob:            syncPrices,
		SyncExchangeRatesJob:     syncExchangeRates,
		CheckNegativeBalancesJob: checkNegativeBalances,
		UpdateDisplayTickerJob:   updateDisplayTicker,
	})
	container.JobRegistry.Register(queue.JobTypeSyncCycle, queue.JobToHandler(syncCycle))
	instances.SyncCycle = syncCycle

	// ==========================================
	// INDIVIDUAL PLANNING JOBS
	// ==========================================

	// Generate Portfolio Hash Job
	// Note: GeneratePortfolioHashJob uses concrete types, not interfaces
	generatePortfolioHash := scheduler.NewGeneratePortfolioHashJob(scheduler.GeneratePortfolioHashConfig{
		Log:          log,
		PositionRepo: container.PositionRepo,
		SecurityRepo: container.SecurityRepo,
		CashManager:  container.CashManager,
	})
	container.JobRegistry.Register(queue.JobTypeGeneratePortfolioHash, queue.JobToHandler(generatePortfolioHash))
	instances.GeneratePortfolioHash = generatePortfolioHash

	// Get Optimizer Weights Job
	// Create adapters for repositories (using interface adapters)
	positionRepoAdapter := scheduler.NewPositionRepositoryAdapter(container.PositionRepo)
	securityRepoAdapter := scheduler.NewSecurityRepositoryAdapter(container.SecurityRepo)
	allocRepoAdapter := scheduler.NewAllocationRepositoryAdapter(container.AllocRepo)
	priceClientAdapter := scheduler.NewPriceClientAdapter(container.YahooClient)
	optimizerServiceAdapter := scheduler.NewOptimizerServiceAdapter(container.OptimizerService)
	priceConversionServiceAdapter := scheduler.NewPriceConversionServiceAdapter(container.PriceConversionService)
	plannerConfigRepoAdapter := scheduler.NewPlannerConfigRepositoryAdapter(container.PlannerConfigRepo)
	getOptimizerWeights := scheduler.NewGetOptimizerWeightsJob(
		positionRepoAdapter,
		securityRepoAdapter,
		allocRepoAdapter,
		container.CashManager,
		priceClientAdapter,
		optimizerServiceAdapter,
		priceConversionServiceAdapter,
		plannerConfigRepoAdapter,
	)
	getOptimizerWeights.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeGetOptimizerWeights, queue.JobToHandler(getOptimizerWeights))
	instances.GetOptimizerWeights = getOptimizerWeights

	// Build Opportunity Context Job - uses unified OpportunityContextBuilder
	buildOpportunityContext := scheduler.NewBuildOpportunityContextJob(
		container.OpportunityContextBuilder,
	)
	buildOpportunityContext.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeBuildOpportunityContext, queue.JobToHandler(buildOpportunityContext))
	instances.BuildOpportunityContext = buildOpportunityContext

	// Create Trade Plan Job
	configRepoAdapter := scheduler.NewConfigRepositoryAdapter(container.PlannerConfigRepo)
	plannerServiceAdapter := scheduler.NewPlannerServiceAdapter(container.PlannerService)
	createTradePlan := scheduler.NewCreateTradePlanJob(plannerServiceAdapter, configRepoAdapter)
	createTradePlan.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeCreateTradePlan, queue.JobToHandler(createTradePlan))
	instances.CreateTradePlan = createTradePlan

	// Store Recommendations Job
	storeRecommendations := scheduler.NewStoreRecommendationsJob(container.RecommendationRepo, container.EventManager, "")
	storeRecommendations.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeStoreRecommendations, queue.JobToHandler(storeRecommendations))
	instances.StoreRecommendations = storeRecommendations

	// ==========================================
	// COMPOSITE PLANNER BATCH JOB (orchestrates individual planning jobs)
	// ==========================================
	plannerBatch := scheduler.NewPlannerBatchJob(scheduler.PlannerBatchConfig{
		Log:                        log,
		EventManager:               container.EventManager,
		RecommendationRepo:         container.RecommendationRepo,
		PlannerRepo:                container.PlannerRepo,
		GeneratePortfolioHashJob:   generatePortfolioHash,
		GetOptimizerWeightsJob:     instances.GetOptimizerWeights,
		BuildOpportunityContextJob: buildOpportunityContext,
		CreateTradePlanJob:         createTradePlan,
		StoreRecommendationsJob:    storeRecommendations,
	})
	container.JobRegistry.Register(queue.JobTypePlannerBatch, queue.JobToHandler(plannerBatch))
	instances.PlannerBatch = plannerBatch

	// ==========================================
	// INDIVIDUAL DIVIDEND JOBS
	// ==========================================

	// Get Unreinvested Dividends Job
	dividendRepoAdapter := scheduler.NewDividendRepositoryAdapter(container.DividendRepo)
	getUnreinvestedDividends := scheduler.NewGetUnreinvestedDividendsJob(dividendRepoAdapter, 0.0)
	getUnreinvestedDividends.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeGetUnreinvestedDividends, queue.JobToHandler(getUnreinvestedDividends))
	instances.GetUnreinvestedDividends = getUnreinvestedDividends

	// Group Dividends By Symbol Job
	groupDividendsBySymbol := scheduler.NewGroupDividendsBySymbolJob()
	groupDividendsBySymbol.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeGroupDividendsBySymbol, queue.JobToHandler(groupDividendsBySymbol))
	instances.GroupDividendsBySymbol = groupDividendsBySymbol

	// Check Dividend Yields Job
	securityRepoForDividendsAdapter := scheduler.NewSecurityRepositoryForDividendsAdapter(container.SecurityRepo)
	yahooClientForDividendsAdapter := scheduler.NewYahooClientForDividendsAdapter(container.YahooClient)
	checkDividendYields := scheduler.NewCheckDividendYieldsJob(securityRepoForDividendsAdapter, yahooClientForDividendsAdapter)
	checkDividendYields.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeCheckDividendYields, queue.JobToHandler(checkDividendYields))
	instances.CheckDividendYields = checkDividendYields

	// Create Dividend Recommendations Job
	minTradeSize := 200.0 // Calculate from transaction costs
	createDividendRecommendations := scheduler.NewCreateDividendRecommendationsJob(
		securityRepoForDividendsAdapter,
		yahooClientForDividendsAdapter,
		minTradeSize,
	)
	createDividendRecommendations.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeCreateDividendRecommendations, queue.JobToHandler(createDividendRecommendations))
	instances.CreateDividendRecommendations = createDividendRecommendations

	// Set Pending Bonuses Job
	setPendingBonuses := scheduler.NewSetPendingBonusesJob(dividendRepoAdapter)
	setPendingBonuses.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeSetPendingBonuses, queue.JobToHandler(setPendingBonuses))
	instances.SetPendingBonuses = setPendingBonuses

	// Execute Dividend Trades Job
	tradeExecutionServiceAdapter := scheduler.NewTradeExecutionServiceAdapter(container.TradeExecutionService)
	executeDividendTrades := scheduler.NewExecuteDividendTradesJob(dividendRepoAdapter, tradeExecutionServiceAdapter)
	executeDividendTrades.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeExecuteDividendTrades, queue.JobToHandler(executeDividendTrades))
	instances.ExecuteDividendTrades = executeDividendTrades

	// ==========================================
	// COMPOSITE DIVIDEND REINVESTMENT JOB (orchestrates individual dividend jobs)
	// ==========================================
	dividendReinvest := scheduler.NewDividendReinvestmentJob(scheduler.DividendReinvestmentConfig{
		Log:                              log,
		GetUnreinvestedDividendsJob:      getUnreinvestedDividends,
		GroupDividendsBySymbolJob:        groupDividendsBySymbol,
		CheckDividendYieldsJob:           checkDividendYields,
		CreateDividendRecommendationsJob: createDividendRecommendations,
		SetPendingBonusesJob:             setPendingBonuses,
		ExecuteDividendTradesJob:         executeDividendTrades,
	})
	container.JobRegistry.Register(queue.JobTypeDividendReinvest, queue.JobToHandler(dividendReinvest))
	instances.DividendReinvest = dividendReinvest

	// ==========================================
	// INDIVIDUAL HEALTH CHECK JOBS
	// ==========================================

	// Check Core Databases Job
	checkCoreDatabases := scheduler.NewCheckCoreDatabasesJob(
		container.UniverseDB,
		container.ConfigDB,
		container.LedgerDB,
		container.PortfolioDB,
	)
	checkCoreDatabases.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeCheckCoreDatabases, queue.JobToHandler(checkCoreDatabases))
	instances.CheckCoreDatabases = checkCoreDatabases

	// Check History Databases Job
	checkHistoryDatabases := scheduler.NewCheckHistoryDatabasesJob(container.HistoryDB)
	checkHistoryDatabases.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeCheckHistoryDatabases, queue.JobToHandler(checkHistoryDatabases))
	instances.CheckHistoryDatabases = checkHistoryDatabases

	// Check WAL Checkpoints Job
	checkWALCheckpoints := scheduler.NewCheckWALCheckpointsJob(
		container.UniverseDB,
		container.ConfigDB,
		container.LedgerDB,
		container.PortfolioDB,
		container.HistoryDB,
		container.CacheDB,
		container.ClientDataDB,
	)
	checkWALCheckpoints.SetLogger(log)
	container.JobRegistry.Register(queue.JobTypeCheckWALCheckpoints, queue.JobToHandler(checkWALCheckpoints))
	instances.CheckWALCheckpoints = checkWALCheckpoints

	// ==========================================
	// COMPOSITE HEALTH CHECK JOB (orchestrates individual health check jobs)
	// ==========================================
	healthCheck := scheduler.NewHealthCheckJob(scheduler.HealthCheckConfig{
		Log:                      log,
		CheckCoreDatabasesJob:    checkCoreDatabases,
		CheckHistoryDatabasesJob: checkHistoryDatabases,
		CheckWALCheckpointsJob:   checkWALCheckpoints,
	})
	container.JobRegistry.Register(queue.JobTypeHealthCheck, queue.JobToHandler(healthCheck))
	instances.HealthCheck = healthCheck

	// ==========================================
	// DEPLOYMENT JOB (optional - only if deployment manager is provided)
	// ==========================================
	if deploymentManager != nil {
		// Type assert to deployment.Manager
		if mgr, ok := deploymentManager.(*deployment.Manager); ok {
			// Get deployment interval from settings (default: 5 minutes)
			deploymentIntervalMinutes, err := container.SettingsRepo.GetFloat("job_auto_deploy_minutes", 5.0)
			if err != nil {
				log.Warn().Err(err).Msg("Failed to get deployment interval from settings, using default 5 minutes")
				deploymentIntervalMinutes = 5.0
			}

			deploymentInterval := time.Duration(deploymentIntervalMinutes) * time.Minute
			deploymentJob := scheduler.NewDeploymentJob(mgr, deploymentInterval, true, log)
			container.JobRegistry.Register(queue.JobTypeDeployment, queue.JobToHandler(deploymentJob))
			instances.Deployment = deploymentJob

			// Configure scheduler with deployment interval
			container.TimeScheduler.SetDeploymentInterval(deploymentInterval)

			log.Info().
				Float64("interval_minutes", deploymentIntervalMinutes).
				Msg("Deployment job registered (auto-deploy enabled)")
		} else {
			log.Warn().Msg("Deployment manager provided but type assertion failed, skipping deployment job registration")
		}
	} else {
		log.Info().Msg("Deployment manager not provided, skipping deployment job registration")
	}

	// ==========================================
	// Configure Worker Pool
	// ==========================================
	// Set event manager for job status broadcasting
	container.WorkerPool.SetEventManager(container.EventManager)

	// ==========================================
	// Start Queue System
	// ==========================================
	container.WorkerPool.Start()
	container.TimeScheduler.Start()

	jobCount := 38
	if deploymentManager != nil {
		jobCount = 38 // Include deployment job
	}
	log.Info().Int("jobs", jobCount).Msg("Jobs registered with queue system")

	return instances, nil
}
