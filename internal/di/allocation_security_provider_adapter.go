package di

import (
	"github.com/aristath/sentinel/internal/modules/universe"
)

// AllocationSecurityProviderAdapter adapts universe.SecurityRepository to allocation.SecurityProvider interface
type AllocationSecurityProviderAdapter struct {
	repo universe.SecurityRepositoryInterface
}

// NewAllocationSecurityProviderAdapter creates a new adapter for allocation
func NewAllocationSecurityProviderAdapter(repo universe.SecurityRepositoryInterface) *AllocationSecurityProviderAdapter {
	return &AllocationSecurityProviderAdapter{repo: repo}
}

// GetAllActiveTradable returns all active and tradable securities
func (a *AllocationSecurityProviderAdapter) GetAllActiveTradable() ([]universe.Security, error) {
	// Use GetTradable() which replaces GetAllActiveTradable()
	// Returns universe.Security directly - no conversion needed
	return a.repo.GetTradable()
}
