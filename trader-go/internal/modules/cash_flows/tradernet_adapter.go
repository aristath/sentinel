package cash_flows

import (
	"github.com/aristath/arduino-trader/internal/clients/tradernet"
)

// TradernetAdapter adapts the Tradernet client to the TradernetClient interface
type TradernetAdapter struct {
	client *tradernet.Client
}

// NewTradernetAdapter creates a new adapter
func NewTradernetAdapter(client *tradernet.Client) *TradernetAdapter {
	return &TradernetAdapter{
		client: client,
	}
}

// GetAllCashFlows fetches cash flows and converts to APITransaction format
func (a *TradernetAdapter) GetAllCashFlows(limit int) ([]APITransaction, error) {
	tradernetCashFlows, err := a.client.GetAllCashFlows(limit)
	if err != nil {
		return nil, err
	}

	// Convert Tradernet format to our APITransaction format
	apiTransactions := make([]APITransaction, len(tradernetCashFlows))
	for i, tcf := range tradernetCashFlows {
		apiTransactions[i] = APITransaction{
			// Handle flexible field names from Tradernet API
			TransactionID: getTransactionID(tcf),
			TypeDocID:     tcf.TypeDocID,
			TransactionType: getTransactionType(tcf),
			Date:            getDate(tcf),
			Amount:          getAmount(tcf),
			Currency:        getCurrency(tcf),
			AmountEUR:       getAmountEUR(tcf),
			Status:          tcf.Status,
			StatusC:         tcf.StatusC,
			Description:     tcf.Description,
			Params:          tcf.Params,
		}
	}

	return apiTransactions, nil
}

// IsConnected checks if Tradernet is connected
func (a *TradernetAdapter) IsConnected() bool {
	return a.client.IsConnected()
}

// Helper functions to handle flexible field names

func getTransactionID(tcf tradernet.CashFlowTransaction) string {
	if tcf.TransactionID != "" {
		return tcf.TransactionID
	}
	return tcf.ID
}

func getTransactionType(tcf tradernet.CashFlowTransaction) string {
	if tcf.TransactionType != "" {
		return tcf.TransactionType
	}
	return tcf.Type
}

func getDate(tcf tradernet.CashFlowTransaction) string {
	if tcf.Date != "" {
		return tcf.Date
	}
	return tcf.DT
}

func getAmount(tcf tradernet.CashFlowTransaction) float64 {
	if tcf.Amount != 0 {
		return tcf.Amount
	}
	return tcf.SM
}

func getCurrency(tcf tradernet.CashFlowTransaction) string {
	if tcf.Currency != "" {
		return tcf.Currency
	}
	return tcf.Curr
}

func getAmountEUR(tcf tradernet.CashFlowTransaction) float64 {
	if tcf.AmountEUR != 0 {
		return tcf.AmountEUR
	}
	return tcf.SMEUR
}
