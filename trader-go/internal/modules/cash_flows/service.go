package cash_flows

import (
	"github.com/rs/zerolog"
)

// CashFlowsService handles cash flow business logic
type CashFlowsService struct {
	log zerolog.Logger
}

// NewCashFlowsService creates a new cash flows service
func NewCashFlowsService(log zerolog.Logger) *CashFlowsService {
	return &CashFlowsService{
		log: log.With().Str("service", "cash_flows").Logger(),
	}
}

// SyncFromTradernet synchronizes cash flows from Tradernet microservice
// TODO: Implement in future phase
func (s *CashFlowsService) SyncFromTradernet() error {
	s.log.Debug().Msg("Cash flows sync not yet implemented")
	return nil
}
