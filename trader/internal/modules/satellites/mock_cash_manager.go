package satellites

import (
	"fmt"
	"sync"
)

// MockCashManager is a simple mock implementation of CashManager for testing
type MockCashManager struct {
	balances map[string]float64 // key: "bucketID:currency", value: balance
	mu       sync.RWMutex
}

// NewMockCashManager creates a new mock cash manager
func NewMockCashManager() *MockCashManager {
	return &MockCashManager{
		balances: make(map[string]float64),
	}
}

// UpdateCashPosition updates a cash position
func (m *MockCashManager) UpdateCashPosition(bucketID string, currency string, balance float64) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	key := fmt.Sprintf("%s:%s", bucketID, currency)
	m.balances[key] = balance
	return nil
}

// GetCashBalance gets cash balance for a bucket and currency
func (m *MockCashManager) GetCashBalance(bucketID string, currency string) (float64, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	key := fmt.Sprintf("%s:%s", bucketID, currency)
	balance, ok := m.balances[key]
	if !ok {
		return 0, nil
	}
	return balance, nil
}

// GetAllCashBalances gets all cash balances for a bucket
func (m *MockCashManager) GetAllCashBalances(bucketID string) (map[string]float64, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	result := make(map[string]float64)
	prefix := bucketID + ":"
	for key, balance := range m.balances {
		if len(key) > len(prefix) && key[:len(prefix)] == prefix {
			currency := key[len(prefix):]
			result[currency] = balance
		}
	}
	return result, nil
}

// GetTotalByCurrency gets total balance across all buckets for a currency
func (m *MockCashManager) GetTotalByCurrency(currency string) (float64, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	total := 0.0
	suffix := ":" + currency
	for key, balance := range m.balances {
		if len(key) > len(suffix) && key[len(key)-len(suffix):] == suffix {
			total += balance
		}
	}
	return total, nil
}

// GetAllCashSymbols gets all cash symbols
func (m *MockCashManager) GetAllCashSymbols() ([]string, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	symbols := make([]string, 0, len(m.balances))
	for key := range m.balances {
		// Convert "bucketID:currency" to "CASH:currency:bucketID" format
		for i := len(key) - 1; i >= 0; i-- {
			if key[i] == ':' {
				bucketID := key[:i]
				currency := key[i+1:]
				symbol := fmt.Sprintf("CASH:%s:%s", currency, bucketID)
				symbols = append(symbols, symbol)
				break
			}
		}
	}
	return symbols, nil
}

// AdjustCashBalance adjusts cash balance by delta
func (m *MockCashManager) AdjustCashBalance(bucketID string, currency string, delta float64) (float64, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	key := fmt.Sprintf("%s:%s", bucketID, currency)
	current := m.balances[key]
	newBalance := current + delta
	if newBalance < 0 {
		newBalance = 0
	}
	m.balances[key] = newBalance
	return newBalance, nil
}
