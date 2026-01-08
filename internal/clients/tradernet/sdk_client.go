package tradernet

// SDKClient interface for dependency injection in tests
// This interface matches the SDK client methods we need
type SDKClient interface {
	AccountSummary() (interface{}, error)
	Buy(symbol string, quantity int, price float64, duration string, useMargin bool, customOrderID *int) (interface{}, error)
	Sell(symbol string, quantity int, price float64, duration string, useMargin bool, customOrderID *int) (interface{}, error)
	GetPlaced(active bool) (interface{}, error)
	GetClientCpsHistory(dateFrom, dateTo string, cpsDocID, id, limit, offset, cpsStatus *int) (interface{}, error)
	CorporateActions(reception int) (interface{}, error)
	GetTradesHistory(start, end string, tradeID, limit, reception *int, symbol, currency *string) (interface{}, error)
	FindSymbol(symbol string, exchange *string) (interface{}, error)
	GetQuotes(symbols []string) (interface{}, error)
	UserInfo() (interface{}, error)
}
