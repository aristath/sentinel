package jobs

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/events"
	"github.com/aristath/arduino-trader/internal/locking"
	"github.com/aristath/arduino-trader/internal/modules/cash_flows"
	"github.com/aristath/arduino-trader/internal/modules/display"
	"github.com/rs/zerolog"
)

// SyncJob handles background cash flow synchronization
type SyncJob struct {
	repo             *cash_flows.Repository
	depositProcessor *cash_flows.DepositProcessor
	dividendCreator  *cash_flows.DividendCreator
	tradernetClient  cash_flows.TradernetClient
	displayManager   *display.StateManager
	lockManager      *locking.Manager
	eventManager     *events.Manager
	log              zerolog.Logger
}

// NewSyncJob creates a new sync job
func NewSyncJob(
	repo *cash_flows.Repository,
	depositProcessor *cash_flows.DepositProcessor,
	dividendCreator *cash_flows.DividendCreator,
	tradernetClient cash_flows.TradernetClient,
	displayManager *display.StateManager,
	lockManager *locking.Manager,
	eventManager *events.Manager,
	log zerolog.Logger,
) *SyncJob {
	return &SyncJob{
		repo:             repo,
		depositProcessor: depositProcessor,
		dividendCreator:  dividendCreator,
		tradernetClient:  tradernetClient,
		displayManager:   displayManager,
		lockManager:      lockManager,
		eventManager:     eventManager,
		log:              log.With().Str("job", "cash_flow_sync").Logger(),
	}
}

// SyncCashFlows performs cash flow synchronization from Tradernet API
// Faithful translation from Python: app/modules/cash_flows/jobs/cash_flow_sync.py
func (j *SyncJob) SyncCashFlows() error {
	// 1. Acquire file lock (timeout 120s)
	lock, err := j.lockManager.AcquireLock("cash_flow_sync", 120*time.Second)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to acquire lock")
		j.eventManager.EmitError("cash_flows", err, map[string]interface{}{
			"step": "acquire_lock",
		})
		return fmt.Errorf("failed to acquire lock: %w", err)
	}
	defer lock.Release()

	// 2. Set LED4 to green
	j.displayManager.SetLED4(0, 255, 0)
	defer j.displayManager.SetLED4(0, 0, 0) // Clear on completion

	// 3. Emit CASH_FLOW_SYNC_START event
	j.eventManager.Emit(events.CashFlowSyncStart, "cash_flows", map[string]interface{}{
		"timestamp": time.Now().Format(time.RFC3339),
	})

	// 4. Connect to Tradernet
	if !j.tradernetClient.IsConnected() {
		err := fmt.Errorf("Tradernet not connected")
		j.log.Error().Msg("Tradernet not connected")
		j.eventManager.EmitError("cash_flows", err, map[string]interface{}{
			"step": "check_connection",
		})
		return err
	}

	// 5. Fetch all cash flows (limit 1000)
	transactions, err := j.tradernetClient.GetAllCashFlows(1000)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to fetch cash flows from Tradernet")
		j.eventManager.EmitError("cash_flows", err, map[string]interface{}{
			"step": "fetch_transactions",
		})
		return fmt.Errorf("failed to fetch cash flows: %w", err)
	}

	j.log.Info().Int("fetched", len(transactions)).Msg("Fetched transactions from Tradernet")

	// 6. Sync to database
	syncedCount := 0
	depositCount := 0
	dividendCount := 0

	for _, tx := range transactions {
		// Check if already exists
		exists, err := j.repo.Exists(tx.TransactionID)
		if err != nil {
			j.log.Error().Err(err).Str("tx_id", tx.TransactionID).Msg("Failed to check existence")
			continue
		}
		if exists {
			continue // Skip duplicates
		}

		// Create cash flow record
		cashFlow := &cash_flows.CashFlow{
			TransactionID:   tx.TransactionID,
			TypeDocID:       tx.TypeDocID,
			TransactionType: &tx.TransactionType,
			Date:            tx.Date,
			Amount:          tx.Amount,
			Currency:        tx.Currency,
			AmountEUR:       tx.AmountEUR,
			Status:          &tx.Status,
			StatusC:         &tx.StatusC,
			Description:     &tx.Description,
		}

		// Serialize params to JSON
		if len(tx.Params) > 0 {
			paramsJSON, _ := json.Marshal(tx.Params)
			paramsStr := string(paramsJSON)
			cashFlow.ParamsJSON = &paramsStr
		}

		// Insert into database
		created, err := j.repo.Create(cashFlow)
		if err != nil {
			j.log.Error().Err(err).Msg("Failed to create cash flow")
			j.eventManager.EmitError("cash_flows", err, map[string]interface{}{
				"step":           "create_cash_flow",
				"transaction_id": tx.TransactionID,
			})
			continue
		}
		syncedCount++

		// Process deposit if applicable
		if j.depositProcessor.ShouldProcessCashFlow(created) {
			_, err := j.depositProcessor.ProcessDeposit(
				created.AmountEUR,
				created.Currency,
				&created.TransactionID,
				created.Description,
			)
			if err != nil {
				j.log.Error().Err(err).Msg("Failed to process deposit")
				j.eventManager.EmitError("cash_flows", err, map[string]interface{}{
					"step":           "process_deposit",
					"transaction_id": created.TransactionID,
				})
				// Continue - don't block sync on deposit failure
			} else {
				depositCount++
				j.eventManager.Emit(events.DepositProcessed, "cash_flows", map[string]interface{}{
					"transaction_id": created.TransactionID,
					"amount_eur":     created.AmountEUR,
				})
			}
		}

		// Create dividend record if type is dividend
		if j.dividendCreator.ShouldCreateDividend(created) {
			err := j.dividendCreator.CreateDividendRecord(created)
			if err != nil {
				j.log.Error().Err(err).Msg("Failed to create dividend record")
				j.eventManager.EmitError("cash_flows", err, map[string]interface{}{
					"step":           "create_dividend",
					"transaction_id": created.TransactionID,
				})
				// Continue - don't block sync on dividend failure
			} else {
				dividendCount++
				j.eventManager.Emit(events.DividendCreated, "cash_flows", map[string]interface{}{
					"transaction_id": created.TransactionID,
					"amount_eur":     created.AmountEUR,
					"date":           created.Date,
				})
			}
		}
	}

	j.log.Info().
		Int("synced", syncedCount).
		Int("deposits_processed", depositCount).
		Int("dividends_created", dividendCount).
		Msg("Cash flow sync completed")

	// 7. Emit CASH_FLOW_SYNC_COMPLETE event
	j.eventManager.Emit(events.CashFlowSyncComplete, "cash_flows", map[string]interface{}{
		"synced_count":          syncedCount,
		"deposits_processed":    depositCount,
		"dividends_created":     dividendCount,
		"total_from_api":        len(transactions),
		"completion_timestamp": time.Now().Format(time.RFC3339),
	})

	return nil
}
