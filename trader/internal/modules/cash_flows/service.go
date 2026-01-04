package cash_flows

import (
	"github.com/rs/zerolog"
)

// SyncJobInterface defines the interface for cash flow sync operations
// This interface breaks the import cycle between cash_flows and cash_flows/jobs
type SyncJobInterface interface {
	SyncCashFlows() error
}

// CashFlowsService handles cash flow business logic
type CashFlowsService struct {
	syncJob SyncJobInterface
	log     zerolog.Logger
}

// NewCashFlowsService creates a new cash flows service
func NewCashFlowsService(syncJob SyncJobInterface, log zerolog.Logger) *CashFlowsService {
	return &CashFlowsService{
		syncJob: syncJob,
		log:     log.With().Str("service", "cash_flows").Logger(),
	}
}

// SyncFromTradernet synchronizes cash flows from Tradernet microservice
// Delegates to SyncJob for actual implementation
func (s *CashFlowsService) SyncFromTradernet() error {
	return s.syncJob.SyncCashFlows()
}
