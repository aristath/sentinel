package services

import (
	"errors"
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/pkg/logger"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Mock implementations for testing OpportunityContextBuilder

type ocbMockPositionRepository struct {
	positions []portfolio.Position
	err       error
}

func (m *ocbMockPositionRepository) GetAll() ([]portfolio.Position, error) {
	return m.positions, m.err
}

type ocbMockSecurityRepository struct {
	securities []universe.Security
	byISIN     map[string]*universe.Security
	bySymbol   map[string]*universe.Security
	err        error
}

func (m *ocbMockSecurityRepository) GetAllActive() ([]universe.Security, error) {
	return m.securities, m.err
}

func (m *ocbMockSecurityRepository) GetByISIN(isin string) (*universe.Security, error) {
	if m.byISIN == nil {
		return nil, errors.New("not found")
	}
	if sec, ok := m.byISIN[isin]; ok {
		return sec, nil
	}
	return nil, errors.New("not found")
}

func (m *ocbMockSecurityRepository) GetBySymbol(symbol string) (*universe.Security, error) {
	if m.bySymbol == nil {
		return nil, errors.New("not found")
	}
	if sec, ok := m.bySymbol[symbol]; ok {
		return sec, nil
	}
	return nil, errors.New("not found")
}

type ocbMockAllocationRepository struct {
	allocations map[string]float64
	err         error
}

func (m *ocbMockAllocationRepository) GetAll() (map[string]float64, error) {
	return m.allocations, m.err
}

type ocbMockGroupingRepository struct {
	countryGroups  map[string][]string
	industryGroups map[string][]string
	groupWeights   map[string]map[string]float64
	err            error
}

func (m *ocbMockGroupingRepository) GetCountryGroups() (map[string][]string, error) {
	return m.countryGroups, m.err
}

func (m *ocbMockGroupingRepository) GetIndustryGroups() (map[string][]string, error) {
	return m.industryGroups, m.err
}

func (m *ocbMockGroupingRepository) GetGroupWeights(groupType string) (map[string]float64, error) {
	if m.groupWeights == nil {
		return nil, m.err
	}
	if weights, ok := m.groupWeights[groupType]; ok {
		return weights, nil
	}
	return make(map[string]float64), nil
}

type ocbMockTradeRepository struct {
	recentlySold   map[string]bool
	recentlyBought map[string]bool
	soldErr        error
	boughtErr      error
}

func (m *ocbMockTradeRepository) GetRecentlySoldISINs(days int) (map[string]bool, error) {
	return m.recentlySold, m.soldErr
}

func (m *ocbMockTradeRepository) GetRecentlyBoughtISINs(days int) (map[string]bool, error) {
	return m.recentlyBought, m.boughtErr
}

type ocbMockScoresRepository struct {
	totalScores        map[string]float64
	cagrs              map[string]float64
	longTermScores     map[string]float64
	fundamentalsScores map[string]float64
	opportunityScores  map[string]float64
	momentumScores     map[string]float64
	volatility         map[string]float64
	sharpe             map[string]float64
	maxDrawdown        map[string]float64
	err                error
}

func (m *ocbMockScoresRepository) GetTotalScores(isinList []string) (map[string]float64, error) {
	return m.totalScores, m.err
}

func (m *ocbMockScoresRepository) GetCAGRs(isinList []string) (map[string]float64, error) {
	return m.cagrs, m.err
}

func (m *ocbMockScoresRepository) GetQualityScores(isinList []string) (map[string]float64, map[string]float64, error) {
	return m.longTermScores, m.fundamentalsScores, m.err
}

func (m *ocbMockScoresRepository) GetValueTrapData(isinList []string) (map[string]float64, map[string]float64, map[string]float64, error) {
	return m.opportunityScores, m.momentumScores, m.volatility, m.err
}

func (m *ocbMockScoresRepository) GetRiskMetrics(isinList []string) (map[string]float64, map[string]float64, error) {
	return m.sharpe, m.maxDrawdown, m.err
}

type ocbMockSettingsRepository struct {
	targetReturn    float64
	thresholdPct    float64
	cooloffDays     int
	virtualTestCash float64
	targetReturnErr error
	cooloffErr      error
	virtualCashErr  error
}

func (m *ocbMockSettingsRepository) GetTargetReturnSettings() (float64, float64, error) {
	return m.targetReturn, m.thresholdPct, m.targetReturnErr
}

func (m *ocbMockSettingsRepository) GetCooloffDays() (int, error) {
	if m.cooloffDays == 0 {
		return 180, m.cooloffErr // Default
	}
	return m.cooloffDays, m.cooloffErr
}

func (m *ocbMockSettingsRepository) GetVirtualTestCash() (float64, error) {
	return m.virtualTestCash, m.virtualCashErr
}

type ocbMockRegimeRepository struct {
	regimeScore float64
	err         error
}

func (m *ocbMockRegimeRepository) GetCurrentRegimeScore() (float64, error) {
	return m.regimeScore, m.err
}

type ocbMockCashManager struct {
	balances map[string]float64
	err      error
}

func (m *ocbMockCashManager) GetAllCashBalances() (map[string]float64, error) {
	return m.balances, m.err
}

type ocbMockPriceClient struct {
	quotes map[string]*float64
	err    error
}

func (m *ocbMockPriceClient) GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error) {
	return m.quotes, m.err
}

type ocbMockPriceConversionService struct {
	convertedPrices map[string]float64
}

func (m *ocbMockPriceConversionService) ConvertPricesToEUR(prices map[string]float64, securities []universe.Security) map[string]float64 {
	if m.convertedPrices != nil {
		return m.convertedPrices
	}
	// Default: return prices unchanged
	return prices
}

type ocbMockBrokerClient struct {
	connected     bool
	pendingOrders []domain.BrokerPendingOrder
	pendingErr    error
}

func (m *ocbMockBrokerClient) IsConnected() bool {
	return m.connected
}

func (m *ocbMockBrokerClient) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	return m.pendingOrders, m.pendingErr
}

type ocbMockDismissedFilterRepository struct {
	filters map[string]map[string][]string
	err     error
}

func (m *ocbMockDismissedFilterRepository) GetAll() (map[string]map[string][]string, error) {
	if m.err != nil {
		return nil, m.err
	}
	if m.filters != nil {
		return m.filters, nil
	}
	return make(map[string]map[string][]string), nil
}

// Test: Build returns a complete context with all fields populated
func TestOpportunityContextBuilder_Build_ReturnsCompleteContext(t *testing.T) {
	isin := "US0378331005"
	symbol := "AAPL"
	price := 150.0

	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{
			positions: []portfolio.Position{
				{ISIN: isin, Symbol: symbol, Quantity: 10, CurrentPrice: price, Currency: "USD"},
			},
		},
		&ocbMockSecurityRepository{
			securities: []universe.Security{
				{ISIN: isin, Symbol: symbol, Currency: "USD", Country: "US", Active: true, AllowBuy: true, AllowSell: true},
			},
			byISIN: map[string]*universe.Security{
				isin: {ISIN: isin, Symbol: symbol, Currency: "USD", Country: "US", Active: true, AllowBuy: true, AllowSell: true},
			},
		},
		&ocbMockAllocationRepository{allocations: map[string]float64{isin: 0.10}},
		&ocbMockGroupingRepository{
			countryGroups: map[string][]string{"North America": {"US"}},
			groupWeights:  map[string]map[string]float64{"country": {"North America": 0.50}},
		},
		&ocbMockTradeRepository{
			recentlySold:   map[string]bool{},
			recentlyBought: map[string]bool{},
		},
		&ocbMockScoresRepository{
			totalScores:        map[string]float64{isin: 75.0},
			cagrs:              map[string]float64{isin: 0.12},
			longTermScores:     map[string]float64{isin: 80.0},
			fundamentalsScores: map[string]float64{isin: 70.0},
			sharpe:             map[string]float64{isin: 1.5},
			maxDrawdown:        map[string]float64{isin: -0.20},
		},
		&ocbMockSettingsRepository{targetReturn: 0.11, thresholdPct: 0.80, cooloffDays: 180},
		&ocbMockRegimeRepository{regimeScore: 0.5},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{quotes: map[string]*float64{symbol: &price}},
		&ocbMockPriceConversionService{convertedPrices: map[string]float64{isin: 139.5}}, // USD to EUR
		&ocbMockBrokerClient{connected: true, pendingOrders: []domain.BrokerPendingOrder{}},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	// Verify core fields
	assert.NotEmpty(t, ctx.EnrichedPositions, "EnrichedPositions should not be empty")
	assert.NotEmpty(t, ctx.Securities, "Securities should not be empty")
	assert.Greater(t, ctx.TotalPortfolioValueEUR, 0.0, "TotalPortfolioValueEUR should be > 0")
	assert.Greater(t, ctx.AvailableCashEUR, 0.0, "AvailableCashEUR should be > 0")

	// Verify maps are populated
	assert.NotNil(t, ctx.StocksByISIN, "StocksByISIN should not be nil")
	assert.NotNil(t, ctx.CurrentPrices, "CurrentPrices should not be nil")
	assert.NotNil(t, ctx.CountryWeights, "CountryWeights should not be nil")
	assert.NotNil(t, ctx.SecurityScores, "SecurityScores should not be nil")

	// Verify cooloff maps are initialized (even if empty)
	assert.NotNil(t, ctx.RecentlySoldISINs, "RecentlySoldISINs should not be nil")
	assert.NotNil(t, ctx.RecentlyBoughtISINs, "RecentlyBoughtISINs should not be nil")
	assert.NotNil(t, ctx.IneligibleISINs, "IneligibleISINs should not be nil")
}

// Test: Cooloff data is populated from trade repository
func TestOpportunityContextBuilder_Build_PopulatesCooloffFromTrades(t *testing.T) {
	soldISIN := "US0378331005"
	boughtISIN := "DE000A1EWWW0"

	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{securities: []universe.Security{}},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{
			recentlySold:   map[string]bool{soldISIN: true},
			recentlyBought: map[string]bool{boughtISIN: true},
		},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{cooloffDays: 180},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	// Verify recently sold ISINs are populated
	assert.True(t, ctx.RecentlySoldISINs[soldISIN], "Recently sold ISIN should be in cooloff map")
	assert.False(t, ctx.RecentlySoldISINs[boughtISIN], "Bought ISIN should not be in sold map")

	// Verify recently bought ISINs are populated
	assert.True(t, ctx.RecentlyBoughtISINs[boughtISIN], "Recently bought ISIN should be in cooloff map")
	assert.False(t, ctx.RecentlyBoughtISINs[soldISIN], "Sold ISIN should not be in bought map")
}

// Test: Pending orders from broker are added to cooloff maps
func TestOpportunityContextBuilder_Build_PopulatesCooloffFromPendingOrders(t *testing.T) {
	pendingSellSymbol := "AAPL"
	pendingSellISIN := "US0378331005"
	pendingBuySymbol := "MSFT"
	pendingBuyISIN := "US5949181045"

	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{
			securities: []universe.Security{
				{ISIN: pendingSellISIN, Symbol: pendingSellSymbol},
				{ISIN: pendingBuyISIN, Symbol: pendingBuySymbol},
			},
			bySymbol: map[string]*universe.Security{
				pendingSellSymbol: {ISIN: pendingSellISIN, Symbol: pendingSellSymbol},
				pendingBuySymbol:  {ISIN: pendingBuyISIN, Symbol: pendingBuySymbol},
			},
		},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{
			recentlySold:   map[string]bool{},
			recentlyBought: map[string]bool{},
		},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{cooloffDays: 180},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{
			connected: true,
			pendingOrders: []domain.BrokerPendingOrder{
				{Symbol: pendingSellSymbol, Side: "SELL", Quantity: 5, Price: 150.0},
				{Symbol: pendingBuySymbol, Side: "BUY", Quantity: 10, Price: 300.0},
			},
		},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	// Verify pending SELL order adds to RecentlySoldISINs
	assert.True(t, ctx.RecentlySoldISINs[pendingSellISIN], "Pending SELL order should be in sold cooloff map")

	// Verify pending BUY order adds to RecentlyBoughtISINs
	assert.True(t, ctx.RecentlyBoughtISINs[pendingBuyISIN], "Pending BUY order should be in bought cooloff map")
}

// Test: Trades and pending orders are merged correctly
func TestOpportunityContextBuilder_Build_MergesCooloffSources(t *testing.T) {
	tradeSoldISIN := "US0378331005"
	pendingSoldISIN := "US5949181045"
	pendingSoldSymbol := "MSFT"

	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{
			securities: []universe.Security{
				{ISIN: pendingSoldISIN, Symbol: pendingSoldSymbol},
			},
			bySymbol: map[string]*universe.Security{
				pendingSoldSymbol: {ISIN: pendingSoldISIN, Symbol: pendingSoldSymbol},
			},
		},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{
			recentlySold:   map[string]bool{tradeSoldISIN: true},
			recentlyBought: map[string]bool{},
		},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{cooloffDays: 180},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{
			connected: true,
			pendingOrders: []domain.BrokerPendingOrder{
				{Symbol: pendingSoldSymbol, Side: "SELL", Quantity: 5, Price: 300.0},
			},
		},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	// Both trade-based and pending order-based cooloff should be present
	assert.True(t, ctx.RecentlySoldISINs[tradeSoldISIN], "Trade-based sold ISIN should be in cooloff")
	assert.True(t, ctx.RecentlySoldISINs[pendingSoldISIN], "Pending order sold ISIN should be in cooloff")
}

// Test: CountryWeights are populated (critical - this was missing from handler)
func TestOpportunityContextBuilder_Build_PopulatesCountryWeights(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{securities: []universe.Security{}},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{
			countryGroups: map[string][]string{
				"North America": {"US", "CA"},
				"Europe":        {"DE", "FR"},
			},
			groupWeights: map[string]map[string]float64{
				"country": {
					"North America": 0.60, // Will be normalized
					"Europe":        0.40, // Will be normalized
				},
			},
		},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	// CountryWeights must be populated (normalized to sum to 1.0)
	assert.NotNil(t, ctx.CountryWeights, "CountryWeights should not be nil")
	assert.InDelta(t, 0.60, ctx.CountryWeights["North America"], 0.01, "North America weight should be ~0.60")
	assert.InDelta(t, 0.40, ctx.CountryWeights["Europe"], 0.01, "Europe weight should be ~0.40")
}

// Test: Security scores are populated
func TestOpportunityContextBuilder_Build_PopulatesSecurityScores(t *testing.T) {
	isin := "US0378331005"

	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{
			securities: []universe.Security{{ISIN: isin, Symbol: "AAPL"}},
		},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{
			totalScores: map[string]float64{isin: 75.0},
		},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	assert.NotNil(t, ctx.SecurityScores, "SecurityScores should not be nil")
	assert.Equal(t, 75.0, ctx.SecurityScores[isin], "Security score should be populated")
}

// Test: Risk metrics are populated (Sharpe, MaxDrawdown)
func TestOpportunityContextBuilder_Build_PopulatesRiskMetrics(t *testing.T) {
	isin := "US0378331005"

	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{
			securities: []universe.Security{{ISIN: isin, Symbol: "AAPL"}},
		},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{
			sharpe:      map[string]float64{isin: 1.5},
			maxDrawdown: map[string]float64{isin: -0.20},
		},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	assert.NotNil(t, ctx.Sharpe, "Sharpe should not be nil")
	assert.NotNil(t, ctx.MaxDrawdown, "MaxDrawdown should not be nil")
	assert.Equal(t, 1.5, ctx.Sharpe[isin], "Sharpe ratio should be populated")
	assert.Equal(t, -0.20, ctx.MaxDrawdown[isin], "MaxDrawdown should be populated")
}

// Test: CAGRs are populated
func TestOpportunityContextBuilder_Build_PopulatesCAGRs(t *testing.T) {
	isin := "US0378331005"

	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{
			securities: []universe.Security{{ISIN: isin, Symbol: "AAPL"}},
		},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{
			cagrs: map[string]float64{isin: 0.12},
		},
		&ocbMockSettingsRepository{targetReturn: 0.11, thresholdPct: 0.80},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	assert.NotNil(t, ctx.CAGRs, "CAGRs should not be nil")
	assert.Equal(t, 0.12, ctx.CAGRs[isin], "CAGR should be populated")
	assert.Equal(t, 0.11, ctx.TargetReturn, "TargetReturn should be populated from settings")
	assert.Equal(t, 0.80, ctx.TargetReturnThresholdPct, "TargetReturnThresholdPct should be populated")
}

// Test: Prices are converted to EUR
func TestOpportunityContextBuilder_Build_ConvertsAllPricesToEUR(t *testing.T) {
	isin := "US0378331005"
	symbol := "AAPL"
	priceUSD := 150.0
	priceEUR := 139.5 // Converted

	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{
			positions: []portfolio.Position{
				{ISIN: isin, Symbol: symbol, Quantity: 10, CurrentPrice: priceUSD, Currency: "USD"},
			},
		},
		&ocbMockSecurityRepository{
			securities: []universe.Security{
				{ISIN: isin, Symbol: symbol, Currency: "USD"},
			},
			byISIN: map[string]*universe.Security{
				isin: {ISIN: isin, Symbol: symbol, Currency: "USD"},
			},
		},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{quotes: map[string]*float64{symbol: &priceUSD}},
		// PriceConversionService returns prices keyed by symbol, then implementation converts to ISIN
		&ocbMockPriceConversionService{convertedPrices: map[string]float64{symbol: priceEUR}},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	// Prices should be in EUR after conversion (keyed by ISIN in the context)
	assert.NotNil(t, ctx.CurrentPrices, "CurrentPrices should not be nil")
	assert.InDelta(t, priceEUR, ctx.CurrentPrices[isin], 0.01, "Price should be converted to EUR")
}

// Test: Configured cooloff days are used
func TestOpportunityContextBuilder_Build_UsesConfiguredCooloffDays(t *testing.T) {
	// This test verifies the cooloff days setting is respected
	// We can't directly test the days parameter, but we verify the method is called
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	tradeRepo := &ocbMockTradeRepository{
		recentlySold:   map[string]bool{"US0378331005": true},
		recentlyBought: map[string]bool{},
	}

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{securities: []universe.Security{}},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		tradeRepo,
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{cooloffDays: 90}, // Custom cooloff days
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	// The cooloff data should still be populated (verifies the method was called)
	assert.True(t, ctx.RecentlySoldISINs["US0378331005"])
}

// Test: Empty positions are handled gracefully
func TestOpportunityContextBuilder_Build_HandlesEmptyPositions(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}}, // Empty
		&ocbMockSecurityRepository{securities: []universe.Security{}},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	assert.Empty(t, ctx.EnrichedPositions, "EnrichedPositions should be empty")
	assert.Equal(t, 1000.0, ctx.AvailableCashEUR, "Cash should still be available")
	assert.Equal(t, 1000.0, ctx.TotalPortfolioValueEUR, "Total value should be cash only")
}

// Test: Missing prices are handled gracefully
func TestOpportunityContextBuilder_Build_HandlesMissingPrices(t *testing.T) {
	isin := "US0378331005"
	symbol := "AAPL"

	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{
			positions: []portfolio.Position{
				{ISIN: isin, Symbol: symbol, Quantity: 10, Currency: "USD"},
			},
		},
		&ocbMockSecurityRepository{
			securities: []universe.Security{
				{ISIN: isin, Symbol: symbol, Currency: "USD"},
			},
		},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{quotes: map[string]*float64{}}, // No prices
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	// Should not error, just handle gracefully
	require.NoError(t, err)
	require.NotNil(t, ctx)
}

// Test: Broker disconnected skips pending orders gracefully
func TestOpportunityContextBuilder_Build_HandlesBrokerDisconnected(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{securities: []universe.Security{}},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{
			connected:     false, // Disconnected
			pendingOrders: []domain.BrokerPendingOrder{},
		},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	// Should not error, just skip pending orders
	require.NoError(t, err)
	require.NotNil(t, ctx)

	// Cooloff maps should still be initialized (but empty from pending orders)
	assert.NotNil(t, ctx.RecentlySoldISINs)
	assert.NotNil(t, ctx.RecentlyBoughtISINs)
}

// Test: Value trap data is populated
func TestOpportunityContextBuilder_Build_PopulatesValueTrapData(t *testing.T) {
	isin := "US0378331005"

	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{
			securities: []universe.Security{{ISIN: isin, Symbol: "AAPL"}},
		},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{
			opportunityScores: map[string]float64{isin: 0.75},
			momentumScores:    map[string]float64{isin: 0.60},
			volatility:        map[string]float64{isin: 0.25},
		},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{regimeScore: 0.5},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	assert.NotNil(t, ctx.OpportunityScores, "OpportunityScores should not be nil")
	assert.NotNil(t, ctx.MomentumScores, "MomentumScores should not be nil")
	assert.NotNil(t, ctx.Volatility, "Volatility should not be nil")
	assert.Equal(t, 0.75, ctx.OpportunityScores[isin])
	assert.Equal(t, 0.60, ctx.MomentumScores[isin])
	assert.Equal(t, 0.25, ctx.Volatility[isin])
	assert.Equal(t, 0.5, ctx.RegimeScore)
}

// Test: Position repository error is handled
func TestOpportunityContextBuilder_Build_HandlesPositionRepoError(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{err: errors.New("database error")},
		&ocbMockSecurityRepository{securities: []universe.Security{}},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.Error(t, err)
	assert.Nil(t, ctx)
	assert.Contains(t, err.Error(), "position")
}

// Test: Security repository error is handled
func TestOpportunityContextBuilder_Build_HandlesSecurityRepoError(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{err: errors.New("database error")},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.Error(t, err)
	assert.Nil(t, ctx)
	assert.Contains(t, err.Error(), "securit")
}

// Test: Dismissed filters are populated
func TestOpportunityContextBuilder_Build_PopulatesDismissedFilters(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	dismissedFilters := map[string]map[string][]string{
		"US0378331005": {
			"opportunity_buys": {"score below minimum", "value trap detected"},
			"averaging_down":   {"recently bought"},
		},
		"US5949181045": {
			"profit_taking": {"insufficient gains"},
		},
	}

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{securities: []universe.Security{}},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		&ocbMockDismissedFilterRepository{filters: dismissedFilters},
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	// Verify dismissed filters are populated
	assert.NotNil(t, ctx.DismissedFilters, "DismissedFilters should not be nil")
	assert.Len(t, ctx.DismissedFilters, 2, "Should have 2 ISINs with dismissed filters")
	assert.Len(t, ctx.DismissedFilters["US0378331005"]["opportunity_buys"], 2)
	assert.Contains(t, ctx.DismissedFilters["US0378331005"]["opportunity_buys"], "score below minimum")
}

// Test: Nil dismissed filter repo is handled gracefully
func TestOpportunityContextBuilder_Build_HandlesNilDismissedFilterRepo(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{securities: []universe.Security{}},
		&ocbMockAllocationRepository{allocations: map[string]float64{}},
		&ocbMockGroupingRepository{groupWeights: map[string]map[string]float64{"country": {}}},
		&ocbMockTradeRepository{recentlySold: map[string]bool{}, recentlyBought: map[string]bool{}},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{connected: false},
		nil, // nil dismissed filter repo
		log,
	)

	ctx, err := builder.Build()

	require.NoError(t, err)
	require.NotNil(t, ctx)

	// Dismissed filters should be empty map (not nil)
	assert.NotNil(t, ctx.DismissedFilters)
	assert.Empty(t, ctx.DismissedFilters)
}
