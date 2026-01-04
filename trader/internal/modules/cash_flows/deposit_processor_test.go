package cash_flows

import (
	"errors"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// MockBalanceService for testing
type MockBalanceService struct {
	allocations map[string]interface{}
	err         error
}

func (m *MockBalanceService) AllocateDeposit(amount float64, currency, description string) (map[string]interface{}, error) {
	if m.err != nil {
		return nil, m.err
	}
	return m.allocations, nil
}

// TestShouldProcessCashFlow tests deposit detection logic
func TestShouldProcessCashFlow(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	processor := NewDepositProcessor(&MockBalanceService{}, log)

	tests := []struct {
		name            string
		transactionType *string
		expected        bool
	}{
		{
			name:            "deposit type",
			transactionType: stringPtr("deposit"),
			expected:        true,
		},
		{
			name:            "DEPOSIT uppercase",
			transactionType: stringPtr("DEPOSIT"),
			expected:        true,
		},
		{
			name:            "refill type",
			transactionType: stringPtr("refill"),
			expected:        true,
		},
		{
			name:            "REFILL uppercase",
			transactionType: stringPtr("REFILL"),
			expected:        true,
		},
		{
			name:            "transfer_in type",
			transactionType: stringPtr("transfer_in"),
			expected:        true,
		},
		{
			name:            "TRANSFER_IN uppercase",
			transactionType: stringPtr("TRANSFER_IN"),
			expected:        true,
		},
		{
			name:            "dividend type should not process",
			transactionType: stringPtr("dividend"),
			expected:        false,
		},
		{
			name:            "withdrawal type should not process",
			transactionType: stringPtr("withdrawal"),
			expected:        false,
		},
		{
			name:            "nil transaction type",
			transactionType: nil,
			expected:        false,
		},
		{
			name:            "empty string",
			transactionType: stringPtr(""),
			expected:        false,
		},
		{
			name:            "unknown type",
			transactionType: stringPtr("unknown"),
			expected:        false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cashFlow := &CashFlow{
				TransactionType: tt.transactionType,
			}

			result := processor.ShouldProcessCashFlow(cashFlow)
			assert.Equal(t, tt.expected, result)
		})
	}
}

// TestProcessDeposit_Success tests successful deposit processing
func TestProcessDeposit_Success(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	expectedAllocations := map[string]interface{}{
		"core":      500.0,
		"satellite": 500.0,
	}

	mockService := &MockBalanceService{
		allocations: expectedAllocations,
		err:         nil,
	}

	processor := NewDepositProcessor(mockService, log)

	transactionID := "TXN123"
	description := "Monthly deposit"

	result, err := processor.ProcessDeposit(1000.0, "EUR", &transactionID, &description)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, expectedAllocations, result)
}

// TestProcessDeposit_NilDescription tests deposit with nil description
func TestProcessDeposit_NilDescription(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	expectedAllocations := map[string]interface{}{
		"core": 1000.0,
	}

	mockService := &MockBalanceService{
		allocations: expectedAllocations,
		err:         nil,
	}

	processor := NewDepositProcessor(mockService, log)

	transactionID := "TXN123"

	result, err := processor.ProcessDeposit(1000.0, "EUR", &transactionID, nil)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, expectedAllocations, result)
}

// TestProcessDeposit_AllocationFailure tests handling of allocation service errors
func TestProcessDeposit_AllocationFailure(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockService := &MockBalanceService{
		allocations: nil,
		err:         errors.New("database connection failed"),
	}

	processor := NewDepositProcessor(mockService, log)

	transactionID := "TXN123"
	description := "Monthly deposit"

	result, err := processor.ProcessDeposit(1000.0, "EUR", &transactionID, &description)

	assert.Error(t, err)
	assert.Nil(t, result)
	assert.Contains(t, err.Error(), "failed to allocate deposit")
}

// TestProcessDeposit_ZeroAmount tests deposit with zero amount
func TestProcessDeposit_ZeroAmount(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	expectedAllocations := map[string]interface{}{
		"core": 0.0,
	}

	mockService := &MockBalanceService{
		allocations: expectedAllocations,
		err:         nil,
	}

	processor := NewDepositProcessor(mockService, log)

	result, err := processor.ProcessDeposit(0.0, "EUR", nil, nil)

	assert.NoError(t, err)
	assert.NotNil(t, result)
}

// TestProcessDeposit_NegativeAmount tests deposit with negative amount (withdrawal scenario)
func TestProcessDeposit_NegativeAmount(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	expectedAllocations := map[string]interface{}{
		"core": -500.0,
	}

	mockService := &MockBalanceService{
		allocations: expectedAllocations,
		err:         nil,
	}

	processor := NewDepositProcessor(mockService, log)

	result, err := processor.ProcessDeposit(-500.0, "EUR", nil, nil)

	assert.NoError(t, err)
	assert.NotNil(t, result)
}

// TestProcessDeposit_DifferentCurrencies tests deposit processing with various currencies
func TestProcessDeposit_DifferentCurrencies(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	currencies := []string{"EUR", "USD", "GBP", "JPY"}

	for _, currency := range currencies {
		t.Run(currency, func(t *testing.T) {
			expectedAllocations := map[string]interface{}{
				"core": 1000.0,
			}

			mockService := &MockBalanceService{
				allocations: expectedAllocations,
				err:         nil,
			}

			processor := NewDepositProcessor(mockService, log)

			result, err := processor.ProcessDeposit(1000.0, currency, nil, nil)

			assert.NoError(t, err)
			assert.NotNil(t, result)
		})
	}
}

// TestProcessDeposit_SmallAmount tests deposit with very small amount (rounding edge case)
func TestProcessDeposit_SmallAmount(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	expectedAllocations := map[string]interface{}{
		"core":      0.005,
		"satellite": 0.005,
	}

	mockService := &MockBalanceService{
		allocations: expectedAllocations,
		err:         nil,
	}

	processor := NewDepositProcessor(mockService, log)

	result, err := processor.ProcessDeposit(0.01, "EUR", nil, nil)

	assert.NoError(t, err)
	assert.NotNil(t, result)
}

// TestProcessDeposit_LargeAmount tests deposit with large amount
func TestProcessDeposit_LargeAmount(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	expectedAllocations := map[string]interface{}{
		"core":      50000.0,
		"satellite": 50000.0,
	}

	mockService := &MockBalanceService{
		allocations: expectedAllocations,
		err:         nil,
	}

	processor := NewDepositProcessor(mockService, log)

	result, err := processor.ProcessDeposit(100000.0, "EUR", nil, nil)

	assert.NoError(t, err)
	assert.NotNil(t, result)
}

// TestProcessDeposit_MultipleAllocations tests complex allocation across multiple buckets
func TestProcessDeposit_MultipleAllocations(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	expectedAllocations := map[string]interface{}{
		"core":        333.33,
		"satellite_1": 333.33,
		"satellite_2": 333.34,
	}

	mockService := &MockBalanceService{
		allocations: expectedAllocations,
		err:         nil,
	}

	processor := NewDepositProcessor(mockService, log)

	result, err := processor.ProcessDeposit(1000.0, "EUR", nil, nil)

	assert.NoError(t, err)
	assert.NotNil(t, result)
	assert.Equal(t, expectedAllocations, result)
}

// Helper function to create string pointer
func stringPtr(s string) *string {
	return &s
}
