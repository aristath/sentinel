package calculators

import (
	"fmt"
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Mock implementations for averaging down tests
type mockTagFilterAveragingDown struct {
	opportunityCandidates []string
	err                   error
}

func (m *mockTagFilterAveragingDown) GetOpportunityCandidates(ctx *planningdomain.OpportunityContext, config *planningdomain.PlannerConfiguration) ([]string, error) {
	return m.opportunityCandidates, m.err
}

func (m *mockTagFilterAveragingDown) GetSellCandidates(ctx *planningdomain.OpportunityContext, config *planningdomain.PlannerConfiguration) ([]string, error) {
	return nil, nil
}

func (m *mockTagFilterAveragingDown) IsMarketVolatile(ctx *planningdomain.OpportunityContext, config *planningdomain.PlannerConfiguration) bool {
	return false
}

// mockSecurityRepoAveragingDown implements SecurityRepository interface for testing.
type mockSecurityRepoAveragingDown struct {
	tags map[string][]string
}

func (m *mockSecurityRepoAveragingDown) GetTagsForSecurity(symbol string) ([]string, error) {
	if tags, ok := m.tags[symbol]; ok {
		return tags, nil
	}
	return []string{}, nil
}

func TestAveragingDownCalculator_WithTagFiltering_PreFiltersPositions(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{
		opportunityCandidates: []string{"TEST.US"}, // Only TEST.US pre-filtered
	}
	securityRepo := &mockSecurityRepoAveragingDown{
		tags: map[string][]string{
			"TEST.US":  {"quality-gate-pass", "quality-value"},
			"OTHER.US": {"quality-gate-pass"},
		},
	}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	// Create two positions with losses
	position1 := domain.Position{
		Symbol:      "TEST.US",
		ISIN:        "US1234567890",
		Quantity:    100,
		AverageCost: 20.0,
	}
	position2 := domain.Position{
		Symbol:      "OTHER.US",
		ISIN:        "US0987654321",
		Quantity:    100,
		AverageCost: 20.0,
	}

	security1 := domain.Security{
		Symbol:   "TEST.US",
		Name:     "Test Security",
		ISIN:     "US1234567890",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}
	security2 := domain.Security{
		Symbol:   "OTHER.US",
		Name:     "Other Security",
		ISIN:     "US0987654321",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:         []domain.Position{position1, position2},
		Securities:        []domain.Security{security1, security2},
		CurrentPrices:     map[string]float64{"US1234567890": 15.0, "US0987654321": 15.0}, // 25% loss
		StocksByISIN:      map[string]domain.Security{"US1234567890": security1, "US0987654321": security2},
		StocksBySymbol:    map[string]domain.Security{"TEST.US": security1, "OTHER.US": security2},
		AvailableCashEUR:  1000.0,
		IneligibleSymbols: map[string]bool{},
		RecentlyBought:    map[string]bool{},
		AllowBuy:          true,
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = true

	params := map[string]interface{}{
		"max_loss_percent": -0.30,
		"min_loss_percent": -0.05,
		"config":           config,
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)

	// Only TEST.US should be included (tag pre-filtered)
	assert.Len(t, candidates, 1, "Should only include pre-filtered position")
	assert.Equal(t, "TEST.US", candidates[0].Symbol)
}

func TestAveragingDownCalculator_WithoutTagFiltering_ProcessesAllPositions(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{
		opportunityCandidates: []string{"TEST.US"},
	}
	securityRepo := &mockSecurityRepoAveragingDown{tags: map[string][]string{}}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	position1 := domain.Position{
		Symbol:      "TEST.US",
		ISIN:        "US1234567890",
		Quantity:    100,
		AverageCost: 20.0,
	}
	position2 := domain.Position{
		Symbol:      "OTHER.US",
		ISIN:        "US0987654321",
		Quantity:    100,
		AverageCost: 20.0,
	}

	security1 := domain.Security{
		Symbol:   "TEST.US",
		Name:     "Test Security",
		ISIN:     "US1234567890",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}
	security2 := domain.Security{
		Symbol:   "OTHER.US",
		Name:     "Other Security",
		ISIN:     "US0987654321",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:          []domain.Position{position1, position2},
		Securities:         []domain.Security{security1, security2},
		CurrentPrices:      map[string]float64{"US1234567890": 15.0, "US0987654321": 15.0},
		StocksByISIN:       map[string]domain.Security{"US1234567890": security1, "US0987654321": security2},
		StocksBySymbol:     map[string]domain.Security{"TEST.US": security1, "OTHER.US": security2},
		AvailableCashEUR:   1000.0,
		IneligibleSymbols:  map[string]bool{},
		RecentlyBought:     map[string]bool{},
		AllowBuy:           true,
		FundamentalsScores: map[string]float64{"TEST.US": 0.7, "OTHER.US": 0.7},
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = false // Tag filtering disabled

	params := map[string]interface{}{
		"max_loss_percent": -0.30,
		"min_loss_percent": -0.05,
		"config":           config,
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)

	// Both positions should be included (no tag filtering)
	assert.Len(t, candidates, 2, "Should process all positions when tag filtering disabled")
}

func TestAveragingDownCalculator_EnforcesAllowBuy(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{opportunityCandidates: []string{"TEST.US"}}
	securityRepo := &mockSecurityRepoAveragingDown{tags: map[string][]string{"TEST.US": {"quality-gate-pass"}}}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	position := domain.Position{
		Symbol:      "TEST.US",
		ISIN:        "US1234567890",
		Quantity:    100,
		AverageCost: 20.0,
	}

	security := domain.Security{
		Symbol:   "TEST.US",
		Name:     "Test Security",
		ISIN:     "US1234567890",
		Active:   true,
		AllowBuy: false, // Buying not allowed
		Currency: "EUR",
		MinLot:   1,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:         []domain.Position{position},
		Securities:        []domain.Security{security},
		CurrentPrices:     map[string]float64{"US1234567890": 15.0},
		StocksByISIN:      map[string]domain.Security{"US1234567890": security},
		StocksBySymbol:    map[string]domain.Security{"TEST.US": security},
		AvailableCashEUR:  1000.0,
		IneligibleSymbols: map[string]bool{},
		RecentlyBought:    map[string]bool{},
		AllowBuy:          true,
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = true

	params := map[string]interface{}{
		"max_loss_percent": -0.30,
		"min_loss_percent": -0.05,
		"config":           config,
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	assert.Empty(t, candidates, "Should skip securities with AllowBuy=false")
}

func TestAveragingDownCalculator_RoundsToLotSize(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{opportunityCandidates: []string{"TEST.US"}}
	securityRepo := &mockSecurityRepoAveragingDown{tags: map[string][]string{"TEST.US": {"quality-gate-pass"}}}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	position := domain.Position{
		Symbol:      "TEST.US",
		ISIN:        "US1234567890",
		Quantity:    888, // Will try to add 88.8 shares (10%), should round to 88
		AverageCost: 20.0,
	}

	security := domain.Security{
		Symbol:   "TEST.US",
		Name:     "Test Security",
		ISIN:     "US1234567890",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:              []domain.Position{position},
		Securities:             []domain.Security{security},
		CurrentPrices:          map[string]float64{"US1234567890": 15.0},
		StocksByISIN:           map[string]domain.Security{"US1234567890": security},
		StocksBySymbol:         map[string]domain.Security{"TEST.US": security},
		AvailableCashEUR:       10000.0,
		TotalPortfolioValueEUR: 10000.0,
		IneligibleSymbols:      map[string]bool{},
		RecentlyBought:         map[string]bool{},
		AllowBuy:               true,
		KellySizes:             nil, // Explicitly nil - use percentage-based fallback
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = true

	params := map[string]interface{}{
		"max_loss_percent":       -0.30,
		"min_loss_percent":       -0.05,
		"averaging_down_percent": 0.10,   // 10%
		"max_value_per_position": 2000.0, // High enough to not interfere with lot sizing test
		"config":                 config,
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, candidates, 1)

	// Quantity should be rounded to whole number (88 shares)
	assert.Equal(t, 88, candidates[0].Quantity, "Should round 88.8 shares to 88")
}

func TestAveragingDownCalculator_KellyBasedQuantity_WhenAvailable(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{opportunityCandidates: []string{"TEST.US"}}
	securityRepo := &mockSecurityRepoAveragingDown{tags: map[string][]string{"TEST.US": {"quality-gate-pass"}}}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	position := domain.Position{
		Symbol:      "TEST.US",
		ISIN:        "US1234567890",
		Quantity:    100,
		AverageCost: 20.0,
	}

	security := domain.Security{
		Symbol:   "TEST.US",
		Name:     "Test Security",
		ISIN:     "US1234567890",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:              []domain.Position{position},
		Securities:             []domain.Security{security},
		CurrentPrices:          map[string]float64{"US1234567890": 15.0},
		StocksByISIN:           map[string]domain.Security{"US1234567890": security},
		StocksBySymbol:         map[string]domain.Security{"TEST.US": security},
		AvailableCashEUR:       10000.0,
		TotalPortfolioValueEUR: 10000.0,
		IneligibleSymbols:      map[string]bool{},
		RecentlyBought:         map[string]bool{},
		AllowBuy:               true,
		KellySizes:             map[string]float64{"TEST.US": 0.20}, // Kelly says 20% of portfolio
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = true

	params := map[string]interface{}{
		"max_loss_percent":       -0.30,
		"min_loss_percent":       -0.05,
		"averaging_down_percent": 0.10, // This should be ignored when Kelly available
		"config":                 config,
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, candidates, 1)

	// Kelly calculation:
	// Kelly target value = 0.20 * 10000 = 2000 EUR
	// Kelly target shares = 2000 / 15 = 133.33 shares
	// Current shares = 100
	// Additional shares = 133.33 - 100 = 33.33 → 33 shares
	assert.Equal(t, 33, candidates[0].Quantity, "Should use Kelly-based quantity (133 target - 100 current = 33)")
}

func TestAveragingDownCalculator_PercentageBasedQuantity_Fallback(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{opportunityCandidates: []string{"TEST.US"}}
	securityRepo := &mockSecurityRepoAveragingDown{tags: map[string][]string{"TEST.US": {"quality-gate-pass"}}}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	position := domain.Position{
		Symbol:      "TEST.US",
		ISIN:        "US1234567890",
		Quantity:    100,
		AverageCost: 20.0,
	}

	security := domain.Security{
		Symbol:   "TEST.US",
		Name:     "Test Security",
		ISIN:     "US1234567890",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:              []domain.Position{position},
		Securities:             []domain.Security{security},
		CurrentPrices:          map[string]float64{"US1234567890": 15.0},
		StocksByISIN:           map[string]domain.Security{"US1234567890": security},
		StocksBySymbol:         map[string]domain.Security{"TEST.US": security},
		AvailableCashEUR:       10000.0,
		TotalPortfolioValueEUR: 10000.0,
		IneligibleSymbols:      map[string]bool{},
		RecentlyBought:         map[string]bool{},
		AllowBuy:               true,
		// No KellySizes - should fall back to percentage
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = true

	params := map[string]interface{}{
		"max_loss_percent":       -0.30,
		"min_loss_percent":       -0.05,
		"averaging_down_percent": 0.15, // 15% of position
		"config":                 config,
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, candidates, 1)

	// Percentage-based calculation: 100 * 0.15 = 15 shares
	assert.Equal(t, 15, candidates[0].Quantity, "Should use percentage-based fallback (100 * 0.15 = 15)")
}

func TestAveragingDownCalculator_UsesConfigurablePercent_NotHardcoded(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{opportunityCandidates: []string{"TEST.US"}}
	securityRepo := &mockSecurityRepoAveragingDown{tags: map[string][]string{"TEST.US": {"quality-gate-pass"}}}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	position := domain.Position{
		Symbol:      "TEST.US",
		ISIN:        "US1234567890",
		Quantity:    100,
		AverageCost: 20.0,
	}

	security := domain.Security{
		Symbol:   "TEST.US",
		Name:     "Test Security",
		ISIN:     "US1234567890",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:         []domain.Position{position},
		Securities:        []domain.Security{security},
		CurrentPrices:     map[string]float64{"US1234567890": 15.0},
		StocksByISIN:      map[string]domain.Security{"US1234567890": security},
		StocksBySymbol:    map[string]domain.Security{"TEST.US": security},
		AvailableCashEUR:  10000.0,
		IneligibleSymbols: map[string]bool{},
		RecentlyBought:    map[string]bool{},
		AllowBuy:          true,
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = true

	tests := []struct {
		name                 string
		averagingDownPercent float64
		expectedQuantity     int
	}{
		{"5% of position", 0.05, 5},
		{"10% of position (default)", 0.10, 10},
		{"15% of position", 0.15, 15},
		{"20% of position", 0.20, 20},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			params := map[string]interface{}{
				"max_loss_percent":       -0.30,
				"min_loss_percent":       -0.05,
				"averaging_down_percent": tt.averagingDownPercent,
				"config":                 config,
			}

			candidates, err := calc.Calculate(ctx, params)
			require.NoError(t, err)
			require.Len(t, candidates, 1)

			assert.Equal(t, tt.expectedQuantity, candidates[0].Quantity,
				"Should use configurable percentage: 100 * %.2f = %d", tt.averagingDownPercent, tt.expectedQuantity)
		})
	}
}

func TestAveragingDownCalculator_SkipsAveragingDown_WhenAtKellyOptimal(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{opportunityCandidates: []string{"TEST.US"}}
	securityRepo := &mockSecurityRepoAveragingDown{tags: map[string][]string{"TEST.US": {"quality-gate-pass"}}}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	position := domain.Position{
		Symbol:      "TEST.US",
		ISIN:        "US1234567890",
		Quantity:    134, // Above Kelly optimal (Kelly target = 133.33 shares)
		AverageCost: 20.0,
	}

	security := domain.Security{
		Symbol:   "TEST.US",
		Name:     "Test Security",
		ISIN:     "US1234567890",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:              []domain.Position{position},
		Securities:             []domain.Security{security},
		CurrentPrices:          map[string]float64{"US1234567890": 15.0},
		StocksByISIN:           map[string]domain.Security{"US1234567890": security},
		StocksBySymbol:         map[string]domain.Security{"TEST.US": security},
		AvailableCashEUR:       10000.0,
		TotalPortfolioValueEUR: 10000.0,
		IneligibleSymbols:      map[string]bool{},
		RecentlyBought:         map[string]bool{},
		AllowBuy:               true,
		KellySizes:             map[string]float64{"TEST.US": 0.20}, // Kelly says 20% = ~133 shares at $15
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = true

	params := map[string]interface{}{
		"max_loss_percent": -0.30,
		"min_loss_percent": -0.05,
		"config":           config,
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)

	// Should skip - already at Kelly optimal
	assert.Empty(t, candidates, "Should skip averaging down when already at Kelly optimal")
}

func TestAveragingDownCalculator_TagBasedQualityGates_ValueTrap(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{opportunityCandidates: []string{"TEST.US"}}
	securityRepo := &mockSecurityRepoAveragingDown{
		tags: map[string][]string{
			"TEST.US": {"value-trap", "quality-gate-pass"}, // Value trap should exclude
		},
	}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	position := domain.Position{
		Symbol:      "TEST.US",
		ISIN:        "US1234567890",
		Quantity:    100,
		AverageCost: 20.0,
	}

	security := domain.Security{
		Symbol:   "TEST.US",
		Name:     "Test Security",
		ISIN:     "US1234567890",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:         []domain.Position{position},
		Securities:        []domain.Security{security},
		CurrentPrices:     map[string]float64{"US1234567890": 15.0},
		StocksByISIN:      map[string]domain.Security{"US1234567890": security},
		StocksBySymbol:    map[string]domain.Security{"TEST.US": security},
		AvailableCashEUR:  1000.0,
		IneligibleSymbols: map[string]bool{},
		RecentlyBought:    map[string]bool{},
		AllowBuy:          true,
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = true

	params := map[string]interface{}{
		"max_loss_percent": -0.30,
		"min_loss_percent": -0.05,
		"config":           config,
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	assert.Empty(t, candidates, "Should exclude value traps")
}

func TestAveragingDownCalculator_TagBasedPriorityBoosting_QualityValue(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{
		opportunityCandidates: []string{"QUALITY.US", "NORMAL.US"},
	}
	securityRepo := &mockSecurityRepoAveragingDown{
		tags: map[string][]string{
			"QUALITY.US": {"quality-gate-pass", "quality-value"},
			"NORMAL.US":  {"quality-gate-pass"},
		},
	}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	position1 := domain.Position{
		Symbol:      "QUALITY.US",
		ISIN:        "US1111111111",
		Quantity:    100,
		AverageCost: 20.0,
	}
	position2 := domain.Position{
		Symbol:      "NORMAL.US",
		ISIN:        "US2222222222",
		Quantity:    100,
		AverageCost: 20.0,
	}

	security1 := domain.Security{
		Symbol:   "QUALITY.US",
		Name:     "Quality Security",
		ISIN:     "US1111111111",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}
	security2 := domain.Security{
		Symbol:   "NORMAL.US",
		Name:     "Normal Security",
		ISIN:     "US2222222222",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:         []domain.Position{position1, position2},
		Securities:        []domain.Security{security1, security2},
		CurrentPrices:     map[string]float64{"US1111111111": 15.0, "US2222222222": 15.0}, // Same loss
		StocksByISIN:      map[string]domain.Security{"US1111111111": security1, "US2222222222": security2},
		StocksBySymbol:    map[string]domain.Security{"QUALITY.US": security1, "NORMAL.US": security2},
		AvailableCashEUR:  10000.0,
		IneligibleSymbols: map[string]bool{},
		RecentlyBought:    map[string]bool{},
		AllowBuy:          true,
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = true

	params := map[string]interface{}{
		"max_loss_percent": -0.30,
		"min_loss_percent": -0.05,
		"config":           config,
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, candidates, 2)

	// QUALITY.US should have higher priority (1.5x boost)
	assert.Equal(t, "QUALITY.US", candidates[0].Symbol, "Quality value should be first")
	assert.Greater(t, candidates[0].Priority, candidates[1].Priority, "Quality value should have higher priority")
}

func TestAveragingDownCalculator_SortsByPriorityDescending(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{
		opportunityCandidates: []string{"DEEP.US", "SHALLOW.US"},
	}
	securityRepo := &mockSecurityRepoAveragingDown{
		tags: map[string][]string{
			"DEEP.US":    {"quality-gate-pass"},
			"SHALLOW.US": {"quality-gate-pass"},
		},
	}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	position1 := domain.Position{
		Symbol:      "DEEP.US",
		ISIN:        "US1111111111",
		Quantity:    100,
		AverageCost: 20.0,
	}
	position2 := domain.Position{
		Symbol:      "SHALLOW.US",
		ISIN:        "US2222222222",
		Quantity:    100,
		AverageCost: 20.0,
	}

	security1 := domain.Security{
		Symbol:   "DEEP.US",
		Name:     "Deep Loss Security",
		ISIN:     "US1111111111",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}
	security2 := domain.Security{
		Symbol:   "SHALLOW.US",
		Name:     "Shallow Loss Security",
		ISIN:     "US2222222222",
		Active:   true,
		AllowBuy: true,
		Currency: "EUR",
		MinLot:   1,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:         []domain.Position{position1, position2},
		Securities:        []domain.Security{security1, security2},
		CurrentPrices:     map[string]float64{"US1111111111": 12.0, "US2222222222": 18.0}, // 40% vs 10% loss
		StocksByISIN:      map[string]domain.Security{"US1111111111": security1, "US2222222222": security2},
		StocksBySymbol:    map[string]domain.Security{"DEEP.US": security1, "SHALLOW.US": security2},
		AvailableCashEUR:  10000.0,
		IneligibleSymbols: map[string]bool{},
		RecentlyBought:    map[string]bool{},
		AllowBuy:          true,
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = true

	params := map[string]interface{}{
		"max_loss_percent": -0.50,
		"min_loss_percent": -0.05,
		"config":           config,
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, candidates, 2)

	// DEEP.US should be first (deeper loss = higher priority)
	assert.Equal(t, "DEEP.US", candidates[0].Symbol, "Deeper loss should have higher priority")
	assert.Greater(t, candidates[0].Priority, candidates[1].Priority)
}

func TestAveragingDownCalculator_RespectsMaxPositionsLimit(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilterAveragingDown{
		opportunityCandidates: []string{"A.US", "B.US", "C.US", "D.US", "E.US"},
	}
	securityRepo := &mockSecurityRepoAveragingDown{
		tags: map[string][]string{
			"A.US": {"quality-gate-pass"},
			"B.US": {"quality-gate-pass"},
			"C.US": {"quality-gate-pass"},
			"D.US": {"quality-gate-pass"},
			"E.US": {"quality-gate-pass"},
		},
	}
	calc := NewAveragingDownCalculator(tagFilter, securityRepo, log)

	positions := []domain.Position{}
	securities := []domain.Security{}
	prices := map[string]float64{}
	stocksByISIN := map[string]domain.Security{}
	stocksBySymbol := map[string]domain.Security{}

	symbols := []string{"A.US", "B.US", "C.US", "D.US", "E.US"}
	for i, symbol := range symbols {
		isin := fmt.Sprintf("US%d", i)
		positions = append(positions, domain.Position{
			Symbol:      symbol,
			ISIN:        isin,
			Quantity:    100,
			AverageCost: 20.0,
		})
		security := domain.Security{
			Symbol:   symbol,
			Name:     symbol,
			ISIN:     isin,
			Active:   true,
			AllowBuy: true,
			Currency: "EUR",
			MinLot:   1,
		}
		securities = append(securities, security)
		prices[isin] = 15.0
		stocksByISIN[isin] = security
		stocksBySymbol[symbol] = security
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:         positions,
		Securities:        securities,
		CurrentPrices:     prices,
		StocksByISIN:      stocksByISIN,
		StocksBySymbol:    stocksBySymbol,
		AvailableCashEUR:  10000.0,
		IneligibleSymbols: map[string]bool{},
		RecentlyBought:    map[string]bool{},
		AllowBuy:          true,
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = true

	params := map[string]interface{}{
		"max_loss_percent": -0.30,
		"min_loss_percent": -0.05,
		"max_positions":    3, // Limit to top 3
		"config":           config,
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)

	assert.Len(t, candidates, 3, "Should respect max_positions limit")
}
