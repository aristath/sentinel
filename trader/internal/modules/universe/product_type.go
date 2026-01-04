package universe

import "strings"

// ProductType represents the type of financial product/instrument
// Faithful translation from Python: app/domain/value_objects/product_type.py
type ProductType string

const (
	// ProductTypeEquity represents individual stocks/shares
	ProductTypeEquity ProductType = "EQUITY"
	// ProductTypeETF represents Exchange Traded Funds
	ProductTypeETF ProductType = "ETF"
	// ProductTypeETC represents Exchange Traded Commodities
	ProductTypeETC ProductType = "ETC"
	// ProductTypeMutualFund represents mutual funds (some UCITS products)
	ProductTypeMutualFund ProductType = "MUTUALFUND"
	// ProductTypeCash represents cash positions (synthetic securities for currency balances)
	ProductTypeCash ProductType = "CASH"
	// ProductTypeUnknown represents unknown type
	ProductTypeUnknown ProductType = "UNKNOWN"
)

// FromYahooQuoteType detects product type from Yahoo Finance quoteType with heuristics
// Faithful translation from Python: app/domain/value_objects/product_type.py -> from_yahoo_quote_type()
//
// Yahoo Finance provides a quoteType field, but it's not always accurate:
// - EQUITY: Regular stocks (reliable)
// - ETF: Most ETFs (reliable)
// - MUTUALFUND: Can be UCITS ETFs or actual mutual funds or ETCs
//
// We use heuristics on the product name to distinguish ETCs from other MUTUALFUND types.
func FromYahooQuoteType(quoteType string, productName string) ProductType {
	if quoteType == "" {
		return ProductTypeUnknown
	}

	quoteType = strings.ToUpper(quoteType)

	// Direct mappings
	if quoteType == "EQUITY" {
		return ProductTypeEquity
	} else if quoteType == "ETF" {
		return ProductTypeETF
	} else if quoteType == "MUTUALFUND" {
		// Use heuristics to distinguish ETCs from ETFs/Mutual Funds
		nameUpper := strings.ToUpper(productName)

		// ETC indicators: commodity names or "ETC" in name
		etcIndicators := []string{
			"ETC",
			"COMMODITY",
			"COMMODITIES",
			"GOLD",
			"SILVER",
			"PLATINUM",
			"PALLADIUM",
			"COPPER",
			"ALUMINIUM",
			"ALUMINUM",
			"OIL",
			"CRUDE",
			"BRENT",
			"WTI",
			"NATURAL GAS",
			"CORN",
			"WHEAT",
			"SOYBEAN",
		}

		for _, indicator := range etcIndicators {
			if strings.Contains(nameUpper, indicator) {
				return ProductTypeETC
			}
		}

		// ETF indicators: "ETF" explicitly in name
		if strings.Contains(nameUpper, "ETF") {
			return ProductTypeETF
		}

		// Default to MUTUALFUND if no clear indicators
		return ProductTypeMutualFund
	} else {
		// Other types (INDEX, CURRENCY, etc.) - return UNKNOWN
		return ProductTypeUnknown
	}
}
