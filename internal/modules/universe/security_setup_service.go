package universe

import (
	"fmt"
	"strings"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/events"
	"github.com/rs/zerolog"
)

// SecuritySetupService handles comprehensive security onboarding.
// Uses Tradernet as the single source for security metadata.
type SecuritySetupService struct {
	symbolResolver  *SymbolResolver
	securityRepo    *SecurityRepository
	brokerClient    domain.BrokerClient
	historicalSync  *HistoricalSyncService
	eventManager    *events.Manager
	scoreCalculator ScoreCalculator // Interface for score calculation
	log             zerolog.Logger
}

// ScoreCalculator interface for calculating and saving security scores
// Implemented by UniverseHandlers.calculateAndSaveScore
type ScoreCalculator interface {
	CalculateAndSaveScore(symbol string, geography string, industry string) error
}

// NewSecuritySetupService creates a new security setup service
func NewSecuritySetupService(
	symbolResolver *SymbolResolver,
	securityRepo *SecurityRepository,
	brokerClient domain.BrokerClient,
	historicalSync *HistoricalSyncService,
	eventManager *events.Manager,
	scoreCalculator ScoreCalculator,
	log zerolog.Logger,
) *SecuritySetupService {
	return &SecuritySetupService{
		symbolResolver:  symbolResolver,
		securityRepo:    securityRepo,
		brokerClient:    brokerClient,
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

// CreateSecurity creates a security with explicit symbol and name.
// This is the primary endpoint handler for POST /api/securities.
//
// This method:
// 1. Validates symbol is unique
// 2. Auto-detects product type from name heuristics
// 3. Creates the security in the database (requires ISIN)
// 4. Publishes SecurityAdded event
// 5. Calculates and saves the initial security score
//
// Note: User-configurable fields (allow_buy, allow_sell, min_lot, priority_multiplier)
// are stored in security_overrides table, not in securities table. Use OverrideRepository
// to set these values after creation.
//
// Unlike AddSecurityByIdentifier, this does NOT:
// - Fetch historical price data (handled by background sync jobs)
// - Fetch Tradernet metadata (currency, ISIN, geography, industry) - ISIN must be provided
// - Resolve identifiers (symbol is already provided)
func (s *SecuritySetupService) CreateSecurity(
	symbol string,
	name string,
	isin string, // Required: PRIMARY KEY after migration 030
) (*Security, error) {
	symbol = strings.TrimSpace(strings.ToUpper(symbol))
	if symbol == "" {
		return nil, fmt.Errorf("symbol cannot be empty")
	}
	if name == "" {
		return nil, fmt.Errorf("name cannot be empty")
	}
	isin = strings.TrimSpace(strings.ToUpper(isin))
	if isin == "" {
		return nil, fmt.Errorf("ISIN is required (PRIMARY KEY after migration 030). Use AddSecurityByIdentifier to automatically fetch ISIN from Tradernet")
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

	// Metadata will be populated by metadata enricher after creation
	var country, fullExchangeName, industry *string
	var productType ProductType

	// Detect product type from symbol pattern
	if productType == "" {
		var err error
		productType, err = s.detectProductType(symbol, name)
		if err != nil {
			s.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to detect product type, using UNKNOWN")
			productType = ProductTypeUnknown
		}
	}

	// Create security (ISIN is required as PRIMARY KEY)
	// Note: allow_buy, allow_sell, min_lot, priority_multiplier are stored in security_overrides
	// Defaults will be applied at read time: allow_buy=true, allow_sell=true, min_lot=1, priority_multiplier=1.0
	security := Security{
		ISIN:             isin,
		Symbol:           symbol,
		Name:             name,
		ProductType:      string(productType),
		Geography:        stringValue(country), // Map broker country to geography
		FullExchangeName: stringValue(fullExchangeName),
		Industry:         stringValue(industry),
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
			security.Geography,
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
//
// This method:
// 1. Resolves the identifier to get all necessary symbols
// 2. Fetches data from Tradernet (symbol, name, currency, ISIN)
// 3. Fetches metadata from Tradernet (country, exchange, industry)
// 4. Creates the security in the database
// 5. Publishes SecurityAdded event
//
// Note: User-configurable fields (allow_buy, allow_sell, min_lot, priority_multiplier)
// are stored in security_overrides table, not in securities table. Use OverrideRepository
// to set these values after creation.
//
// Historical data sync and score calculation are handled asynchronously by the
// idle processor, which detects securities with last_synced = NULL.
func (s *SecuritySetupService) AddSecurityByIdentifier(
	identifier string,
) (*Security, error) {
	identifier = strings.TrimSpace(strings.ToUpper(identifier))
	if identifier == "" {
		return nil, fmt.Errorf("identifier cannot be empty")
	}

	// Reject index symbols - indices are managed automatically via IndexSyncService
	if strings.HasSuffix(identifier, ".IDX") {
		return nil, fmt.Errorf("cannot add index %s via this endpoint; indices are managed automatically", identifier)
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
	isin := symbolInfo.ISIN // Use ISIN from resolver if available

	if idType == IdentifierTypeTradernet {
		// Already have Tradernet symbol
		tradernetSymbol = identifier

		// Check if Tradernet is connected before trying to fetch data
		if s.brokerClient == nil || !s.brokerClient.IsConnected() {
			return nil, fmt.Errorf("tradernet client is not connected. Cannot fetch ISIN for symbol: %s. Please connect to Tradernet first", tradernetSymbol)
		}

		tradernetData, err := s.getTradernetData(tradernetSymbol)
		if err != nil {
			return nil, fmt.Errorf("failed to fetch data from Tradernet API for symbol: %s: %w", tradernetSymbol, err)
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

		// Check if Tradernet is connected before trying to lookup
		// Note: We check here instead of inside getTradernetSymbolFromISIN to avoid
		// redundant checks and ensure consistent error messages
		if s.brokerClient == nil || !s.brokerClient.IsConnected() {
			return nil, fmt.Errorf("tradernet client is not connected. Cannot lookup Tradernet symbol for ISIN: %s. Please connect to Tradernet first", isinVal)
		}

		lookupResult, err := s.getTradernetSymbolFromISIN(isinVal)
		if err != nil {
			// Check if error is about SDK client not initialized or network error
			// This can happen if FindSymbol fails for reasons other than connection
			if strings.Contains(err.Error(), "SDK client not initialized") ||
				strings.Contains(err.Error(), "client not available") {
				return nil, fmt.Errorf("tradernet client is not available. Cannot lookup Tradernet symbol for ISIN: %s", isinVal)
			}
			return nil, fmt.Errorf("failed to lookup Tradernet symbol for ISIN: %w", err)
		}
		if lookupResult == nil {
			return nil, fmt.Errorf("could not find Tradernet symbol for ISIN: %s. The ISIN may not exist in Tradernet's database, or the security may not have a Tradernet symbol", isinVal)
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
		// Generic format - not supported for adding securities
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
		// Check if Tradernet is connected before trying to fetch ISIN
		if s.brokerClient == nil || !s.brokerClient.IsConnected() {
			return nil, fmt.Errorf("tradernet client is not connected. Cannot fetch ISIN for symbol: %s. Please connect to Tradernet first", tradernetSymbol)
		}

		tradernetData, err := s.getTradernetData(tradernetSymbol)
		if err != nil {
			return nil, fmt.Errorf("failed to fetch ISIN from Tradernet API for symbol: %s: %w", tradernetSymbol, err)
		}
		if tradernetData != nil && tradernetData.ISIN != nil && *tradernetData.ISIN != "" {
			isin = tradernetData.ISIN
		}
	}

	// Validate ISIN is present (required for PRIMARY KEY after migration)
	if isin == nil || *isin == "" {
		return nil, fmt.Errorf("ISIN is required but could not be obtained from Tradernet API for symbol: %s. Please ensure the security exists in Tradernet and has an ISIN", tradernetSymbol)
	}

	// Metadata (country, exchange, industry) will be populated by metadata enricher after creation
	var country, fullExchangeName, industry *string
	var productType = ProductTypeUnknown

	// Get name - prefer Tradernet name, then symbol
	name := ""
	if tradernetName != nil && *tradernetName != "" {
		name = *tradernetName
	} else {
		name = tradernetSymbol
		s.log.Warn().Str("symbol", tradernetSymbol).Msg("Using symbol as name fallback")
	}

	// Final ISIN validation (double-check before creating security)
	// ISIN is required as PRIMARY KEY after migration
	// Note: isin is already validated above, but this is a safety check
	if *isin == "" {
		return nil, fmt.Errorf("ISIN is required but missing for security: %s (symbol: %s). Cannot create security without ISIN", name, tradernetSymbol)
	}

	// Detect product type using name heuristics
	detectedType, err := s.detectProductType(tradernetSymbol, name)
	if err != nil {
		s.log.Warn().Err(err).Str("symbol", tradernetSymbol).Msg("Failed to detect product type, using UNKNOWN")
		productType = ProductTypeUnknown
	} else {
		productType = detectedType
	}

	// Step 4: Create security
	// Note: allow_buy, allow_sell, min_lot, priority_multiplier are stored in security_overrides
	// Defaults will be applied at read time: allow_buy=true, allow_sell=true, min_lot=1, priority_multiplier=1.0
	security := Security{
		Symbol:           tradernetSymbol,
		Name:             name,
		ProductType:      string(productType),
		Geography:        stringValue(country),
		FullExchangeName: stringValue(fullExchangeName),
		ISIN:             stringValue(isin),
		Industry:         stringValue(industry),
		Currency:         stringValue(currency),
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

	// Historical data sync and score calculation are handled asynchronously
	// by the idle processor, which detects securities with last_synced = NULL.
	// This allows the API to return immediately instead of blocking for 20+ seconds.

	s.log.Info().
		Str("symbol", security.Symbol).
		Str("identifier", identifier).
		Msg("Security setup complete")

	return &security, nil
}

// TradernetData represents data fetched from Tradernet API
// Includes metadata for geography, industry, and exchange information
type TradernetData struct {
	Currency     *string
	ISIN         *string
	Country      *string // Issuer country code -> maps to Geography
	Sector       *string // Sector/industry code -> maps to Industry
	Market       *string // Market code (e.g., "FIX", "EU", "US")
	ExchangeName *string // Full exchange name
}

// getTradernetData gets currency and ISIN from Tradernet for a symbol
// Faithful translation from Python: SecuritySetupService._get_tradernet_data()
func (s *SecuritySetupService) getTradernetData(symbol string) (*TradernetData, error) {
	if s.brokerClient == nil {
		s.log.Warn().Msg("Tradernet client not available, skipping data fetch")
		return nil, nil
	}

	if !s.brokerClient.IsConnected() {
		s.log.Warn().Msg("Tradernet not connected, skipping data fetch")
		return nil, nil
	}

	// Use FindSymbol to get security info
	securities, err := s.brokerClient.FindSymbol(symbol, nil)
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
		Currency:     security.Currency,
		ISIN:         security.ISIN,
		Country:      security.Country,      // Issuer country code -> Geography
		Sector:       security.Sector,       // Sector/industry code -> Industry
		Market:       security.Market,       // Market code for region mapping
		ExchangeName: security.ExchangeName, // Full exchange name
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
// Note: Connection check should be done by caller to avoid redundant expensive checks.
// IsConnected() makes a network call (UserInfo), so calling it twice can cause false negatives.
func (s *SecuritySetupService) getTradernetSymbolFromISIN(isin string) (*TradernetLookupResult, error) {
	if s.brokerClient == nil {
		return nil, fmt.Errorf("tradernet client not available")
	}

	// Trust caller's connection check - IsConnected() makes expensive network calls
	// and can fail intermittently even when Tradernet is functionally connected.
	// Instead, just try the operation and handle errors properly.

	securities, err := s.brokerClient.FindSymbol(isin, nil)
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

// detectProductType detects product type using name heuristics
func (s *SecuritySetupService) detectProductType(symbol string, name string) (ProductType, error) {
	s.log.Debug().Str("symbol", symbol).Msg("Using name heuristics for product type detection")
	return s.detectProductTypeFromName(name), nil
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
//
// This method:
// 1. Syncs historical prices from Tradernet
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
			security.Geography,
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
