package di

import (
	"github.com/aristath/sentinel/internal/modules/symbolic_regression"
	"github.com/aristath/sentinel/internal/modules/universe"
)

// SymbolicRegressionSecurityProviderAdapter adapts universe.SecurityRepository to symbolic_regression.SecurityProvider interface
type SymbolicRegressionSecurityProviderAdapter struct {
	repo universe.SecurityRepositoryInterface
}

// NewSymbolicRegressionSecurityProviderAdapter creates a new adapter for symbolic regression module
func NewSymbolicRegressionSecurityProviderAdapter(repo universe.SecurityRepositoryInterface) *SymbolicRegressionSecurityProviderAdapter {
	return &SymbolicRegressionSecurityProviderAdapter{repo: repo}
}

// GetISINBySymbol returns ISIN for a given symbol
func (a *SymbolicRegressionSecurityProviderAdapter) GetISINBySymbol(symbol string) (string, error) {
	return a.repo.GetISINBySymbol(symbol)
}

// GetSymbolByISIN returns symbol for a given ISIN
func (a *SymbolicRegressionSecurityProviderAdapter) GetSymbolByISIN(isin string) (string, error) {
	return a.repo.GetSymbolByISIN(isin)
}

// GetAll returns all securities, converting universe.Security to symbolic_regression.SecurityInfo
func (a *SymbolicRegressionSecurityProviderAdapter) GetAll() ([]symbolic_regression.SecurityInfo, error) {
	securities, err := a.repo.GetAll()
	if err != nil {
		return nil, err
	}

	result := make([]symbolic_regression.SecurityInfo, len(securities))
	for i, sec := range securities {
		result[i] = symbolic_regression.SecurityInfo{
			ISIN:        sec.ISIN,
			Symbol:      sec.Symbol,
			ProductType: sec.ProductType,
		}
	}

	return result, nil
}
