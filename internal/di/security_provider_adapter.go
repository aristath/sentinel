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
// Uses GetTradable() which replaces GetAllActive()
func (a *SecurityProviderAdapter) GetAllActive() ([]portfolio.SecurityInfo, error) {
	securities, err := a.repo.GetTradable()
	if err != nil {
		return nil, err
	}

	result := make([]portfolio.SecurityInfo, len(securities))
	for i, sec := range securities {
		result[i] = portfolio.SecurityInfo{
			ISIN:             sec.ISIN,
			Symbol:           sec.Symbol,
			Name:             sec.Name,
			Geography:        sec.Geography,
			FullExchangeName: sec.FullExchangeName,
			Industry:         sec.Industry,
			Currency:         sec.Currency,
			AllowSell:        sec.AllowSell,
		}
	}

	return result, nil
}

// GetAllActiveTradable returns all active and tradable securities (excludes indices)
// Uses GetTradable() which replaces GetAllActiveTradable()
func (a *SecurityProviderAdapter) GetAllActiveTradable() ([]portfolio.SecurityInfo, error) {
	securities, err := a.repo.GetTradable()
	if err != nil {
		return nil, err
	}

	result := make([]portfolio.SecurityInfo, len(securities))
	for i, sec := range securities {
		result[i] = portfolio.SecurityInfo{
			ISIN:             sec.ISIN,
			Symbol:           sec.Symbol,
			Name:             sec.Name,
			Geography:        sec.Geography,
			FullExchangeName: sec.FullExchangeName,
			Industry:         sec.Industry,
			Currency:         sec.Currency,
			AllowSell:        sec.AllowSell,
		}
	}

	return result, nil
}

// GetISINBySymbol returns ISIN for a given symbol
func (a *SecurityProviderAdapter) GetISINBySymbol(symbol string) (string, error) {
	return a.repo.GetISINBySymbol(symbol)
}
