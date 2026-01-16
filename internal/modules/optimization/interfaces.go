package optimization

// Note: TradernetClientInterface and CurrencyExchangeServiceInterface have been moved to domain/interfaces.go
// They are now available as domain.TradernetClientInterface and domain.CurrencyExchangeServiceInterface

// SecurityProvider provides read-only access to securities for ISIN lookups.
// Used to avoid circular dependencies with universe module.
type SecurityProvider interface {
	GetISINBySymbol(symbol string) (string, error)
}
