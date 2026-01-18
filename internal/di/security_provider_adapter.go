package di

import (
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
)

// SecurityProviderAdapter adapts universe.SecurityRepository to portfolio.SecurityProvider interface
// This adapter breaks the import cycle between portfolio and universe packages by living in the DI layer
type SecurityProviderAdapter struct {
	repo universe.SecurityRepositoryInterface
}

// NewSecurityProviderAdapter creates a new adapter
func NewSecurityProviderAdapter(repo universe.SecurityRepositoryInterface) *SecurityProviderAdapter {
	return &SecurityProviderAdapter{repo: repo}
}

// GetAllActive returns all active securities (excludes indices)
// Converts universe.Security to portfolio.SecurityInfo for portfolio module compatibility
func (a *SecurityProviderAdapter) GetAllActive() ([]portfolio.SecurityInfo, error) {
	securities, err := a.repo.GetTradable()
	if err != nil {
		return nil, err
	}

	result := make([]portfolio.SecurityInfo, 0, len(securities))
	for _, sec := range securities {
		// SecurityRepository automatically merges overrides via ApplyOverrides(),
		// so sec.AllowSell already contains the override value (if set) or default (true)
		result = append(result, portfolio.SecurityInfo{
			ISIN:             sec.ISIN,
			Symbol:           sec.Symbol,
			Name:             sec.Name,
			Geography:        sec.Geography,
			FullExchangeName: sec.FullExchangeName,
			Industry:         sec.Industry,
			Currency:         sec.Currency,
			AllowSell:        sec.AllowSell, // Already merged by SecurityRepository
		})
	}

	return result, nil
}

// GetAllActiveTradable returns all active and tradable securities (excludes indices)
// Converts universe.Security to portfolio.SecurityInfo for portfolio module compatibility
func (a *SecurityProviderAdapter) GetAllActiveTradable() ([]portfolio.SecurityInfo, error) {
	// Same as GetAllActive - both return tradable securities
	return a.GetAllActive()
}

// GetISINBySymbol returns ISIN for a given symbol
func (a *SecurityProviderAdapter) GetISINBySymbol(symbol string) (string, error) {
	return a.repo.GetISINBySymbol(symbol)
}
