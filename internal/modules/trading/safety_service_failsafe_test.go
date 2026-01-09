package trading

import (
	"os"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/database"
	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// createTestDB creates a temporary test database with schema
func createTestDB(t *testing.T, name string) (*database.DB, func()) {
	t.Helper()

	// Create temporary file
	tmpFile, err := os.CreateTemp("", "test_"+name+"_*.db")
	if err != nil {
		t.Fatalf("Failed to create temp file: %v", err)
	}
	tmpPath := tmpFile.Name()
	_ = tmpFile.Close()

	// Create database
	db, err := database.New(database.Config{
		Path:    tmpPath,
		Profile: database.ProfileStandard,
		Name:    name,
	})
	if err != nil {
		_ = os.Remove(tmpPath)
		t.Fatalf("Failed to create test database: %v", err)
	}

	// Migrate schema
	err = db.Migrate()
	if err != nil {
		_ = db.Close()
		_ = os.Remove(tmpPath)
		t.Fatalf("Failed to migrate database: %v", err)
	}

	// Return cleanup function
	cleanup := func() {
		_ = db.Close()
		_ = os.Remove(tmpPath)
	}

	return db, cleanup
}

// setupLiveTradingMode sets up dummy credentials and enables live trading mode for testing
func setupLiveTradingMode(t *testing.T, settingsService *settings.Service) {
	t.Helper()

	// Set dummy API credentials (required for live mode)
	_, err := settingsService.Set("tradernet_api_key", "test_key")
	assert.NoError(t, err)
	_, err = settingsService.Set("tradernet_api_secret", "test_secret")
	assert.NoError(t, err)

	// Now we can set trading mode to live
	_, err = settingsService.Set("trading_mode", "live")
	assert.NoError(t, err)
}

// Test HARD Fail-Safe: Security validation blocks when repository unavailable
func TestValidateTrade_HardFailSafe_BlocksWhenSecurityRepoUnavailable(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create config DB for settings service
	configDB, cleanupConfig := createTestDB(t, "config")
	defer cleanupConfig()

	// Create settings service and set trading mode to "live" so we can test security repo fail-safe
	settingsService := settings.NewService(settings.NewRepository(configDB.Conn(), log), log)
	setupLiveTradingMode(t, settingsService)

	// Create service with nil securityRepo
	service := &TradeSafetyService{
		tradeRepo:          nil,
		positionRepo:       nil,
		securityRepo:       nil, // Security repo unavailable
		settingsService:    settingsService,
		marketHoursService: nil,
		log:                log,
	}

	// HARD fail-safe should block the trade
	err := service.ValidateTrade("AAPL", "BUY", 10.0)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "security repository not available")
}

// Test SOFT Fail-Safe: Market hours allows when service unavailable
func TestValidateTrade_SoftFailSafe_AllowsWhenMarketHoursUnavailable(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test databases
	universeDB, cleanupUniverse := createTestDB(t, "universe")
	defer cleanupUniverse()

	ledgerDB, cleanupLedger := createTestDB(t, "ledger")
	defer cleanupLedger()

	portfolioDB, cleanupPortfolio := createTestDB(t, "portfolio")
	defer cleanupPortfolio()

	configDB, cleanupConfig := createTestDB(t, "config")
	defer cleanupConfig()

	// Create repositories
	tradeRepo := NewTradeRepository(ledgerDB.Conn(), log)
	securityRepo := universe.NewSecurityRepository(universeDB.Conn(), log)
	positionRepo := portfolio.NewPositionRepository(portfolioDB.Conn(), universeDB.Conn(), log)
	settingsService := settings.NewService(settings.NewRepository(configDB.Conn(), log), log)

	// Set trading mode to "live" so we can test market hours fail-safe
	setupLiveTradingMode(t, settingsService)

	// Insert test security
	security := universe.Security{
		Symbol:           "AAPL",
		Name:             "Apple Inc.",
		ProductType:      "Stock",
		Currency:         "USD",
		ISIN:             "US0378331005",
		FullExchangeName: "NASDAQ",
	}
	err := securityRepo.Create(security)
	assert.NoError(t, err)

	// Insert test position (so SELL validation passes)
	now := time.Now().Unix()
	position := portfolio.Position{
		ISIN:         "US0378331005",
		Symbol:       "AAPL",
		Quantity:     100.0,
		AvgPrice:     150.0,
		Currency:     "USD",
		CurrentPrice: 155.0,
		LastUpdated:  &now,
	}
	err = positionRepo.Upsert(position)
	assert.NoError(t, err)

	// Create service with nil marketHoursService (SOFT fail-safe)
	service := &TradeSafetyService{
		tradeRepo:          tradeRepo,
		positionRepo:       positionRepo,
		securityRepo:       securityRepo,
		settingsService:    settingsService,
		marketHoursService: nil, // Market hours service unavailable
		log:                log,
	}

	// SOFT fail-safe should allow the trade (market hours is advisory)
	err = service.ValidateTrade("AAPL", "SELL", 10.0)

	// Should not error - SOFT fail-safe allows trade
	assert.NoError(t, err)
}

// Test HARD Fail-Safe: Trade repo blocks when unavailable
func TestValidateTrade_HardFailSafe_BlocksWhenTradeRepoUnavailable(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test databases
	universeDB, cleanupUniverse := createTestDB(t, "universe")
	defer cleanupUniverse()

	portfolioDB, cleanupPortfolio := createTestDB(t, "portfolio")
	defer cleanupPortfolio()

	configDB, cleanupConfig := createTestDB(t, "config")
	defer cleanupConfig()

	// Create repositories
	securityRepo := universe.NewSecurityRepository(universeDB.Conn(), log)
	positionRepo := portfolio.NewPositionRepository(portfolioDB.Conn(), universeDB.Conn(), log)
	settingsService := settings.NewService(settings.NewRepository(configDB.Conn(), log), log)

	// Set trading mode to "live" so we can test trade repo fail-safe
	setupLiveTradingMode(t, settingsService)

	// Insert test security
	security := universe.Security{
		Symbol:           "AAPL",
		Name:             "Apple Inc.",
		ProductType:      "Stock",
		Currency:         "USD",
		ISIN:             "US0378331005",
		FullExchangeName: "NASDAQ",
	}
	err := securityRepo.Create(security)
	assert.NoError(t, err)

	// Insert test position
	now := time.Now().Unix()
	position := portfolio.Position{
		ISIN:        "US0378331005",
		Symbol:      "AAPL",
		Quantity:    100.0,
		AvgPrice:    150.0,
		Currency:    "USD",
		LastUpdated: &now,
	}
	err = positionRepo.Upsert(position)
	assert.NoError(t, err)

	// Create service with nil tradeRepo
	service := &TradeSafetyService{
		tradeRepo:          nil, // Trade repo unavailable
		positionRepo:       positionRepo,
		securityRepo:       securityRepo,
		settingsService:    settingsService,
		marketHoursService: nil,
		log:                log,
	}

	// HARD fail-safe should block SELL orders (pending order check needs tradeRepo)
	err = service.ValidateTrade("AAPL", "SELL", 10.0)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "trade repository not available")
}

// Test Market Hours Check with Service Available
func TestValidateTrade_WithMarketHoursService(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test databases
	universeDB, cleanupUniverse := createTestDB(t, "universe")
	defer cleanupUniverse()

	ledgerDB, cleanupLedger := createTestDB(t, "ledger")
	defer cleanupLedger()

	portfolioDB, cleanupPortfolio := createTestDB(t, "portfolio")
	defer cleanupPortfolio()

	configDB, cleanupConfig := createTestDB(t, "config")
	defer cleanupConfig()

	// Create repositories
	tradeRepo := NewTradeRepository(ledgerDB.Conn(), log)
	securityRepo := universe.NewSecurityRepository(universeDB.Conn(), log)
	positionRepo := portfolio.NewPositionRepository(portfolioDB.Conn(), universeDB.Conn(), log)
	settingsService := settings.NewService(settings.NewRepository(configDB.Conn(), log), log)
	marketHoursService := market_hours.NewMarketHoursService()

	// Insert test security
	security := universe.Security{
		Symbol:           "AAPL",
		Name:             "Apple Inc.",
		ProductType:      "Stock",
		Currency:         "USD",
		ISIN:             "US0378331005",
		FullExchangeName: "NASDAQ",
	}
	err := securityRepo.Create(security)
	assert.NoError(t, err)

	// Insert test position
	now := time.Now().Unix()
	position := portfolio.Position{
		ISIN:        "US0378331005",
		Symbol:      "AAPL",
		Quantity:    100.0,
		AvgPrice:    150.0,
		Currency:    "USD",
		LastUpdated: &now,
	}
	err = positionRepo.Upsert(position)
	assert.NoError(t, err)

	// Create service
	service := &TradeSafetyService{
		tradeRepo:          tradeRepo,
		positionRepo:       positionRepo,
		securityRepo:       securityRepo,
		settingsService:    settingsService,
		marketHoursService: marketHoursService,
		log:                log,
	}

	// Try to trade - this tests that the service works with all dependencies
	err = service.ValidateTrade("AAPL", "BUY", 10.0)

	// The validation may pass or fail depending on market hours, but it shouldn't panic
	// The important thing is that the fail-safe pattern is in place
	if err != nil {
		t.Logf("Trade validation returned error (expected if market hours or other checks fail): %v", err)
	}
}

// Test Position Validation Blocks Insufficient Quantity
func TestValidateTrade_BlocksInsufficientQuantity(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test databases
	universeDB, cleanupUniverse := createTestDB(t, "universe")
	defer cleanupUniverse()

	ledgerDB, cleanupLedger := createTestDB(t, "ledger")
	defer cleanupLedger()

	portfolioDB, cleanupPortfolio := createTestDB(t, "portfolio")
	defer cleanupPortfolio()

	configDB, cleanupConfig := createTestDB(t, "config")
	defer cleanupConfig()

	// Create repositories
	tradeRepo := NewTradeRepository(ledgerDB.Conn(), log)
	securityRepo := universe.NewSecurityRepository(universeDB.Conn(), log)
	positionRepo := portfolio.NewPositionRepository(portfolioDB.Conn(), universeDB.Conn(), log)
	settingsService := settings.NewService(settings.NewRepository(configDB.Conn(), log), log)

	// Set trading mode to "live" so we can test position validation
	setupLiveTradingMode(t, settingsService)

	// Insert test security
	security := universe.Security{
		Symbol:           "AAPL",
		Name:             "Apple Inc.",
		ProductType:      "Stock",
		Currency:         "USD",
		ISIN:             "US0378331005",
		FullExchangeName: "NASDAQ",
	}
	err := securityRepo.Create(security)
	assert.NoError(t, err)

	// Insert test position with only 10 shares
	now := time.Now().Unix()
	position := portfolio.Position{
		ISIN:        "US0378331005",
		Symbol:      "AAPL",
		Quantity:    10.0,
		AvgPrice:    150.0,
		Currency:    "USD",
		LastUpdated: &now,
	}
	err = positionRepo.Upsert(position)
	assert.NoError(t, err)

	// Create service
	service := &TradeSafetyService{
		tradeRepo:          tradeRepo,
		positionRepo:       positionRepo,
		securityRepo:       securityRepo,
		settingsService:    settingsService,
		marketHoursService: nil,
		log:                log,
	}

	// Try to sell 15 shares when only 10 available
	err = service.ValidateTrade("AAPL", "SELL", 15.0)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "exceeds position")
}

// Test Position Validation Allows Valid Quantity
func TestValidateTrade_AllowsValidQuantity(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test databases
	universeDB, cleanupUniverse := createTestDB(t, "universe")
	defer cleanupUniverse()

	ledgerDB, cleanupLedger := createTestDB(t, "ledger")
	defer cleanupLedger()

	portfolioDB, cleanupPortfolio := createTestDB(t, "portfolio")
	defer cleanupPortfolio()

	configDB, cleanupConfig := createTestDB(t, "config")
	defer cleanupConfig()

	// Create repositories
	tradeRepo := NewTradeRepository(ledgerDB.Conn(), log)
	securityRepo := universe.NewSecurityRepository(universeDB.Conn(), log)
	positionRepo := portfolio.NewPositionRepository(portfolioDB.Conn(), universeDB.Conn(), log)
	settingsService := settings.NewService(settings.NewRepository(configDB.Conn(), log), log)

	// Set trading mode to "live" so we can test position validation
	setupLiveTradingMode(t, settingsService)

	// Insert test security
	security := universe.Security{
		Symbol:           "AAPL",
		Name:             "Apple Inc.",
		ProductType:      "Stock",
		Currency:         "USD",
		ISIN:             "US0378331005",
		FullExchangeName: "NASDAQ",
	}
	err := securityRepo.Create(security)
	assert.NoError(t, err)

	// Insert test position with 100 shares
	now := time.Now().Unix()
	position := portfolio.Position{
		ISIN:        "US0378331005",
		Symbol:      "AAPL",
		Quantity:    100.0,
		AvgPrice:    150.0,
		Currency:    "USD",
		LastUpdated: &now,
	}
	err = positionRepo.Upsert(position)
	assert.NoError(t, err)

	// Create service
	service := &TradeSafetyService{
		tradeRepo:          tradeRepo,
		positionRepo:       positionRepo,
		securityRepo:       securityRepo,
		settingsService:    settingsService,
		marketHoursService: nil,
		log:                log,
	}

	// Sell 10 shares when 100 available - should pass
	err = service.ValidateTrade("AAPL", "SELL", 10.0)

	assert.NoError(t, err)
}

// Test Security Not Found
func TestValidateTrade_BlocksUnknownSecurity(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test databases
	universeDB, cleanupUniverse := createTestDB(t, "universe")
	defer cleanupUniverse()

	configDB, cleanupConfig := createTestDB(t, "config")
	defer cleanupConfig()

	// Create repositories
	securityRepo := universe.NewSecurityRepository(universeDB.Conn(), log)
	settingsService := settings.NewService(settings.NewRepository(configDB.Conn(), log), log)

	// Set trading mode to "live" so we can test security validation
	setupLiveTradingMode(t, settingsService)

	// Create service
	service := &TradeSafetyService{
		tradeRepo:          nil,
		positionRepo:       nil,
		securityRepo:       securityRepo,
		settingsService:    settingsService,
		marketHoursService: nil,
		log:                log,
	}

	// Try to trade unknown security
	err := service.ValidateTrade("UNKNOWN", "BUY", 10.0)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "security not found")
}
