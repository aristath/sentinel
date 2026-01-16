// Package di provides dependency injection for the work processor.
package di

import (
	"context"
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/database"
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/events"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	planninghash "github.com/aristath/sentinel/internal/modules/planning/hash"
	"github.com/aristath/sentinel/internal/modules/trading"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/internal/scheduler"
	"github.com/aristath/sentinel/internal/work"
	"github.com/rs/zerolog"
)

// WorkComponents holds all work processor components
type WorkComponents struct {
	Registry   *work.Registry
	Completion *work.CompletionTracker
	Market     *work.MarketTimingChecker
	Processor  *work.Processor
	Handlers   *work.Handlers
}

// marketHoursAdapter adapts MarketHoursService to work.MarketChecker interface
type marketHoursAdapter struct {
	container *Container
}

func (a *marketHoursAdapter) IsAnyMarketOpen() bool {
	if a.container.MarketHoursService == nil {
		return false
	}
	openMarkets := a.container.MarketHoursService.GetOpenMarkets(time.Now())
	return len(openMarkets) > 0
}

func (a *marketHoursAdapter) IsSecurityMarketOpen(isin string) bool {
	if a.container.MarketHoursService == nil {
		return false
	}
	// Get security to determine market
	sec, err := a.container.SecurityRepo.GetByISIN(isin)
	if err != nil || sec == nil {
		return false
	}
	return a.container.MarketHoursService.IsMarketOpen(sec.FullExchangeName, time.Now())
}

func (a *marketHoursAdapter) AreAllMarketsClosed() bool {
	if a.container.MarketHoursService == nil {
		return true
	}
	openMarkets := a.container.MarketHoursService.GetOpenMarkets(time.Now())
	return len(openMarkets) == 0
}

// eventEmitterAdapter adapts events.Manager to work.EventEmitter interface
type eventEmitterAdapter struct {
	manager *events.Manager
}

func (a *eventEmitterAdapter) Emit(event string, data any) {
	if a.manager == nil {
		return
	}
	// Convert string event name to events.EventType
	eventType := events.EventType(event)
	// Convert data to map[string]interface{} for EventManager
	details, ok := data.(map[string]interface{})
	if !ok && data != nil {
		// Wrap non-map data in a map
		details = map[string]interface{}{"data": data}
	}
	a.manager.Emit(eventType, "", details)
}

// InitializeWork creates and wires up all work processor components
func InitializeWork(container *Container, log zerolog.Logger) (*WorkComponents, error) {
	// Create core components
	registry := work.NewRegistry()
	completion := work.NewCompletionTracker()
	market := work.NewMarketTimingChecker(&marketHoursAdapter{container: container})
	processor := work.NewProcessor(registry, completion, market)

	// Wire event emitter for progress reporting
	if container.EventManager != nil {
		processor.SetEventEmitter(&eventEmitterAdapter{manager: container.EventManager})
	}

	handlers := work.NewHandlers(processor, registry)

	// Create work cache
	workCache := newWorkCache()

	// Register planner work types
	registerPlannerWork(registry, container, workCache, log)

	// Register sync work types
	registerSyncWork(registry, container, log)

	// Register maintenance work types
	registerMaintenanceWork(registry, container, log)

	// Register trading work types
	registerTradingWork(registry, container, log)

	// Register security work types
	registerSecurityWork(registry, container, log)

	// Register dividend work types
	registerDividendWork(registry, container, workCache, log)

	// Register analysis work types
	registerAnalysisWork(registry, container, log)

	// Register deployment work types
	registerDeploymentWork(registry, container, log)

	// Register triggers
	registerTriggers(container, processor, completion, workCache)

	log.Info().Int("work_types", registry.Count()).Msg("Work processor initialized")

	return &WorkComponents{
		Registry:   registry,
		Completion: completion,
		Market:     market,
		Processor:  processor,
		Handlers:   handlers,
	}, nil
}

// workCache is an in-memory cache for work types
type workCache struct {
	data map[string]interface{}
}

func newWorkCache() *workCache {
	return &workCache{
		data: make(map[string]interface{}),
	}
}

func (c *workCache) Has(key string) bool {
	_, exists := c.data[key]
	return exists
}

func (c *workCache) Get(key string) interface{} {
	return c.data[key]
}

func (c *workCache) Set(key string, value interface{}) {
	c.data[key] = value
}

func (c *workCache) Delete(key string) {
	delete(c.data, key)
}

func (c *workCache) DeletePrefix(prefix string) {
	for key := range c.data {
		if len(key) >= len(prefix) && key[:len(prefix)] == prefix {
			delete(c.data, key)
		}
	}
}

// workBrokerPriceAdapter adapts domain.BrokerClient to scheduler.BrokerClientForPrices interface
type workBrokerPriceAdapter struct {
	client domain.BrokerClient
}

func (a *workBrokerPriceAdapter) GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error) {
	if a.client == nil {
		return nil, fmt.Errorf("broker client not available")
	}

	// Extract symbols from map
	symbols := make([]string, 0, len(symbolMap))
	for symbol := range symbolMap {
		symbols = append(symbols, symbol)
	}

	// Get quotes from broker
	quotes, err := a.client.GetQuotes(symbols)
	if err != nil {
		return nil, fmt.Errorf("failed to get broker quotes: %w", err)
	}

	// Convert to price map
	prices := make(map[string]*float64)
	for symbol, quote := range quotes {
		if quote != nil && quote.Price > 0 {
			price := quote.Price
			prices[symbol] = &price
		}
	}

	return prices, nil
}

// Planner adapters - wrap existing planner jobs
type plannerOptimizerAdapter struct {
	container *Container
	cache     *workCache
	log       zerolog.Logger
}

func (a *plannerOptimizerAdapter) CalculateWeights() (map[string]float64, error) {
	// Create adapters for the optimizer weights job
	positionAdapter := scheduler.NewPositionRepositoryAdapter(a.container.PositionRepo)
	securityAdapter := scheduler.NewSecurityRepositoryAdapter(a.container.SecurityRepo)
	allocAdapter := scheduler.NewAllocationRepositoryAdapter(a.container.AllocRepo)
	priceAdapter := scheduler.NewPriceClientAdapter(&workBrokerPriceAdapter{client: a.container.BrokerClient})
	optimizerAdapter := scheduler.NewOptimizerServiceAdapter(a.container.OptimizerService)
	priceConversionAdapter := scheduler.NewPriceConversionServiceAdapter(a.container.PriceConversionService)
	plannerConfigAdapter := scheduler.NewPlannerConfigRepositoryAdapter(a.container.PlannerConfigRepo)
	clientDataAdapter := scheduler.NewClientDataRepositoryAdapter(a.container.ClientDataRepo)
	marketHoursAdapter := scheduler.NewMarketHoursServiceAdapter(a.container.MarketHoursService)

	// Create and run the optimizer weights job
	job := scheduler.NewGetOptimizerWeightsJob(
		positionAdapter,
		securityAdapter,
		allocAdapter,
		a.container.CashManager,
		priceAdapter,
		optimizerAdapter,
		priceConversionAdapter,
		plannerConfigAdapter,
		clientDataAdapter,
		marketHoursAdapter,
	)
	job.SetLogger(a.log)

	if err := job.Run(); err != nil {
		return nil, err
	}

	return job.GetTargetWeights(), nil
}

type plannerContextBuilderAdapter struct {
	container *Container
}

func (a *plannerContextBuilderAdapter) Build() (interface{}, error) {
	return a.container.OpportunityContextBuilder.Build()
}

func (a *plannerContextBuilderAdapter) SetWeights(weights map[string]float64) {
	// Weights are set via the optimizer result
}

type plannerServiceAdapter struct {
	container *Container
	cache     *workCache
}

func (a *plannerServiceAdapter) CreatePlan(ctx interface{}) (interface{}, error) {
	// Get opportunity context from cache
	opportunityContext := a.cache.Get("opportunity_context")
	if opportunityContext == nil {
		return nil, nil
	}

	// Get planner configuration
	config, err := a.container.PlannerConfigRepo.GetDefaultConfig()
	if err != nil {
		return nil, err
	}

	// Use the existing planner service with type assertion
	ctxTyped, ok := opportunityContext.(*planningdomain.OpportunityContext)
	if !ok {
		return nil, nil
	}

	return a.container.PlannerService.CreatePlan(ctxTyped, config)
}

type plannerRecommendationRepoAdapter struct {
	container *Container
	log       zerolog.Logger
}

func (a *plannerRecommendationRepoAdapter) Store(recommendations interface{}) error {
	// Type assert the plan to HolisticPlan
	plan, ok := recommendations.(*planningdomain.HolisticPlan)
	if !ok {
		return fmt.Errorf("invalid plan type: expected *HolisticPlan")
	}

	// Generate portfolio hash for tracking using the hash package
	portfolioHash := a.generatePortfolioHash()

	// Store the plan using the recommendation repository
	err := a.container.RecommendationRepo.StorePlan(plan, portfolioHash)
	if err != nil {
		return fmt.Errorf("failed to store plan: %w", err)
	}

	a.log.Info().
		Str("portfolio_hash", portfolioHash).
		Int("steps", len(plan.Steps)).
		Msg("Successfully stored recommendations")

	return nil
}

func (a *plannerRecommendationRepoAdapter) generatePortfolioHash() string {
	// Get positions
	positions, err := a.container.PositionRepo.GetAll()
	if err != nil {
		a.log.Warn().Err(err).Msg("Failed to get positions for hash")
		return ""
	}

	// Get securities
	securities, err := a.container.SecurityRepo.GetAllActive()
	if err != nil {
		a.log.Warn().Err(err).Msg("Failed to get securities for hash")
		return ""
	}

	// Get cash balances
	cashBalances := make(map[string]float64)
	if a.container.CashManager != nil {
		balances, err := a.container.CashManager.GetAllCashBalances()
		if err != nil {
			a.log.Warn().Err(err).Msg("Failed to get cash balances for hash")
		} else {
			cashBalances = balances
		}
	}

	// Convert to hash format
	hashPositions := make([]planninghash.Position, 0, len(positions))
	for _, pos := range positions {
		hashPositions = append(hashPositions, planninghash.Position{
			Symbol:   pos.Symbol,
			Quantity: int(pos.Quantity),
		})
	}

	hashSecurities := make([]*universe.Security, 0, len(securities))
	for i := range securities {
		hashSecurities = append(hashSecurities, &securities[i])
	}

	pendingOrders := []planninghash.PendingOrder{}

	return planninghash.GeneratePortfolioHash(
		hashPositions,
		hashSecurities,
		cashBalances,
		pendingOrders,
	)
}

type plannerEventManagerAdapter struct {
	container *Container
}

func (a *plannerEventManagerAdapter) Emit(event string, data interface{}) {
	a.container.EventManager.Emit(events.JobProgress, event, nil)
}

func registerPlannerWork(registry *work.Registry, container *Container, cache *workCache, log zerolog.Logger) {
	deps := &work.PlannerDeps{
		Cache:              cache,
		OptimizerService:   &plannerOptimizerAdapter{container: container, cache: cache, log: log},
		ContextBuilder:     &plannerContextBuilderAdapter{container: container},
		PlannerService:     &plannerServiceAdapter{container: container, cache: cache},
		RecommendationRepo: &plannerRecommendationRepoAdapter{container: container, log: log},
		EventManager:       &plannerEventManagerAdapter{container: container},
	}

	work.RegisterPlannerWorkTypes(registry, deps)
	log.Debug().Msg("Planner work types registered")
}

// Sync adapters
type syncPortfolioAdapter struct {
	container *Container
}

func (a *syncPortfolioAdapter) SyncPortfolio() error {
	return a.container.PortfolioService.SyncFromTradernet()
}

type syncTradesAdapter struct {
	container *Container
}

func (a *syncTradesAdapter) SyncTrades() error {
	return a.container.TradingService.SyncFromTradernet()
}

type syncCashFlowsAdapter struct {
	container *Container
}

func (a *syncCashFlowsAdapter) SyncCashFlows() error {
	return a.container.CashFlowsService.SyncFromTradernet()
}

type syncPricesAdapter struct {
	container *Container
}

func (a *syncPricesAdapter) SyncPrices() error {
	return a.container.UniverseService.SyncPrices()
}

type syncExchangeRatesAdapter struct {
	container *Container
}

func (a *syncExchangeRatesAdapter) SyncExchangeRates() error {
	return a.container.ExchangeRateCacheService.SyncRates()
}

type syncDisplayAdapter struct {
	container *Container
}

func (a *syncDisplayAdapter) UpdateDisplay() error {
	if a.container.UpdateDisplayTicker != nil {
		return a.container.UpdateDisplayTicker()
	}
	return nil
}

type syncNegativeBalanceAdapter struct {
	container *Container
}

func (a *syncNegativeBalanceAdapter) CheckNegativeBalances() error {
	if a.container.EmergencyRebalance != nil {
		return a.container.EmergencyRebalance()
	}
	return nil
}

type syncEventManagerAdapter struct {
	container *Container
}

func (a *syncEventManagerAdapter) Emit(event string, data any) {
	a.container.EventManager.Emit(events.JobProgress, event, nil)
}

func registerSyncWork(registry *work.Registry, container *Container, log zerolog.Logger) {
	deps := &work.SyncDeps{
		PortfolioService:       &syncPortfolioAdapter{container: container},
		TradesService:          &syncTradesAdapter{container: container},
		CashFlowsService:       &syncCashFlowsAdapter{container: container},
		PricesService:          &syncPricesAdapter{container: container},
		ExchangeRateService:    &syncExchangeRatesAdapter{container: container},
		DisplayService:         &syncDisplayAdapter{container: container},
		NegativeBalanceService: &syncNegativeBalanceAdapter{container: container},
		EventManager:           &syncEventManagerAdapter{container: container},
	}

	work.RegisterSyncWorkTypes(registry, deps)
	log.Debug().Msg("Sync work types registered")
}

// Maintenance adapters
type maintenanceBackupAdapter struct {
	container *Container
}

func (a *maintenanceBackupAdapter) RunDailyBackup() error {
	return a.container.BackupService.DailyBackup()
}

func (a *maintenanceBackupAdapter) BackedUpToday() bool {
	// Check if the last backup was today
	// The BackupService tracks this internally
	return false // Always run to be safe
}

type maintenanceR2BackupAdapter struct {
	container *Container
}

func (a *maintenanceR2BackupAdapter) UploadBackup() error {
	if a.container.R2BackupService != nil {
		return a.container.R2BackupService.CreateAndUploadBackup(context.Background())
	}
	return nil
}

func (a *maintenanceR2BackupAdapter) RotateBackups() error {
	if a.container.R2BackupService != nil {
		// Use default retention of 90 days
		return a.container.R2BackupService.RotateOldBackups(context.Background(), 90)
	}
	return nil
}

type maintenanceVacuumAdapter struct {
	container *Container
	log       zerolog.Logger
}

func (a *maintenanceVacuumAdapter) VacuumDatabases() error {
	// Vacuum ephemeral databases: cache, history, portfolio (following WeeklyMaintenanceJob pattern)
	// Ledger is append-only and should not be vacuumed
	dbs := []struct {
		name string
		db   *database.DB
	}{
		{"cache", a.container.CacheDB},
		{"history", a.container.HistoryDB},
		{"portfolio", a.container.PortfolioDB},
	}

	for _, dbInfo := range dbs {
		if dbInfo.db == nil {
			continue
		}

		// Get size before vacuum
		var pageCount, pageSize int
		dbInfo.db.Conn().QueryRow("PRAGMA page_count").Scan(&pageCount)
		dbInfo.db.Conn().QueryRow("PRAGMA page_size").Scan(&pageSize)
		sizeBefore := float64(pageCount*pageSize) / 1024 / 1024

		// Run VACUUM
		_, err := dbInfo.db.Conn().Exec("VACUUM")
		if err != nil {
			a.log.Error().Err(err).Str("database", dbInfo.name).Msg("VACUUM failed")
			continue // Don't fail the entire operation
		}

		// Get size after vacuum
		dbInfo.db.Conn().QueryRow("PRAGMA page_count").Scan(&pageCount)
		sizeAfter := float64(pageCount*pageSize) / 1024 / 1024
		spaceReclaimed := sizeBefore - sizeAfter

		a.log.Info().
			Str("database", dbInfo.name).
			Float64("size_before_mb", sizeBefore).
			Float64("size_after_mb", sizeAfter).
			Float64("space_reclaimed_mb", spaceReclaimed).
			Msg("VACUUM completed")
	}

	return nil
}

type maintenanceHealthAdapter struct {
	container *Container
}

func (a *maintenanceHealthAdapter) RunHealthChecks() error {
	// Run health checks using CheckAndRecover
	for _, hs := range a.container.HealthServices {
		if err := hs.CheckAndRecover(); err != nil {
			return err
		}
	}
	return nil
}

type maintenanceCleanupAdapter struct {
	container *Container
	log       zerolog.Logger
}

func (a *maintenanceCleanupAdapter) CleanupHistory() error {
	// History database cleanup: run WAL checkpoint to prevent bloat
	// Full history deletion is not implemented as we want to preserve historical data
	if a.container.HistoryDB != nil {
		_, err := a.container.HistoryDB.Conn().Exec("PRAGMA wal_checkpoint(TRUNCATE)")
		if err != nil {
			a.log.Warn().Err(err).Msg("History WAL checkpoint failed")
		} else {
			a.log.Debug().Msg("History WAL checkpoint completed")
		}
	}
	return nil
}

func (a *maintenanceCleanupAdapter) CleanupCache() error {
	// Cache database cleanup: run WAL checkpoint to prevent bloat
	if a.container.CacheDB != nil {
		_, err := a.container.CacheDB.Conn().Exec("PRAGMA wal_checkpoint(TRUNCATE)")
		if err != nil {
			a.log.Warn().Err(err).Msg("Cache WAL checkpoint failed")
		} else {
			a.log.Debug().Msg("Cache WAL checkpoint completed")
		}
	}
	return nil
}

func (a *maintenanceCleanupAdapter) CleanupRecommendations() error {
	// Delete recommendations older than 7 days
	_, err := a.container.RecommendationRepo.DeleteOlderThan(7 * 24 * time.Hour)
	return err
}

func (a *maintenanceCleanupAdapter) CleanupClientData() error {
	_, err := a.container.ClientDataRepo.DeleteAllExpired()
	return err
}

func registerMaintenanceWork(registry *work.Registry, container *Container, log zerolog.Logger) {
	deps := &work.MaintenanceDeps{
		BackupService:      &maintenanceBackupAdapter{container: container},
		R2BackupService:    &maintenanceR2BackupAdapter{container: container},
		VacuumService:      &maintenanceVacuumAdapter{container: container, log: log},
		HealthCheckService: &maintenanceHealthAdapter{container: container},
		CleanupService:     &maintenanceCleanupAdapter{container: container, log: log},
	}

	work.RegisterMaintenanceWorkTypes(registry, deps)
	log.Debug().Msg("Maintenance work types registered")
}

// Trading adapters
type tradingExecutionAdapter struct {
	container *Container
}

func (a *tradingExecutionAdapter) ExecutePendingTrades() error {
	// Get pending recommendations (limit to 1 for throttling)
	recommendations, err := a.container.RecommendationRepo.GetPendingRecommendations(1)
	if err != nil {
		return err
	}

	if len(recommendations) == 0 {
		return nil
	}

	rec := recommendations[0]

	// Execute the trade via trading service
	tradeRequest := trading.TradeRequest{
		Symbol:   rec.Symbol,
		Side:     rec.Side,
		Quantity: int(rec.Quantity),
		Reason:   rec.Reason,
	}

	result, err := a.container.TradingService.ExecuteTrade(tradeRequest)
	if err != nil {
		// Record failed attempt
		_ = a.container.RecommendationRepo.RecordFailedAttempt(rec.UUID, err.Error())
		return err
	}

	if !result.Success {
		_ = a.container.RecommendationRepo.RecordFailedAttempt(rec.UUID, result.Reason)
		return nil
	}

	// Mark recommendation as executed
	return a.container.RecommendationRepo.MarkExecuted(rec.UUID)
}

func (a *tradingExecutionAdapter) HasPendingTrades() bool {
	buyCount, sellCount, _ := a.container.RecommendationRepo.CountPendingBySide()
	return buyCount > 0 || sellCount > 0
}

type tradingRetryAdapter struct {
	container *Container
}

func (a *tradingRetryAdapter) RetryFailedTrades() error {
	// Get pending retries from the trade repository
	retries, err := a.container.TradeRepo.GetPendingRetries()
	if err != nil {
		return err
	}

	for _, retry := range retries {
		// Try to execute the retry
		tradeRequest := trading.TradeRequest{
			Symbol:   retry.Symbol,
			Side:     retry.Side,
			Quantity: int(retry.Quantity), // Convert float64 to int
			Reason:   retry.Reason,
		}

		result, err := a.container.TradingService.ExecuteTrade(tradeRequest)
		if err != nil {
			// Increment retry attempt
			_ = a.container.TradeRepo.IncrementRetryAttempt(retry.ID)
			continue
		}

		if result.Success {
			// Mark as completed
			_ = a.container.TradeRepo.UpdateRetryStatus(retry.ID, "completed")
		} else {
			// Increment retry attempt
			_ = a.container.TradeRepo.IncrementRetryAttempt(retry.ID)
		}
	}

	return nil
}

func (a *tradingRetryAdapter) HasFailedTrades() bool {
	retries, err := a.container.TradeRepo.GetPendingRetries()
	if err != nil {
		return false
	}
	return len(retries) > 0
}

func registerTradingWork(registry *work.Registry, container *Container, log zerolog.Logger) {
	deps := &work.TradingDeps{
		ExecutionService: &tradingExecutionAdapter{container: container},
		RetryService:     &tradingRetryAdapter{container: container},
	}

	work.RegisterTradingWorkTypes(registry, deps)
	log.Debug().Msg("Trading work types registered")
}

// Register event triggers
func registerTriggers(container *Container, processor *work.Processor, completion *work.CompletionTracker, cache *workCache) {
	bus := container.EventBus

	// StateChanged -> Clear planner cache and trigger
	bus.Subscribe(events.StateChanged, func(e *events.Event) {
		cache.DeletePrefix("planner:")
		cache.DeletePrefix("optimizer_weights")
		cache.DeletePrefix("opportunity_context")
		cache.DeletePrefix("trade_plan")
		completion.ClearByPrefix("planner:")
		processor.Trigger()
	})

	// RecommendationsReady -> trigger trading
	bus.Subscribe(events.RecommendationsReady, func(e *events.Event) {
		processor.Trigger()
	})

	// MarketsStatusChanged -> Trigger to check market-timed work
	bus.Subscribe(events.MarketsStatusChanged, func(e *events.Event) {
		processor.Trigger()
	})

	// DividendDetected -> Clear dividend cache and trigger
	bus.Subscribe(events.DividendDetected, func(e *events.Event) {
		cache.DeletePrefix("dividend:")
		completion.ClearByPrefix("dividend:")
		processor.Trigger()
	})
}

// Security work type adapters
type securityHistorySyncAdapter struct {
	container *Container
}

func (a *securityHistorySyncAdapter) SyncSecurityHistory(isin string) error {
	// Get security to get the symbol
	sec, err := a.container.SecurityRepo.GetByISIN(isin)
	if err != nil || sec == nil {
		return err
	}
	return a.container.HistoricalSyncService.SyncHistoricalPrices(sec.Symbol)
}

func (a *securityHistorySyncAdapter) GetStaleSecurities() []string {
	// Get ISINs that need historical data sync
	// For now, return all active securities - the work processor handles staleness via completion tracker
	securities, err := a.container.SecurityRepo.GetAllActive()
	if err != nil {
		return nil
	}
	var isins []string
	for _, sec := range securities {
		isins = append(isins, sec.ISIN)
	}
	return isins
}

type securityTechnicalAdapter struct {
	container *Container
}

func (a *securityTechnicalAdapter) CalculateTechnicals(isin string) error {
	// Technical calculations are done during historical sync
	return nil
}

func (a *securityTechnicalAdapter) GetSecuritiesNeedingTechnicals() []string {
	// Already handled by historical sync
	return nil
}

type securityFormulaAdapter struct {
	container *Container
}

func (a *securityFormulaAdapter) RunDiscovery(isin string) error {
	// Formula discovery - placeholder for now
	return nil
}

func (a *securityFormulaAdapter) GetSecuritiesNeedingDiscovery() []string {
	return nil
}

type securityTagAdapter struct {
	container *Container
}

func (a *securityTagAdapter) UpdateTags(isin string) error {
	// Tag assignment requires full AssignTagsInput - for now this is a no-op
	// Tags are assigned as part of the scoring workflow
	return nil
}

func (a *securityTagAdapter) GetSecuritiesNeedingTagUpdate() []string {
	// Tag updates happen as part of scoring workflow
	// Return empty list for now
	return nil
}

type metadataSyncAdapter struct {
	service *universe.MetadataSyncService
}

func (a *metadataSyncAdapter) SyncMetadata(isin string) error {
	return a.service.SyncMetadata(isin)
}

func (a *metadataSyncAdapter) GetAllActiveISINs() []string {
	return a.service.GetAllActiveISINs()
}

func registerSecurityWork(registry *work.Registry, container *Container, log zerolog.Logger) {
	// Create metadata sync service
	metadataSyncService := universe.NewMetadataSyncService(
		container.SecurityRepo,
		container.BrokerClient,
		log,
	)

	deps := &work.SecurityDeps{
		HistorySyncService:  &securityHistorySyncAdapter{container: container},
		TechnicalService:    &securityTechnicalAdapter{container: container},
		FormulaService:      &securityFormulaAdapter{container: container},
		TagService:          &securityTagAdapter{container: container},
		MetadataSyncService: &metadataSyncAdapter{service: metadataSyncService},
	}

	work.RegisterSecurityWorkTypes(registry, deps)
	log.Debug().Msg("Security work types registered")
}

// Dividend work type adapters
type dividendDetectionAdapter struct {
	container *Container
}

func (a *dividendDetectionAdapter) DetectUnreinvestedDividends() (any, error) {
	// Use the dividend repository to get unreinvested dividends (min 0 EUR)
	return a.container.DividendRepo.GetUnreinvestedDividends(0)
}

func (a *dividendDetectionAdapter) HasPendingDividends() bool {
	dividends, err := a.container.DividendRepo.GetUnreinvestedDividends(0)
	if err != nil {
		return false
	}
	return len(dividends) > 0
}

type dividendAnalysisAdapter struct {
	container *Container
}

func (a *dividendAnalysisAdapter) AnalyzeDividends(dividends any) (any, error) {
	// Analyze dividends - the actual analysis happens in the detection step
	return dividends, nil
}

type dividendRecommendationAdapter struct {
	container *Container
}

func (a *dividendRecommendationAdapter) CreateRecommendations(analysis any) (any, error) {
	// Create dividend reinvestment recommendations
	return analysis, nil
}

type dividendExecutionAdapter struct {
	container *Container
}

func (a *dividendExecutionAdapter) ExecuteTrades(recommendations any) error {
	// Execute dividend reinvestment trades
	return nil
}

func registerDividendWork(registry *work.Registry, container *Container, cache *workCache, log zerolog.Logger) {
	deps := &work.DividendDeps{
		DetectionService:      &dividendDetectionAdapter{container: container},
		AnalysisService:       &dividendAnalysisAdapter{container: container},
		RecommendationService: &dividendRecommendationAdapter{container: container},
		ExecutionService:      &dividendExecutionAdapter{container: container},
		Cache:                 cache,
	}

	work.RegisterDividendWorkTypes(registry, deps)
	log.Debug().Msg("Dividend work types registered")
}

// Analysis work type adapters
type marketRegimeAdapter struct {
	container *Container
}

func (a *marketRegimeAdapter) AnalyzeMarketRegime() error {
	if a.container.RegimeDetector == nil || a.container.RegimePersistence == nil {
		return nil
	}
	// Calculate and persist regime scores for all regions
	scores, err := a.container.RegimeDetector.CalculateAllRegionScores(90) // 90-day window
	if err != nil {
		return err
	}
	// Record each region's score
	for region, score := range scores {
		regimeScore := a.container.RegimeDetector.CalculateRegimeScore(score, 0, 0) // Basic score
		if err := a.container.RegimePersistence.RecordRegimeScoreForRegion(region, regimeScore); err != nil {
			return err
		}
	}
	return nil
}

func (a *marketRegimeAdapter) NeedsAnalysis() bool {
	// Check if regime detector is available
	return a.container.RegimeDetector != nil && a.container.RegimePersistence != nil
}

func registerAnalysisWork(registry *work.Registry, container *Container, log zerolog.Logger) {
	deps := &work.AnalysisDeps{
		MarketRegimeService: &marketRegimeAdapter{container: container},
	}

	work.RegisterAnalysisWorkTypes(registry, deps)
	log.Debug().Msg("Analysis work types registered")
}

// Deployment work type adapters
type deploymentCheckAdapter struct {
	container *Container
}

func (a *deploymentCheckAdapter) CheckForDeployment() error {
	// Deployment is handled externally - this is a no-op placeholder
	return nil
}

func (a *deploymentCheckAdapter) GetCheckInterval() time.Duration {
	// Default to 1 hour
	return time.Hour
}

func registerDeploymentWork(registry *work.Registry, container *Container, log zerolog.Logger) {
	deps := &work.DeploymentDeps{
		DeploymentService: &deploymentCheckAdapter{container: container},
	}

	work.RegisterDeploymentWorkTypes(registry, deps)
	log.Debug().Msg("Deployment work types registered")
}
