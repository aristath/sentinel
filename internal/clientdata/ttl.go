package clientdata

import "time"

// TTL constants for different data types.
// These are added to time.Now() when storing to calculate expires_at.
const (
	// Very stable data (rarely changes)
	TTLOpenFIGI         = 30 * 24 * time.Hour // 30 days - ISIN-to-ticker mappings rarely change
	TTLSecurityMetadata = 30 * 24 * time.Hour // 30 days - Static company info

	// Quarterly financial data (updates with filings)
	TTLBalanceSheet = 45 * 24 * time.Hour // 45 days - Quarterly balance sheets
	TTLCashFlow     = 45 * 24 * time.Hour // 45 days - Quarterly cash flow statements
	TTLEarnings     = 45 * 24 * time.Hour // 45 days - Quarterly earnings reports

	// Weekly-ish data (changes more frequently but not critical)
	TTLAVOverview    = 7 * 24 * time.Hour // 7 days - Company overview, P/E, market cap
	TTLDividends     = 7 * 24 * time.Hour // 7 days - Dividend history
	TTLETFProfile    = 7 * 24 * time.Hour // 7 days - ETF profile and holdings
	TTLYahooMetadata = 7 * 24 * time.Hour // 7 days - Yahoo security metadata

	// Daily data (time-sensitive signals)
	TTLInsider  = 24 * time.Hour // 1 day - Insider transactions (time-sensitive signal)
	TTLEconomic = 24 * time.Hour // 1 day - Economic indicators (Fed releases, CPI, etc.)

	// Short-lived data (changes frequently)
	TTLExchangeRate = time.Hour        // 1 hour - Currency exchange rates
	TTLCurrentPrice = 10 * time.Minute // 10 minutes - Current price cache for batch operations
)
