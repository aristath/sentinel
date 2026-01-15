package calculations

import (
	"time"

	"github.com/rs/zerolog"
)

// SyncThresholdHours is how old last_synced must be to require processing (24 hours)
const SyncThresholdHours = 24

// SecurityInfo holds minimal security data for sync processing
type SecurityInfo struct {
	ISIN       string
	Symbol     string
	LastSynced *int64
}

// SecuritySyncer defines the interface for syncing a single security.
// This is implemented by universe.SyncService.RefreshSingleSecurity.
type SecuritySyncer interface {
	RefreshSingleSecurity(symbol string) error
}

// DefaultSyncProcessor implements SyncProcessor using existing SyncService logic.
// It checks if a security needs sync based on its LastSynced timestamp and
// delegates the actual sync to the underlying SecuritySyncer.
type DefaultSyncProcessor struct {
	syncer SecuritySyncer
	log    zerolog.Logger
}

// NewDefaultSyncProcessor creates a new sync processor
func NewDefaultSyncProcessor(syncer SecuritySyncer, log zerolog.Logger) *DefaultSyncProcessor {
	return &DefaultSyncProcessor{
		syncer: syncer,
		log:    log.With().Str("component", "sync_processor").Logger(),
	}
}

// NeedsSync checks if a security needs sync (24h threshold).
// A security needs sync if:
// - last_synced is NULL (never synced)
// - last_synced is older than SyncThresholdHours
func (sp *DefaultSyncProcessor) NeedsSync(security SecurityInfo) bool {
	if security.LastSynced == nil {
		return true // Never synced
	}
	threshold := time.Now().Add(-SyncThresholdHours * time.Hour).Unix()
	return *security.LastSynced < threshold
}

// ProcessSync syncs historical data and scores for a single security.
// This delegates to SyncService.RefreshSingleSecurity which handles:
// 1. Sync historical prices
// 2. Refresh score
// 3. Update last_synced timestamp
func (sp *DefaultSyncProcessor) ProcessSync(security SecurityInfo) error {
	return sp.syncer.RefreshSingleSecurity(security.Symbol)
}
