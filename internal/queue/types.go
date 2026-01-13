package queue

import "time"

// JobType represents the type of job
type JobType string

const (
	// Original composite jobs (kept for backward compatibility)
	JobTypePlannerBatch       JobType = "planner_batch"
	JobTypeEventBasedTrading  JobType = "event_based_trading"
	JobTypeTagUpdate          JobType = "tag_update"
	JobTypeSyncCycle          JobType = "sync_cycle"
	JobTypeDividendReinvest   JobType = "dividend_reinvestment"
	JobTypeHealthCheck        JobType = "health_check"
	JobTypeHourlyBackup       JobType = "hourly_backup"
	JobTypeDailyBackup        JobType = "daily_backup"
	JobTypeDailyMaintenance   JobType = "daily_maintenance"
	JobTypeWeeklyBackup       JobType = "weekly_backup"
	JobTypeWeeklyMaintenance  JobType = "weekly_maintenance"
	JobTypeMonthlyBackup      JobType = "monthly_backup"
	JobTypeMonthlyMaintenance JobType = "monthly_maintenance"
	JobTypeFormulaDiscovery   JobType = "formula_discovery"
	JobTypeAdaptiveMarket     JobType = "adaptive_market_check"
	JobTypeHistoryCleanup     JobType = "history_cleanup"
	JobTypeRecommendationGC   JobType = "recommendation_gc"
	JobTypeClientDataCleanup  JobType = "client_data_cleanup"
	JobTypeDeployment         JobType = "deployment"
	JobTypeR2Backup           JobType = "r2_backup"
	JobTypeR2BackupRotation   JobType = "r2_backup_rotation"

	// Sync jobs - individual responsibilities split from sync_cycle
	JobTypeSyncTrades            JobType = "sync_trades"
	JobTypeSyncCashFlows         JobType = "sync_cash_flows"
	JobTypeSyncPortfolio         JobType = "sync_portfolio"
	JobTypeCheckNegativeBalances JobType = "check_negative_balances"
	JobTypeSyncPrices            JobType = "sync_prices"
	JobTypeSyncExchangeRates     JobType = "sync_exchange_rates"
	JobTypeUpdateDisplayTicker   JobType = "update_display_ticker"
	JobTypeRetryTrades           JobType = "retry_trades"

	// Planning jobs - individual responsibilities split from planner_batch
	JobTypeGeneratePortfolioHash   JobType = "generate_portfolio_hash"
	JobTypeGetOptimizerWeights     JobType = "get_optimizer_weights"
	JobTypeBuildOpportunityContext JobType = "build_opportunity_context"
	JobTypeIdentifyOpportunities   JobType = "identify_opportunities"
	JobTypeGenerateSequences       JobType = "generate_sequences"
	JobTypeEvaluateSequences       JobType = "evaluate_sequences"
	JobTypeCreateTradePlan         JobType = "create_trade_plan"
	JobTypeStoreRecommendations    JobType = "store_recommendations"

	// Dividend jobs - individual responsibilities split from dividend_reinvestment
	JobTypeGetUnreinvestedDividends      JobType = "get_unreinvested_dividends"
	JobTypeGroupDividendsBySymbol        JobType = "group_dividends_by_symbol"
	JobTypeCheckDividendYields           JobType = "check_dividend_yields"
	JobTypeCreateDividendRecommendations JobType = "create_dividend_recommendations"
	JobTypeSetPendingBonuses             JobType = "set_pending_bonuses"
	JobTypeExecuteDividendTrades         JobType = "execute_dividend_trades"

	// Health check jobs - individual responsibilities split from health_check
	JobTypeCheckCoreDatabases    JobType = "check_core_databases"
	JobTypeCheckHistoryDatabases JobType = "check_history_databases"
	JobTypeCheckWALCheckpoints   JobType = "check_wal_checkpoints"
)

// Priority represents job priority
type Priority int

const (
	PriorityLow Priority = iota
	PriorityMedium
	PriorityHigh
	PriorityCritical
)

// Job represents a queued job
type Job struct {
	ID          string
	Type        JobType
	Priority    Priority
	Payload     map[string]interface{}
	CreatedAt   time.Time
	AvailableAt time.Time
	Retries     int
	MaxRetries  int

	// Progress reporting (injected by WorkerPool)
	progressReporter *ProgressReporter
}

// GetProgressReporter returns the progress reporter for this job.
// Returns interface{} to satisfy the scheduler/base.JobBase interface requirement.
// Callers should type-assert to *ProgressReporter.
// Returns nil (not a nil-pointer interface) when no reporter is set.
func (j *Job) GetProgressReporter() interface{} {
	if j.progressReporter == nil {
		return nil
	}
	return j.progressReporter
}

// Queue interface for job queue operations
type Queue interface {
	Enqueue(job *Job) error
	Dequeue() (*Job, error)
	Size() int
}

// BaseJob provides a base implementation for scheduler jobs that need progress reporting
type BaseJob struct {
	queueJob *Job
}

// SetJob injects the queue.Job reference (satisfies scheduler.Job interface)
func (b *BaseJob) SetJob(j interface{}) {
	if qj, ok := j.(*Job); ok {
		b.queueJob = qj
	}
}

// GetProgressReporter returns the progress reporter for this job.
// Returns interface{} to match the scheduler/base.JobBase interface.
// Callers should type-assert to *ProgressReporter.
func (b *BaseJob) GetProgressReporter() interface{} {
	if b.queueJob == nil {
		return nil
	}
	return b.queueJob.GetProgressReporter()
}

// GetJobDescription returns a human-readable description for a job type
func GetJobDescription(jobType JobType) string {
	descriptions := map[JobType]string{
		// Composite jobs
		JobTypePlannerBatch:       "Generating trading recommendations",
		JobTypeEventBasedTrading:  "Executing trade",
		JobTypeTagUpdate:          "Updating security tags",
		JobTypeSyncCycle:          "Syncing all data from broker",
		JobTypeDividendReinvest:   "Processing dividend reinvestment",
		JobTypeHealthCheck:        "Running health check",
		JobTypeHourlyBackup:       "Creating hourly backup",
		JobTypeDailyBackup:        "Creating daily backup",
		JobTypeDailyMaintenance:   "Running daily maintenance",
		JobTypeWeeklyBackup:       "Creating weekly backup",
		JobTypeWeeklyMaintenance:  "Running weekly maintenance",
		JobTypeMonthlyBackup:      "Creating monthly backup",
		JobTypeMonthlyMaintenance: "Running monthly maintenance",
		JobTypeFormulaDiscovery:   "Discovering optimal formulas",
		JobTypeAdaptiveMarket:     "Checking market regime",
		JobTypeHistoryCleanup:     "Cleaning up historical data",
		JobTypeRecommendationGC:   "Cleaning up old recommendations",
		JobTypeClientDataCleanup:  "Cleaning up expired API cache",
		JobTypeDeployment:         "Checking for system updates",
		JobTypeR2Backup:           "Uploading backup to cloud",
		JobTypeR2BackupRotation:   "Rotating cloud backups",

		// Sync jobs
		JobTypeSyncTrades:            "Syncing trades from broker",
		JobTypeSyncCashFlows:         "Syncing cash flows",
		JobTypeSyncPortfolio:         "Syncing portfolio positions",
		JobTypeCheckNegativeBalances: "Checking account balances",
		JobTypeSyncPrices:            "Updating security prices",
		JobTypeSyncExchangeRates:     "Updating exchange rates",
		JobTypeUpdateDisplayTicker:   "Updating LED display",
		JobTypeRetryTrades:           "Retrying pending trades",

		// Planning jobs
		JobTypeGeneratePortfolioHash:   "Generating portfolio hash",
		JobTypeGetOptimizerWeights:     "Running portfolio optimizer",
		JobTypeBuildOpportunityContext: "Building opportunity context",
		JobTypeIdentifyOpportunities:   "Identifying opportunities",
		JobTypeGenerateSequences:       "Generating trade sequences",
		JobTypeEvaluateSequences:       "Evaluating trade sequences",
		JobTypeCreateTradePlan:         "Creating trade plan",
		JobTypeStoreRecommendations:    "Storing recommendations",

		// Dividend jobs
		JobTypeGetUnreinvestedDividends:      "Getting unreinvested dividends",
		JobTypeGroupDividendsBySymbol:        "Grouping dividends by symbol",
		JobTypeCheckDividendYields:           "Checking dividend yields",
		JobTypeCreateDividendRecommendations: "Creating dividend recommendations",
		JobTypeSetPendingBonuses:             "Setting pending bonuses",
		JobTypeExecuteDividendTrades:         "Executing dividend trades",

		// Health check jobs
		JobTypeCheckCoreDatabases:    "Checking core databases",
		JobTypeCheckHistoryDatabases: "Checking history databases",
		JobTypeCheckWALCheckpoints:   "Checking WAL checkpoints",
	}

	if desc, exists := descriptions[jobType]; exists {
		return desc
	}

	// Fallback to job type string
	return string(jobType)
}
