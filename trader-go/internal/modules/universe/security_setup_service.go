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

	// The Yahoo client's getQuoteInfo is not exposed, but we can use GetFundamentalData
	// which internally calls getQuoteInfo and can extract the name
	// Actually, looking at the Go client, there's no direct method to get just the name.
	// We need to add this functionality or use a workaround.
	// For now, let's return nil and rely on Tradernet name
	// TODO: Add GetQuoteName method to Yahoo client or extract from existing calls
	s.log.Debug().Str("symbol", symbol).Msg("Yahoo name fetch not yet implemented, using Tradernet name")
	return nil, nil
}

// detectProductType detects product type using Yahoo Finance quoteType
// Faithful translation from Python: yahoo.get_product_type()
func (s *SecuritySetupService) detectProductType(symbol string, yahooSymbol *string, name string) (ProductType, error) {
	// For now, we don't have a direct quoteType endpoint in the Go Yahoo client
	// We can infer from the name as a fallback
	// TODO: Add GetQuoteType method to Yahoo client
	s.log.Debug().Str("symbol", symbol).Msg("Product type detection using name heuristics")

	// Use heuristics based on name
	nameUpper := strings.ToUpper(name)

	// ETF indicators
	if strings.Contains(nameUpper, "ETF") {
		return ProductTypeETF, nil
	}

	// ETC indicators
	etcIndicators := []string{
		"ETC", "COMMODITY", "COMMODITIES", "GOLD", "SILVER",
		"PLATINUM", "PALLADIUM", "COPPER", "OIL", "CRUDE",
	}
	for _, indicator := range etcIndicators {
		if strings.Contains(nameUpper, indicator) {
			return ProductTypeETC, nil
		}
	}

	// Default to EQUITY for now
	return ProductTypeEquity, nil
}

// Helper function to get string value from pointer
func stringValue(ptr *string) string {
	if ptr == nil {
		return ""
	}
	return *ptr
}
