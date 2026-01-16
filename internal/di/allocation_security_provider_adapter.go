package di

import (
	"github.com/aristath/sentinel/internal/modules/allocation"
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
func (a *AllocationSecurityProviderAdapter) GetAllActiveTradable() ([]allocation.SecurityInfo, error) {
	// Use GetTradable() which replaces GetAllActiveTradable()
	securities, err := a.repo.GetTradable()
	if err != nil {
		return nil, err
	}

	result := make([]allocation.SecurityInfo, len(securities))
	for i, sec := range securities {
		result[i] = allocation.SecurityInfo{
			ISIN:      sec.ISIN,
			Symbol:    sec.Symbol,
			Name:      sec.Name,
			Geography: sec.Geography,
			Industry:  sec.Industry,
		}
	}

	return result, nil
}
