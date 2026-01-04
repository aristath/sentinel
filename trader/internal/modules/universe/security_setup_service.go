package universe

import (
	"fmt"
	"strings"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/clients/yahoo"
	"github.com/aristath/arduino-trader/internal/events"
	"github.com/rs/zerolog"
)

// SecuritySetupService handles comprehensive security onboarding
// Faithful translation from Python: app/modules/universe/services/security_setup_service.py
type SecuritySetupService struct {
	symbolResolver  *SymbolResolver
	securityRepo    *SecurityRepository
	tradernetClient *tradernet.Client
	yahooClient     *yahoo.Client
	historicalSync  *HistoricalSyncService
	eventManager    *events.Manager
	scoreCalculator ScoreCalculator // Interface for score calculation
	log             zerolog.Logger
}

// ScoreCalculator interface for calculating and saving security scores
// Implemented by UniverseHandlers.calculateAndSaveScore
type ScoreCalculator interface {
	CalculateAndSaveScore(symbol string, yahooSymbol string, country string, industry string) error
}

// NewSecuritySetupService creates a new security setup service
func NewSecuritySetupService(
	symbolResolver *SymbolResolver,
	securityRepo *SecurityRepository,
	tradernetClient *tradernet.Client,
	yahooClient *yahoo.Client,
	historicalSync *HistoricalSyncService,
	eventManager *events.Manager,
	scoreCalculator ScoreCalculator,
	log zerolog.Logger,
) *SecuritySetupService {
	return &SecuritySetupService{
		symbolResolver:  symbolResolver,
		securityRepo:    securityRepo,
		tradernetClient: tradernetClient,
		yahooClient:     yahooClient,
		historicalSync:  historicalSync,
		eventManager:    eventManager,
		scoreCalculator: scoreCalculator,
		log:             log.With().Str("service", "security_setup").Logger(),
	}
}

// SetScoreCalculator sets the score calculator (for deferred wiring)
func (s *SecuritySetupService) SetScoreCalculator(calculator ScoreCalculator) {
	s.scoreCalculator = calculator
}

// CreateSecurity creates a security with explicit symbol and name
// Faithful translation from Python: app/modules/universe/api/securities.py -> create_stock()
//
// This method:
// 1. Validates symbol is unique
// 2. Auto-detects country, exchange, industry from Yahoo Finance
// 3. Creates the security in the database
// 4. Publishes SecurityAdded event
// 5. Calculates and saves the initial security score
//
// Unlike AddSecurityByIdentifier, this does NOT:
// - Fetch historical price data (handled by background sync jobs)
// - Fetch Tradernet metadata (currency, ISIN)
// - Resolve identifiers (symbol is already provided)
func (s *SecuritySetupService) CreateSecurity(
	symbol string,
	name string,
	yahooSymbol string,
	minLot int,
	allowBuy bool,
	allowSell bool,
) (*Security, error) {
	symbol = strings.TrimSpace(strings.ToUpper(symbol))
	if symbol == "" {
		return nil, fmt.Errorf("symbol cannot be empty")
	}
	if name == "" {
		return nil, fmt.Errorf("name cannot be empty")
	}

	s.log.Info().
		Str("symbol", symbol).
		Str("name", name).
		Msg("Creating security")

	// Check if security already exists
	existing, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return nil, fmt.Errorf("failed to check existing security: %w", err)
	}
	if existing != nil {
		return nil, fmt.Errorf("security already exists: %s", existing.Symbol)
	}

	// Auto-detect country, exchange, and industry from Yahoo Finance
	var yahooSymbolPtr *string
	if yahooSymbol != "" {
		yahooSymbolPtr = &yahooSymbol
	}

	country, fullExchangeName, err := s.yahooClient.GetSecurityCountryAndExchange(symbol, yahooSymbolPtr)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to get country/exchange from Yahoo")
	}

	industry, err := s.yahooClient.GetSecurityIndustry(symbol, yahooSymbolPtr)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to get industry from Yahoo")
	}

	// Detect product type using Yahoo Finance with heuristics
	productType, err := s.detectProductType(symbol, yahooSymbolPtr, name)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to detect product type, using UNKNOWN")
		productType = ProductTypeUnknown
	}

	// Determine final yahoo symbol
	finalYahooSymbol := yahooSymbol
	if finalYahooSymbol == "" {
		finalYahooSymbol = symbol
	}

	// Create security
	security := Security{
		Symbol:             symbol,
		Name:               name,
		ProductType:        string(productType),
		Country:            stringValue(country),
		FullExchangeName:   stringValue(fullExchangeName),
		YahooSymbol:        finalYahooSymbol,
		Industry:           stringValue(industry),
		PriorityMultiplier: 1.0,
		MinLot:             minLot,
		Active:             true,
		AllowBuy:           allowBuy,
		AllowSell:          allowSell,
	}

	err = s.securityRepo.Create(security)
	if err != nil {
		return nil, fmt.Errorf("failed to create security in database: %w", err)
	}

	s.log.Info().
		Str("symbol", security.Symbol).
		Str("name", security.Name).
		Str("product_type", security.ProductType).
		Msg("Created security in database")

	// Publish domain event
	if s.eventManager != nil {
		s.eventManager.Emit(events.SecurityAdded, "universe", map[string]interface{}{
			"symbol": security.Symbol,
			"isin":   security.ISIN,
			"name":   security.Name,
		})
	}

	// Calculate initial score
	// Non-fatal - continue if this fails
	if s.scoreCalculator != nil {
		err = s.scoreCalculator.CalculateAndSaveScore(
			security.Symbol,
			security.YahooSymbol,
			security.Country,
			security.Industry,
		)
		if err != nil {
			s.log.Warn().
				Err(err).
				Str("symbol", security.Symbol).
				Msg("Failed to calculate initial score - continuing anyway")
		} else {
			s.log.Info().Str("symbol", security.Symbol).Msg("Calculated initial score")
		}
	}

	s.log.Info().
		Str("symbol", security.Symbol).
		Msg("Security creation complete")

	return &security, nil
}

// AddSecurityByIdentifier adds a security to the universe by symbol or ISIN
// Faithful translation from Python: app/modules/universe/services/security_setup_service.py -> add_security_by_identifier()
//
// This method:
// 1. Resolves the identifier to get all necessary symbols
// 2. Fetches data from Tradernet (symbol, name, currency, ISIN)
// 3. Fetches data from Yahoo Finance (country, exchange, industry)
// 4. Creates the security in the database
// 5. Publishes SecurityAdded event
// 6. Fetches historical price data (10 years initial seed)
// 7. Calculates and saves the initial security score
func (s *SecuritySetupService) AddSecurityByIdentifier(
	identifier string,
	minLot int,
	allowBuy bool,
	allowSell bool,
) (*Security, error) {
	identifier = strings.TrimSpace(strings.ToUpper(identifier))
	if identifier == "" {
		return nil, fmt.Errorf("identifier cannot be empty")
	}

	s.log.Info().Str("identifier", identifier).Msg("Adding security by identifier")

	// Check if security already exists
	existing, err := s.securityRepo.GetByIdentifier(identifier)
	if err != nil {
		return nil, fmt.Errorf("failed to check existing security: %w", err)
	}
	if existing != nil {
		return nil, fmt.Errorf("security already exists: %s", existing.Symbol)
	}

	// Step 1: Detect identifier type and resolve
	idType := s.symbolResolver.DetectType(identifier)
	symbolInfo, err := s.symbolResolver.Resolve(identifier)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve identifier: %w", err)
	}

	s.log.Debug().
		Str("identifier", identifier).
		Str("type", idType.String()).
		Interface("symbol_info", symbolInfo).
		Msg("Resolved identifier")

	// Step 2: Fetch data from Tradernet
	var tradernetSymbol string
	var tradernetName *string
	var currency *string
	var isin *string = symbolInfo.ISIN // Use ISIN from resolver if available

	if idType == IdentifierTypeTradernet {
		// Already have Tradernet symbol
		tradernetSymbol = identifier
		tradernetData, err := s.getTradernetData(tradernetSymbol)
		if err != nil {
			s.log.Warn().Err(err).Str("symbol", tradernetSymbol).Msg("Failed to get Tradernet data")
		} else if tradernetData != nil {
			// Prefer ISIN from resolver, fallback to API data
			if isin == nil || *isin == "" {
				isin = tradernetData.ISIN
			}
			currency = tradernetData.Currency
		}
	} else if idType == IdentifierTypeISIN {
		// Need to look up Tradernet symbol from ISIN
		isinVal := identifier // Use the provided ISIN
		isin = &isinVal
		lookupResult, err := s.getTradernetSymbolFromISIN(isinVal)
		if err != nil {
			return nil, fmt.Errorf("failed to lookup Tradernet symbol for ISIN: %w", err)
		}
		if lookupResult == nil {
			return nil, fmt.Errorf("could not find Tradernet symbol for ISIN: %s", isinVal)
		}
		tradernetSymbol = lookupResult.Symbol
		tradernetName = lookupResult.Name
		currency = lookupResult.Currency

		// Validate ISIN matches (warn if different, but use the one we looked up)
		if lookupResult.ISIN != nil && *lookupResult.ISIN != isinVal {
			s.log.Warn().
				Str("requested", isinVal).
				Str("got", *lookupResult.ISIN).
				Msg("ISIN mismatch, using requested ISIN")
		}
	} else {
		// Yahoo format - not supported for adding securities
		return nil, fmt.Errorf(
			"cannot add security with identifier '%s'. "+
				"Please provide a Tradernet symbol (e.g., AAPL.US) or ISIN (e.g., US0378331005)",
			identifier,
		)
	}

	if tradernetSymbol == "" {
		return nil, fmt.Errorf("could not resolve Tradernet symbol for: %s", identifier)
	}

	// Ensure we have ISIN - try to get it if we don't have it yet
	if isin == nil || *isin == "" {
		tradernetData, err := s.getTradernetData(tradernetSymbol)
		if err == nil && tradernetData != nil {
			isin = tradernetData.ISIN
		}
	}

	// Step 3: Fetch data from Yahoo Finance
	yahooSymbol := symbolInfo.YahooSymbol
	if yahooSymbol == "" && isin != nil && *isin != "" {
		yahooSymbol = *isin
	}
	if yahooSymbol == "" {
		yahooSymbol = tradernetSymbol
	}

	yahooSymbolPtr := &yahooSymbol
	country, fullExchangeName, err := s.yahooClient.GetSecurityCountryAndExchange(tradernetSymbol, yahooSymbolPtr)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", tradernetSymbol).Msg("Failed to get country/exchange from Yahoo")
	}

	industry, err := s.yahooClient.GetSecurityIndustry(tradernetSymbol, yahooSymbolPtr)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", tradernetSymbol).Msg("Failed to get industry from Yahoo")
	}

	// Get name - prefer Tradernet name, fallback to Yahoo Finance
	name := ""
	if tradernetName != nil && *tradernetName != "" {
		name = *tradernetName
	} else {
		yaName, err := s.getSecurityNameFromYahoo(tradernetSymbol, yahooSymbolPtr)
		if err == nil && yaName != nil {
			name = *yaName
		}
	}

	if name == "" {
		return nil, fmt.Errorf("could not determine security name for: %s", identifier)
	}

	// Detect product type using Yahoo Finance with heuristics
	productType, err := s.detectProductType(tradernetSymbol, yahooSymbolPtr, name)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", tradernetSymbol).Msg("Failed to detect product type, using UNKNOWN")
		productType = ProductTypeUnknown
	}

	// Step 4: Create security
	security := Security{
		Symbol:             tradernetSymbol,
		Name:               name,
		ProductType:        string(productType),
		Country:            stringValue(country),
		FullExchangeName:   stringValue(fullExchangeName),
		YahooSymbol:        yahooSymbol,
		ISIN:               stringValue(isin),
		Industry:           stringValue(industry),
		Currency:           stringValue(currency),
		PriorityMultiplier: 1.0,
		MinLot:             minLot,
		Active:             true,
		AllowBuy:           allowBuy,
		AllowSell:          allowSell,
	}

	err = s.securityRepo.Create(security)
	if err != nil {
		return nil, fmt.Errorf("failed to create security in database: %w", err)
	}

	s.log.Info().
		Str("symbol", security.Symbol).
		Str("name", security.Name).
		Str("product_type", security.ProductType).
		Msg("Created security in database")

	// Step 5: Publish domain event
	if s.eventManager != nil {
		s.eventManager.Emit(events.SecurityAdded, "universe", map[string]interface{}{
			"symbol": security.Symbol,
			"isin":   security.ISIN,
			"name":   security.Name,
		})
	}

	// Step 6: Fetch historical data (10 years initial seed)
	// Non-fatal - continue if this fails
	if s.historicalSync != nil {
		err = s.historicalSync.SyncHistoricalPrices(security.Symbol)
		if err != nil {
			s.log.Warn().
				Err(err).
				Str("symbol", security.Symbol).
				Msg("Failed to fetch historical data - continuing anyway")
		} else {
			s.log.Info().Str("symbol", security.Symbol).Msg("Fetched historical data")
		}
	}

	// Step 7: Calculate initial score
	// Non-fatal - continue if this fails
	if s.scoreCalculator != nil {
		err = s.scoreCalculator.CalculateAndSaveScore(
			security.Symbol,
			security.YahooSymbol,
			security.Country,
			security.Industry,
		)
		if err != nil {
			s.log.Warn().
				Err(err).
				Str("symbol", security.Symbol).
				Msg("Failed to calculate initial score - continuing anyway")
		} else {
			s.log.Info().Str("symbol", security.Symbol).Msg("Calculated initial score")
		}
	}

	s.log.Info().
		Str("symbol", security.Symbol).
		Str("identifier", identifier).
		Msg("Security setup complete")

	return &security, nil
}

// TradernetData represents data fetched from Tradernet API
type TradernetData struct {
	Currency *string
	ISIN     *string
}

// getTradernetData gets currency and ISIN from Tradernet for a symbol
// Faithful translation from Python: SecuritySetupService._get_tradernet_data()
func (s *SecuritySetupService) getTradernetData(symbol string) (*TradernetData, error) {
	if s.tradernetClient == nil {
		s.log.Warn().Msg("Tradernet client not available, skipping data fetch")
		return nil, nil
	}

	if !s.tradernetClient.IsConnected() {
		s.log.Warn().Msg("Tradernet not connected, skipping data fetch")
		return nil, nil
	}

	// Use FindSymbol to get security info
	securities, err := s.tradernetClient.FindSymbol(symbol, nil)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to get Tradernet data")
		return nil, err
	}

	if len(securities) == 0 {
		s.log.Debug().Str("symbol", symbol).Msg("No results from Tradernet FindSymbol")
		return nil, nil
	}

	// Use first result
	security := securities[0]

	return &TradernetData{
		Currency: security.Currency,
		ISIN:     security.ISIN,
	}, nil
}

// TradernetLookupResult represents the result of looking up a Tradernet symbol by ISIN
type TradernetLookupResult struct {
	Symbol   string
	Name     *string
	Currency *string
	ISIN     *string
}

// getTradernetSymbolFromISIN gets Tradernet symbol, name, and currency from ISIN
// Faithful translation from Python: SecuritySetupService._get_tradernet_symbol_from_isin()
func (s *SecuritySetupService) getTradernetSymbolFromISIN(isin string) (*TradernetLookupResult, error) {
	if s.tradernetClient == nil {
		return nil, fmt.Errorf("Tradernet client not available")
	}

	if !s.tradernetClient.IsConnected() {
		return nil, fmt.Errorf("Tradernet not connected")
	}

	securities, err := s.tradernetClient.FindSymbol(isin, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to lookup ISIN via FindSymbol: %w", err)
	}

	if len(securities) == 0 {
		s.log.Warn().Str("isin", isin).Msg("No results from find_symbol for ISIN")
		return nil, nil
	}

	// Use first result (typically the primary exchange listing)
	instrument := securities[0]

	if instrument.Symbol == "" {
		s.log.Warn().Str("isin", isin).Msg("No symbol in find_symbol result for ISIN")
		return nil, nil
	}

	return &TradernetLookupResult{
		Symbol:   instrument.Symbol,
		Name:     instrument.Name,
		Currency: instrument.Currency,
		ISIN:     instrument.ISIN,
	}, nil
}

// getSecurityNameFromYahoo gets security name from Yahoo Finance
// Faithful translation from Python: SecuritySetupService._get_security_name_from_yahoo()
func (s *SecuritySetupService) getSecurityNameFromYahoo(symbol string, yahooSymbol *string) (*string, error) {
	if s.yahooClient == nil {
		return nil, fmt.Errorf("Yahoo client not available")
	}

	name, err := s.yahooClient.GetQuoteName(symbol, yahooSymbol)
	if err != nil {
		return nil, fmt.Errorf("failed to get quote name from Yahoo: %w", err)
	}

	return name, nil
}

// detectProductType detects product type using Yahoo Finance quoteType
// Faithful translation from Python: yahoo.get_product_type()
func (s *SecuritySetupService) detectProductType(symbol string, yahooSymbol *string, name string) (ProductType, error) {
	if s.yahooClient == nil {
		// Fallback to name heuristics if Yahoo client not available
		s.log.Debug().Str("symbol", symbol).Msg("Yahoo client not available, using name heuristics")
		return s.detectProductTypeFromName(name), nil
	}

	// Get quoteType from Yahoo Finance
	quoteType, err := s.yahooClient.GetQuoteType(symbol, yahooSymbol)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to get quote type from Yahoo, using name heuristics")
		return s.detectProductTypeFromName(name), nil
	}

	// Get name from Yahoo if not provided (matching Python behavior)
	yahooName := name
	if yahooName == "" {
		if namePtr, err := s.yahooClient.GetQuoteName(symbol, yahooSymbol); err == nil && namePtr != nil {
			yahooName = *namePtr
		}
	}

	// Use FromYahooQuoteType which matches Python's ProductType.from_yahoo_quote_type()
	return FromYahooQuoteType(quoteType, yahooName), nil
}

// detectProductTypeFromName uses heuristics based on name as fallback
func (s *SecuritySetupService) detectProductTypeFromName(name string) ProductType {
	nameUpper := strings.ToUpper(name)

	// ETF indicators
	if strings.Contains(nameUpper, "ETF") {
		return ProductTypeETF
	}

	// ETC indicators
	etcIndicators := []string{
		"ETC", "COMMODITY", "COMMODITIES", "GOLD", "SILVER",
		"PLATINUM", "PALLADIUM", "COPPER", "OIL", "CRUDE",
	}
	for _, indicator := range etcIndicators {
		if strings.Contains(nameUpper, indicator) {
			return ProductTypeETC
		}
	}

	// Default to EQUITY
	return ProductTypeEquity
}

// RefreshSecurityData triggers full data refresh for a security
// Faithful translation from Python: app/modules/universe/api/securities.py -> refresh_security_data()
//
// This method:
// 1. Syncs historical prices from Yahoo Finance
// 2. Recalculates security score
//
// This is a full pipeline refresh that bypasses last_synced checks.
func (s *SecuritySetupService) RefreshSecurityData(symbol string) error {
	s.log.Info().Str("symbol", symbol).Msg("Refreshing security data")

	// Step 1: Sync historical prices
	if s.historicalSync != nil {
		err := s.historicalSync.SyncHistoricalPrices(symbol)
		if err != nil {
			return fmt.Errorf("failed to sync historical prices: %w", err)
		}
		s.log.Info().Str("symbol", symbol).Msg("Synced historical prices")
	} else {
		s.log.Warn().Msg("Historical sync service not available, skipping price sync")
	}

	// Step 2: Recalculate score
	// Get security details for score calculation
	security, err := s.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to get security: %w", err)
	}
	if security == nil {
		return fmt.Errorf("security not found: %s", symbol)
	}

	if s.scoreCalculator != nil {
		err = s.scoreCalculator.CalculateAndSaveScore(
			security.Symbol,
			security.YahooSymbol,
			security.Country,
			security.Industry,
		)
		if err != nil {
			return fmt.Errorf("failed to recalculate score: %w", err)
		}
		s.log.Info().Str("symbol", symbol).Msg("Recalculated security score")
	} else {
		s.log.Warn().Msg("Score calculator not available, skipping score recalculation")
	}

	s.log.Info().Str("symbol", symbol).Msg("Security data refresh complete")
	return nil
}

// Helper function to get string value from pointer
func stringValue(ptr *string) string {
	if ptr == nil {
		return ""
	}
	return *ptr
}
