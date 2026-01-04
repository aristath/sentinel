package scheduler

import (
	"time"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/modules/satellites"
	"github.com/rs/zerolog"
)

// SatelliteReconciliationJob handles daily bucket reconciliation
// Faithful translation from Python: app/modules/satellites/jobs/bucket_reconciliation.py
//
// Ensures virtual bucket balances match actual brokerage balances by:
// 1. Fetching actual brokerage balances from Tradernet
// 2. Running reconciliation for each currency (EUR, USD, GBP, HKD)
// 3. Logging discrepancies
// 4. Alerting if significant drift detected
// 5. Auto-correcting minor discrepancies within tolerance
//
// This job is CRITICAL for maintaining the fundamental invariant:
// SUM(bucket_balances for currency X) == Actual brokerage balance for currency X
type SatelliteReconciliationJob struct {
	log                   zerolog.Logger
	tradernetClient       *tradernet.Client
	reconciliationService *satellites.ReconciliationService
}

// NewSatelliteReconciliationJob creates a new satellite reconciliation job
func NewSatelliteReconciliationJob(
	log zerolog.Logger,
	tradernetClient *tradernet.Client,
	reconciliationService *satellites.ReconciliationService,
) *SatelliteReconciliationJob {
	return &SatelliteReconciliationJob{
		log:                   log.With().Str("job", "satellite_reconciliation").Logger(),
		tradernetClient:       tradernetClient,
		reconciliationService: reconciliationService,
	}
}

// Name returns the job name
func (j *SatelliteReconciliationJob) Name() string {
	return "satellite_reconciliation"
}

// Run executes the satellite reconciliation job
// Note: Concurrent execution is prevented by the scheduler's SkipIfStillRunning wrapper
func (j *SatelliteReconciliationJob) Run() error {
	j.log.Info().Msg("Starting daily bucket reconciliation")
	startTime := time.Now()

	// Fetch actual brokerage balances from Tradernet
	if !j.tradernetClient.IsConnected() {
		j.log.Warn().Msg("Tradernet client not connected, skipping reconciliation")
		return nil
	}

	cashBalances, err := j.tradernetClient.GetCashBalances()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to fetch brokerage cash balances")
		return err
	}

	// Convert to map for reconciliation
	actualBalances := make(map[string]float64)
	for _, balance := range cashBalances {
		actualBalances[balance.Currency] = balance.Amount
		j.log.Debug().
			Str("currency", balance.Currency).
			Float64("balance", balance.Amount).
			Msg("Fetched brokerage balance")
	}

	// Run reconciliation for all currencies
	results, err := j.reconciliationService.ReconcileAll(actualBalances, nil)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to reconcile balances")
		return err
	}

	// Log results
	for _, result := range results {
		logEvent := j.log.Info()
		if !result.IsReconciled {
			logEvent = j.log.Warn()
		}

		logEvent.
			Str("currency", result.Currency).
			Float64("virtual_total", result.VirtualTotal).
			Float64("actual_total", result.ActualTotal).
			Float64("difference", result.Difference).
			Float64("difference_pct", result.DifferencePct()*100).
			Bool("reconciled", result.IsReconciled).
			Interface("adjustments", result.AdjustmentsMade).
			Msg("Reconciliation result")
	}

	elapsed := time.Since(startTime)

	j.log.Info().
		Float64("elapsed_seconds", elapsed.Seconds()).
		Int("currencies_checked", len(results)).
		Msg("Bucket reconciliation complete")

	return nil
}

// ReconciliationResult contains the result of a currency reconciliation
type ReconciliationResult struct {
	VirtualTotal    float64 `json:"virtual_total"`
	ActualBalance   float64 `json:"actual_balance"`
	Discrepancy     float64 `json:"discrepancy"`
	WithinTolerance bool    `json:"within_tolerance"`
	Corrected       bool    `json:"corrected"`
	NeedsAttention  bool    `json:"needs_attention"`
	Error           string  `json:"error,omitempty"`
}
