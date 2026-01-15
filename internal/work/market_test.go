package work

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

// MockMarketChecker is a mock implementation for testing
type MockMarketChecker struct {
	isOpen           bool
	isSecurityOpen   map[string]bool
	allMarketsClosed bool
}

func (m *MockMarketChecker) IsAnyMarketOpen() bool {
	return m.isOpen
}

func (m *MockMarketChecker) IsSecurityMarketOpen(isin string) bool {
	if m.isSecurityOpen == nil {
		return m.isOpen
	}
	open, exists := m.isSecurityOpen[isin]
	if !exists {
		return m.isOpen
	}
	return open
}

func (m *MockMarketChecker) AreAllMarketsClosed() bool {
	return m.allMarketsClosed
}

func TestMarketTimingChecker_CanExecute_AnyTime(t *testing.T) {
	mock := &MockMarketChecker{isOpen: false, allMarketsClosed: true}
	checker := NewMarketTimingChecker(mock)

	// AnyTime should always return true
	assert.True(t, checker.CanExecute(AnyTime, ""))
	assert.True(t, checker.CanExecute(AnyTime, "NL0010273215"))

	mock.isOpen = true
	mock.allMarketsClosed = false
	assert.True(t, checker.CanExecute(AnyTime, ""))
	assert.True(t, checker.CanExecute(AnyTime, "US0378331005"))
}

func TestMarketTimingChecker_CanExecute_AfterMarketClose(t *testing.T) {
	mock := &MockMarketChecker{
		isOpen: true,
		isSecurityOpen: map[string]bool{
			"NL0010273215": false, // Amsterdam closed
			"US0378331005": true,  // US open
		},
	}
	checker := NewMarketTimingChecker(mock)

	t.Run("returns true when security market is closed", func(t *testing.T) {
		result := checker.CanExecute(AfterMarketClose, "NL0010273215")
		assert.True(t, result)
	})

	t.Run("returns false when security market is open", func(t *testing.T) {
		result := checker.CanExecute(AfterMarketClose, "US0378331005")
		assert.False(t, result)
	})

	t.Run("global work uses any market open check", func(t *testing.T) {
		// When any market is open, global AfterMarketClose work shouldn't run
		result := checker.CanExecute(AfterMarketClose, "")
		assert.False(t, result)

		// When no markets are open, it should run
		mock.isOpen = false
		result = checker.CanExecute(AfterMarketClose, "")
		assert.True(t, result)
	})
}

func TestMarketTimingChecker_CanExecute_DuringMarketOpen(t *testing.T) {
	mock := &MockMarketChecker{
		isOpen: true,
		isSecurityOpen: map[string]bool{
			"NL0010273215": false, // Amsterdam closed
			"US0378331005": true,  // US open
		},
	}
	checker := NewMarketTimingChecker(mock)

	t.Run("returns true when security market is open", func(t *testing.T) {
		result := checker.CanExecute(DuringMarketOpen, "US0378331005")
		assert.True(t, result)
	})

	t.Run("returns false when security market is closed", func(t *testing.T) {
		result := checker.CanExecute(DuringMarketOpen, "NL0010273215")
		assert.False(t, result)
	})

	t.Run("global work uses any market open check", func(t *testing.T) {
		// When any market is open, global DuringMarketOpen work should run
		result := checker.CanExecute(DuringMarketOpen, "")
		assert.True(t, result)

		// When no markets are open, it shouldn't run
		mock.isOpen = false
		result = checker.CanExecute(DuringMarketOpen, "")
		assert.False(t, result)
	})
}

func TestMarketTimingChecker_CanExecute_AllMarketsClosed(t *testing.T) {
	mock := &MockMarketChecker{
		isOpen:           true,
		allMarketsClosed: false,
	}
	checker := NewMarketTimingChecker(mock)

	t.Run("returns false when any market is open", func(t *testing.T) {
		result := checker.CanExecute(AllMarketsClosed, "")
		assert.False(t, result)
	})

	t.Run("returns true when all markets are closed", func(t *testing.T) {
		mock.isOpen = false
		mock.allMarketsClosed = true

		result := checker.CanExecute(AllMarketsClosed, "")
		assert.True(t, result)
	})

	t.Run("subject is ignored for AllMarketsClosed", func(t *testing.T) {
		mock.isOpen = false
		mock.allMarketsClosed = true

		// Subject should be ignored - it's a global timing check
		result := checker.CanExecute(AllMarketsClosed, "NL0010273215")
		assert.True(t, result)
	})
}

func TestMarketTimingChecker_CanExecute_UnknownTiming(t *testing.T) {
	mock := &MockMarketChecker{isOpen: true}
	checker := NewMarketTimingChecker(mock)

	// Unknown timing should default to false for safety
	result := checker.CanExecute(MarketTiming(99), "")
	assert.False(t, result)
}
