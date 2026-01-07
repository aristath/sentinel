package cash_flows

// CashRepositoryInterface defines the contract for cash repository operations
type CashRepositoryInterface interface {
	// Get returns the cash balance for the given currency
	// Returns 0.0 if currency doesn't exist (not an error)
	Get(currency string) (float64, error)

	// GetAll returns all cash balances as a map of currency -> balance
	GetAll() (map[string]float64, error)

	// Upsert inserts or updates a cash balance for the given currency
	Upsert(currency string, balance float64) error

	// Delete removes a cash balance for the given currency
	// Does not error if currency doesn't exist
	Delete(currency string) error
}

// Compile-time check that CashRepository implements CashRepositoryInterface
var _ CashRepositoryInterface = (*CashRepository)(nil)
