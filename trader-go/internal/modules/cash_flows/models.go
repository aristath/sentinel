package cash_flows

import (
	"time"
)

// CashFlow represents a cash flow transaction (append-only ledger)
// Faithful translation from Python: app/modules/cash_flows/domain/models.py
type CashFlow struct {
	ID              int       `json:"id,omitempty"`
	TransactionID   string    `json:"transaction_id"`           // Unique from Tradernet
	TypeDocID       int       `json:"type_doc_id"`              // Transaction type code
	TransactionType *string   `json:"transaction_type"`         // DEPOSIT, WITHDRAWAL, etc.
	Date            string    `json:"date"`                     // YYYY-MM-DD
	Amount          float64   `json:"amount"`                   // Original currency
	Currency        string    `json:"currency"`                 // Currency code
	AmountEUR       float64   `json:"amount_eur"`               // Converted to EUR
	Status          *string   `json:"status"`                   // Status string
	StatusC         *int      `json:"status_c"`                 // Status code
	Description     *string   `json:"description"`              // Human description
	ParamsJSON      *string   `json:"-"`                        // Raw params (not exposed in API)
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at,omitempty"`     // Not used (append-only)
}

// APITransaction represents transaction from Tradernet API
// Used during sync_from_api - handles flexible field naming
type APITransaction struct {
	TransactionID   string                 `json:"id"`           // May also be "transaction_id"
	TypeDocID       int                    `json:"type_doc_id"`
	TransactionType string                 `json:"type"`         // May also be "transaction_type"
	Date            string                 `json:"dt"`           // May also be "date"
	Amount          float64                `json:"sm"`           // May also be "amount"
	Currency        string                 `json:"curr"`         // May also be "currency"
	AmountEUR       float64                `json:"sm_eur"`       // May also be "amount_eur"
	Status          string                 `json:"status"`
	StatusC         int                    `json:"status_c"`
	Description     string                 `json:"description"`
	Params          map[string]interface{} `json:"params"` // Raw params dict
}
