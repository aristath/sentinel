package constraints

import (
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestEnforcer_EnforceConstraints_AllowSellFalse(t *testing.T) {
	log := zerolog.Nop()

	// Create context with BYD security (allow_sell=false)
	security := universe.Security{
		Symbol:    "BYD.285.AS",
		Name:      "BYD Electronic",
		ISIN:      "KYG1170T1067",
		AllowSell: false,
		AllowBuy:  true,
		MinLot:    500,
	}

	ctx := createTestContext(security)
	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	// Create action to sell BYD (allow_sell=false)
	action := planningdomain.ActionCandidate{
		Side:     "SELL",
		ISIN:     "KYG1170T1067",
		Symbol:   "BYD.285.AS",
		Name:     "BYD Electronic",
		Quantity: 13,
		Price:    36.0,
		ValueEUR: 468.0,
		Currency: "EUR",
		Priority: 0.8,
		Reason:   "Overweight",
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, nil)

	// Should be filtered out
	assert.Len(t, validated, 0)
	assert.Len(t, filtered, 1)
	assert.Equal(t, "allow_sell=false", filtered[0].Reason)
	assert.Equal(t, "BYD.285.AS", filtered[0].Action.Symbol)
}

func TestEnforcer_EnforceConstraints_AllowBuyFalse(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		AllowBuy:  false,
		MinLot:    1,
	}

	ctx := createTestContext(security)
	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	action := planningdomain.ActionCandidate{
		Side:     "BUY",
		ISIN:     "US1234567890",
		Symbol:   "TEST.US",
		Name:     "Test Security",
		Quantity: 10,
		Price:    50.0,
		ValueEUR: 500.0,
		Currency: "EUR",
		Priority: 0.5,
		Reason:   "Underweight",
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, nil)

	assert.Len(t, validated, 0)
	assert.Len(t, filtered, 1)
	assert.Equal(t, "allow_buy=false", filtered[0].Reason)
}

func TestEnforcer_EnforceConstraints_LotSizeRoundingDown(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    500,
	}

	ctx := createTestContext(security)
	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	// 1200 shares with minLot=500 should round down to 1000
	action := planningdomain.ActionCandidate{
		Side:     "SELL",
		ISIN:     "US1234567890",
		Symbol:   "TEST.US",
		Name:     "Test Security",
		Quantity: 1200,
		Price:    10.0,
		ValueEUR: 12000.0,
		Currency: "EUR",
		Priority: 0.5,
		Reason:   "Overweight",
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, nil)

	assert.Len(t, validated, 1)
	assert.Len(t, filtered, 0)
	assert.Equal(t, 1000, validated[0].Quantity)
	assert.Equal(t, 10000.0, validated[0].ValueEUR) // 1000 * 10.0
}

func TestEnforcer_EnforceConstraints_LotSizeRoundingUp(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "BYD.285.AS",
		Name:      "BYD Electronic",
		ISIN:      "KYG1170T1067",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    500,
	}

	ctx := createTestContext(security)
	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	// 13 shares with minLot=500 should round up to 500 (since rounding down gives 0)
	action := planningdomain.ActionCandidate{
		Side:     "SELL",
		ISIN:     "KYG1170T1067",
		Symbol:   "BYD.285.AS",
		Name:     "BYD Electronic",
		Quantity: 13,
		Price:    36.0,
		ValueEUR: 468.0,
		Currency: "EUR",
		Priority: 0.8,
		Reason:   "Overweight",
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, nil)

	assert.Len(t, validated, 1)
	assert.Len(t, filtered, 0)
	assert.Equal(t, 500, validated[0].Quantity)
	assert.Equal(t, 18000.0, validated[0].ValueEUR) // 500 * 36.0
}

func TestEnforcer_EnforceConstraints_LotSizeExactMatch(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    500,
	}

	ctx := createTestContext(security)
	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	// 500 shares with minLot=500 should stay 500
	action := planningdomain.ActionCandidate{
		Side:     "SELL",
		ISIN:     "US1234567890",
		Symbol:   "TEST.US",
		Name:     "Test Security",
		Quantity: 500,
		Price:    10.0,
		ValueEUR: 5000.0,
		Currency: "EUR",
		Priority: 0.5,
		Reason:   "Overweight",
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, nil)

	assert.Len(t, validated, 1)
	assert.Len(t, filtered, 0)
	assert.Equal(t, 500, validated[0].Quantity)
	assert.Equal(t, 5000.0, validated[0].ValueEUR)
}

func TestEnforcer_EnforceConstraints_LotSizeMultiple(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    500,
	}

	ctx := createTestContext(security)
	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	// 1500 shares with minLot=500 should stay 1500 (already a multiple)
	action := planningdomain.ActionCandidate{
		Side:     "SELL",
		ISIN:     "US1234567890",
		Symbol:   "TEST.US",
		Name:     "Test Security",
		Quantity: 1500,
		Price:    10.0,
		ValueEUR: 15000.0,
		Currency: "EUR",
		Priority: 0.5,
		Reason:   "Overweight",
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, nil)

	assert.Len(t, validated, 1)
	assert.Len(t, filtered, 0)
	assert.Equal(t, 1500, validated[0].Quantity)
	assert.Equal(t, 15000.0, validated[0].ValueEUR)
}

func TestEnforcer_EnforceConstraints_ValueRecalculation(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    500,
	}

	ctx := createTestContext(security)
	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	// Quantity changes from 13 to 500, value should be recalculated
	action := planningdomain.ActionCandidate{
		Side:     "SELL",
		ISIN:     "US1234567890",
		Symbol:   "TEST.US",
		Name:     "Test Security",
		Quantity: 13,
		Price:    36.0,
		ValueEUR: 468.0, // Original value
		Currency: "EUR",
		Priority: 0.5,
		Reason:   "Overweight",
	}

	validated, _ := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, nil)

	require.Len(t, validated, 1)
	assert.Equal(t, 500, validated[0].Quantity)
	assert.Equal(t, 18000.0, validated[0].ValueEUR) // 500 * 36.0, not 468.0
}

func TestEnforcer_EnforceConstraints_MultipleActions(t *testing.T) {
	log := zerolog.Nop()

	actions := []planningdomain.ActionCandidate{
		{
			Side:     "SELL",
			ISIN:     "KYG1170T1067",
			Symbol:   "BYD.285.AS",
			Name:     "BYD Electronic",
			Quantity: 13,
			Price:    36.0,
			ValueEUR: 468.0,
			Currency: "EUR",
			Priority: 0.8,
			Reason:   "Overweight",
		},
		{
			Side:     "BUY",
			ISIN:     "US9876543210",
			Symbol:   "VALID.US",
			Name:     "Valid Security",
			Quantity: 100,
			Price:    50.0,
			ValueEUR: 5000.0,
			Currency: "EUR",
			Priority: 0.5,
			Reason:   "Underweight",
		},
	}

	securities := []universe.Security{
		{
			Symbol:    "BYD.285.AS",
			Name:      "BYD Electronic",
			ISIN:      "KYG1170T1067",
			AllowSell: false, // Should be filtered
			AllowBuy:  true,
			MinLot:    500,
		},
		{
			Symbol:    "VALID.US",
			Name:      "Valid Security",
			ISIN:      "US9876543210",
			AllowSell: true,
			AllowBuy:  true,
			MinLot:    1,
		},
	}

	ctx := createTestContextWithMultipleSecurities(securities)
	securityLookup := createSecurityLookup(securities)
	enforcer := NewEnforcer(log, securityLookup)

	validated, filtered := enforcer.EnforceConstraints(actions, ctx, nil)

	assert.Len(t, validated, 1)
	assert.Len(t, filtered, 1)
	assert.Equal(t, "VALID.US", validated[0].Symbol)
	assert.Equal(t, "BYD.285.AS", filtered[0].Action.Symbol)
	assert.Equal(t, "allow_sell=false", filtered[0].Reason)
}

func TestEnforcer_EnforceConstraints_MissingSecurity(t *testing.T) {
	log := zerolog.Nop()
	securityLookup := createSecurityLookup([]universe.Security{}) // Empty lookup
	enforcer := NewEnforcer(log, securityLookup)

	action := planningdomain.ActionCandidate{
		Side:     "SELL",
		ISIN:     "US0000000000",
		Symbol:   "UNKNOWN.US",
		Name:     "Unknown Security",
		Quantity: 100,
		Price:    10.0,
		ValueEUR: 1000.0,
		Currency: "EUR",
		Priority: 0.5,
		Reason:   "Overweight",
	}

	// Context without this security
	ctx := &planningdomain.OpportunityContext{
		StocksByISIN: make(map[string]domain.Security),
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, nil)

	assert.Len(t, validated, 0)
	assert.Len(t, filtered, 1)
	assert.Contains(t, filtered[0].Reason, "security not found")
}

func TestEnforcer_EnforceConstraints_ZeroLotSize(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    0, // Zero lot size
	}

	ctx := createTestContext(security)
	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	// Zero or negative lot size should be treated as 1 (no rounding)
	action := planningdomain.ActionCandidate{
		Side:     "SELL",
		ISIN:     "US1234567890",
		Symbol:   "TEST.US",
		Name:     "Test Security",
		Quantity: 13,
		Price:    10.0,
		ValueEUR: 130.0,
		Currency: "EUR",
		Priority: 0.5,
		Reason:   "Overweight",
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, nil)

	assert.Len(t, validated, 1)
	assert.Len(t, filtered, 0)
	assert.Equal(t, 13, validated[0].Quantity) // No rounding when lot size is 0
}

func TestEnforcer_roundToLotSize(t *testing.T) {
	log := zerolog.Nop()
	securityLookup := createSecurityLookup([]universe.Security{})
	enforcer := NewEnforcer(log, securityLookup)

	tests := []struct {
		name     string
		quantity int
		lotSize  int
		expected int
	}{
		{"round down: 1200 -> 1000", 1200, 500, 1000},
		{"round up: 13 -> 500", 13, 500, 500},
		{"exact match: 500 -> 500", 500, 500, 500},
		{"multiple: 1500 -> 1500", 1500, 500, 1500},
		{"zero lot size: 13 -> 13", 13, 0, 13},
		{"negative lot size: 13 -> 13", 13, -1, 13},
		{"small quantity below lot: 100 -> 0 then 500", 100, 500, 500},
		{"exactly one lot: 500 -> 500", 500, 500, 500},
		{"just below one lot: 499 -> 500", 499, 500, 500},
		{"just above one lot: 501 -> 500", 501, 500, 500},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := enforcer.roundToLotSize(tt.quantity, tt.lotSize)
			assert.Equal(t, tt.expected, result, "quantity=%d, lotSize=%d", tt.quantity, tt.lotSize)
		})
	}
}

func TestEnforcer_EnforceConstraints_MaxSellPercentage(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "PPA.GR",
		Name:      "PPA Security",
		ISIN:      "GR1234567890",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    1,
	}

	// Position: 888.8 shares
	position := domain.Position{
		Symbol:   "PPA.GR",
		ISIN:     "GR1234567890",
		Quantity: 888.8,
	}

	config := &planningdomain.PlannerConfiguration{
		MaxSellPercentage: 0.28, // 28% max sell
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:         []domain.Position{position},
		Securities:        []domain.Security{{Symbol: "PPA.GR", ISIN: "GR1234567890"}},
		StocksByISIN:      map[string]domain.Security{"GR1234567890": {Symbol: "PPA.GR", ISIN: "GR1234567890"}},
		IneligibleISINs:   map[string]bool{},
		RecentlySoldISINs: map[string]bool{},
		AllowSell:         true,
	}

	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	tests := []struct {
		name                string
		sellQuantity        int
		expectedValid       bool
		expectedMaxQuantity int
		description         string
	}{
		{
			name:                "441 shares exceeds 28% of 888.8 (max 248)",
			sellQuantity:        441,
			expectedValid:       true, // Should be adjusted, not filtered
			expectedMaxQuantity: 248,  // int(888.8 * 0.28) = 248
			description:         "Should adjust 441 down to 248 (28% of 888.8)",
		},
		{
			name:                "248 shares = exactly 28% of 888.8",
			sellQuantity:        248,
			expectedValid:       true,
			expectedMaxQuantity: 248,
			description:         "Should allow exactly 28%",
		},
		{
			name:                "100 shares < 28% of 888.8",
			sellQuantity:        100,
			expectedValid:       true,
			expectedMaxQuantity: 100,
			description:         "Should allow amounts below the limit",
		},
		{
			name:                "500 shares > 28% of 888.8",
			sellQuantity:        500,
			expectedValid:       true,
			expectedMaxQuantity: 248,
			description:         "Should adjust 500 down to 248 (28% of 888.8)",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			action := planningdomain.ActionCandidate{
				Side:     "SELL",
				ISIN:     "GR1234567890",
				Symbol:   "PPA.GR",
				Name:     "PPA Security",
				Quantity: tt.sellQuantity,
				Price:    10.0,
				ValueEUR: float64(tt.sellQuantity) * 10.0,
				Currency: "EUR",
				Priority: 0.5,
				Reason:   "Test",
			}

			validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, config)

			if tt.expectedValid {
				assert.Len(t, validated, 1, "Should validate the action (possibly adjusted)")
				assert.Len(t, filtered, 0, "Should not filter the action")
				assert.Equal(t, tt.expectedMaxQuantity, validated[0].Quantity,
					"Quantity should be %d, got %d", tt.expectedMaxQuantity, validated[0].Quantity)
			} else {
				assert.Len(t, validated, 0, "Should not validate the action")
				assert.Len(t, filtered, 1, "Should filter the action")
			}
		})
	}
}

func TestEnforcer_EnforceConstraints_MaxSellPercentage_BuyNotAffected(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    1,
	}

	config := &planningdomain.PlannerConfiguration{
		MaxSellPercentage: 0.28,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:         []domain.Position{},
		Securities:        []domain.Security{{Symbol: "TEST.US", ISIN: "US1234567890"}},
		StocksByISIN:      map[string]domain.Security{"US1234567890": {Symbol: "TEST.US", ISIN: "US1234567890"}},
		IneligibleISINs:   map[string]bool{},
		RecentlySoldISINs: map[string]bool{},
		AllowBuy:          true,
	}

	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	// MaxSellPercentage should NOT affect BUY actions
	action := planningdomain.ActionCandidate{
		Side:     "BUY",
		ISIN:     "US1234567890",
		Symbol:   "TEST.US",
		Name:     "Test Security",
		Quantity: 1000, // Large buy amount
		Price:    10.0,
		ValueEUR: 10000.0,
		Currency: "EUR",
		Priority: 0.5,
		Reason:   "Test",
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, config)

	assert.Len(t, validated, 1, "BUY action should be validated")
	assert.Len(t, filtered, 0, "BUY action should not be filtered")
	assert.Equal(t, 1000, validated[0].Quantity, "BUY quantity should not be affected by MaxSellPercentage")
}

func TestEnforcer_EnforceConstraints_MaxSellPercentage_NoPosition(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    1,
	}

	config := &planningdomain.PlannerConfiguration{
		MaxSellPercentage: 0.28,
	}

	// No positions in context
	ctx := &planningdomain.OpportunityContext{
		Positions:         []domain.Position{},
		Securities:        []domain.Security{{Symbol: "TEST.US", ISIN: "US1234567890"}},
		StocksByISIN:      map[string]domain.Security{"US1234567890": {Symbol: "TEST.US", ISIN: "US1234567890"}},
		IneligibleISINs:   map[string]bool{},
		RecentlySoldISINs: map[string]bool{},
		AllowSell:         true,
	}

	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	// Trying to sell a security we don't own
	action := planningdomain.ActionCandidate{
		Side:     "SELL",
		ISIN:     "US1234567890",
		Symbol:   "TEST.US",
		Name:     "Test Security",
		Quantity: 100,
		Price:    10.0,
		ValueEUR: 1000.0,
		Currency: "EUR",
		Priority: 0.5,
		Reason:   "Test",
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, config)

	// Should be filtered because we don't have a position
	assert.Len(t, validated, 0, "Should not validate sell of non-existent position")
	assert.Len(t, filtered, 1, "Should filter sell of non-existent position")
	assert.Contains(t, filtered[0].Reason, "no position found", "Should indicate no position")
}

func TestEnforcer_EnforceConstraints_InvalidSide(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    1,
	}

	ctx := createTestContext(security)
	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	action := planningdomain.ActionCandidate{
		Side:     "INVALID",
		ISIN:     "US1234567890",
		Symbol:   "TEST.US",
		Name:     "Test Security",
		Quantity: 10,
		Price:    50.0,
		ValueEUR: 500.0,
		Currency: "EUR",
		Priority: 0.5,
		Reason:   "Test",
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, nil)

	assert.Len(t, validated, 0)
	assert.Len(t, filtered, 1)
	assert.Contains(t, filtered[0].Reason, "invalid side")
}

func TestEnforcer_EnforceConstraints_InvalidPrice(t *testing.T) {
	log := zerolog.Nop()

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    500,
	}

	ctx := createTestContext(security)
	securityLookup := createSecurityLookup([]universe.Security{security})
	enforcer := NewEnforcer(log, securityLookup)

	action := planningdomain.ActionCandidate{
		Side:     "SELL",
		ISIN:     "US1234567890",
		Symbol:   "TEST.US",
		Name:     "Test Security",
		Quantity: 13,  // Will be rounded to 500
		Price:    0.0, // Invalid price
		ValueEUR: 0.0,
		Currency: "EUR",
		Priority: 0.5,
		Reason:   "Overweight",
	}

	validated, filtered := enforcer.EnforceConstraints([]planningdomain.ActionCandidate{action}, ctx, nil)

	assert.Len(t, validated, 0)
	assert.Len(t, filtered, 1)
	assert.Contains(t, filtered[0].Reason, "invalid price")
}

// Helper functions

func createTestContext(security universe.Security) *planningdomain.OpportunityContext {
	return createTestContextWithMultipleSecurities([]universe.Security{security})
}

func createTestContextWithMultipleSecurities(securities []universe.Security) *planningdomain.OpportunityContext {
	// Convert universe.Security to domain.Security for context
	domainSecurities := make([]domain.Security, len(securities))
	stocksBySymbol := make(map[string]domain.Security)
	stocksByISIN := make(map[string]domain.Security)

	for i, sec := range securities {
		domainSec := domain.Security{
			Symbol: sec.Symbol,
			Name:   sec.Name,
			ISIN:   sec.ISIN,
		}
		domainSecurities[i] = domainSec

		if sec.Symbol != "" {
			stocksBySymbol[sec.Symbol] = domainSec
		}
		if sec.ISIN != "" {
			stocksByISIN[sec.ISIN] = domainSec
		}
	}

	ctx := &planningdomain.OpportunityContext{
		Securities:   domainSecurities,
		StocksByISIN: stocksByISIN,
		AllowSell:    true,
		AllowBuy:     true,
	}

	return ctx
}

// createSecurityLookup creates a lookup function for tests
func createSecurityLookup(securities []universe.Security) func(symbol, isin string) (*universe.Security, bool) {
	// Create maps for lookup
	bySymbol := make(map[string]*universe.Security)
	byISIN := make(map[string]*universe.Security)

	for i := range securities {
		sec := &securities[i]
		if sec.Symbol != "" {
			bySymbol[sec.Symbol] = sec
		}
		if sec.ISIN != "" {
			byISIN[sec.ISIN] = sec
		}
	}

	return func(symbol, isin string) (*universe.Security, bool) {
		// Try ISIN first
		if isin != "" {
			if sec, ok := byISIN[isin]; ok {
				return sec, true
			}
		}
		// Fallback to symbol
		if symbol != "" {
			if sec, ok := bySymbol[symbol]; ok {
				return sec, true
			}
		}
		return nil, false
	}
}
