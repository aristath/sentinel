package di

import (
	"github.com/aristath/sentinel/internal/modules/universe"
)

// TradingSecurityProviderAdapter adapts universe.SecurityRepository to trading.SecurityProvider interface
// Implements: GetISINBySymbol(symbol string) (string, error)
//
//	BatchGetISINsBySymbols(symbols []string) (map[string]string, error)
type TradingSecurityProviderAdapter struct {
	repo universe.SecurityRepositoryInterface
}

// NewTradingSecurityProviderAdapter creates a new adapter for trading module
func NewTradingSecurityProviderAdapter(repo universe.SecurityRepositoryInterface) *TradingSecurityProviderAdapter {
	return &TradingSecurityProviderAdapter{repo: repo}
}

// GetISINBySymbol returns ISIN for a given symbol
func (a *TradingSecurityProviderAdapter) GetISINBySymbol(symbol string) (string, error) {
	return a.repo.GetISINBySymbol(symbol)
}

// BatchGetISINsBySymbols returns a map of symbol → ISIN for multiple symbols
func (a *TradingSecurityProviderAdapter) BatchGetISINsBySymbols(symbols []string) (map[string]string, error) {
	return a.repo.BatchGetISINsBySymbols(symbols)
}
