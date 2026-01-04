package cash_flows

// TradernetClient interface for fetching cash flows
// Implemented by tradernet.Client
type TradernetClient interface {
	GetAllCashFlows(limit int) ([]APITransaction, error)
	IsConnected() bool
}
