//go:build integration
// +build integration

package planner

import (
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	planningconstraints "github.com/aristath/sentinel/internal/modules/planning/constraints"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
)

// MockSecurityRepository is a mock security repository for testing
type MockSecurityRepository struct {
	mock.Mock
	securities map[string]*universe.Security // symbol -> security
}

func NewMockSecurityRepository() *MockSecurityRepository {
	return &MockSecurityRepository{
		securities: make(map[string]*universe.Security),
	}
}

func (m *MockSecurityRepository) AddSecurity(sec *universe.Security) {
	if sec.Symbol != "" {
		m.securities[sec.Symbol] = sec
	}
	if sec.ISIN != "" {
		m.securities[sec.ISIN] = sec
	}
}

func (m *MockSecurityRepository) GetBySymbol(symbol string) (*universe.Security, error) {
	if sec, ok := m.securities[symbol]; ok {
		return sec, nil
	}
	return nil, nil
}

func (m *MockSecurityRepository) GetByISIN(isin string) (*universe.Security, error) {
	if sec, ok := m.securities[isin]; ok {
		return sec, nil
	}
	return nil, nil
}

func TestPlanner_ConstraintEnforcement_BYDSellFiltered(t *testing.T) {
	// Setup: Create mock security repository with BYD (allow_sell=false, min_lot=500)
	mockSecurityRepo := NewMockSecurityRepository()
	bydSecurity := &universe.Security{
		Symbol:    "BYD.285.AS",
		Name:      "BYD Electronic",
		ISIN:      "KYG1170T1067",
		AllowSell: false, // Should be filtered
		AllowBuy:  true,
		MinLot:    500,
	}
	mockSecurityRepo.AddSecurity(bydSecurity)

	validSecurity := &universe.Security{
		Symbol:    "AAPL.US",
		Name:      "Apple Inc.",
		ISIN:      "US0378331005",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    1,
	}
	mockSecurityRepo.AddSecurity(validSecurity)

	// Create planner with mock repository
	log := zerolog.Nop()
	opportunitiesService := &MockOpportunitiesService{}
	sequencesService := &MockSequencesService{}
	evaluationService := &MockEvaluationService{}

	// Create security lookup function that uses mock repository
	securityLookup := func(symbol, isin string) (*universe.Security, bool) {
		var sec *universe.Security
		var err error
		if isin != "" {
			sec, err = mockSecurityRepo.GetByISIN(isin)
			if err == nil && sec != nil {
				return sec, true
			}
		}
		if symbol != "" {
			sec, err = mockSecurityRepo.GetBySymbol(symbol)
			if err == nil && sec != nil {
				return sec, true
			}
		}
		return nil, false
	}

	// Create planner with constraint enforcer using mock lookup
	planner := createTestPlannerWithLookup(opportunitiesService, sequencesService, evaluationService, securityLookup, log)

	// Create a sequence with actions including BYD sell (should be filtered)
	sequence := planningdomain.ActionSequence{
		Actions: []planningdomain.ActionCandidate{
			{
				Side:     "SELL",
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
				Symbol:   "AAPL.US",
				Name:     "Apple Inc.",
				Quantity: 10,
				Price:    150.0,
				ValueEUR: 1500.0,
				Currency: "EUR",
				Priority: 0.5,
				Reason:   "Underweight",
			},
		},
		Priority:    0.8,
		PatternType: "rebalance",
	}

	// Create opportunity context
	ctx := createTestOpportunityContext(bydSecurity, validSecurity)

	// Convert to plan (this will apply constraint enforcement)
	plan := planner.convertToPlan(sequence, ctx, 0.0, 100.0)

	// Verify: BYD sell should be filtered out, only AAPL buy should remain
	require.NotNil(t, plan)
	assert.Len(t, plan.Steps, 1, "BYD sell should be filtered out")
	assert.Equal(t, "AAPL.US", plan.Steps[0].Symbol)
	assert.Equal(t, "BUY", plan.Steps[0].Side)
}

func TestPlanner_ConstraintEnforcement_LotSizeAdjusted(t *testing.T) {
	// Setup: Create security with min_lot=500
	mockSecurityRepo := NewMockSecurityRepository()
	security := &universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    500, // Requires lot size of 500
	}
	mockSecurityRepo.AddSecurity(security)

	log := zerolog.Nop()
	securityLookup := func(symbol, isin string) (*universe.Security, bool) {
		sec, err := mockSecurityRepo.GetBySymbol(symbol)
		if err == nil && sec != nil {
			return sec, true
		}
		return nil, false
	}
	planner := createTestPlannerWithLookup(nil, nil, nil, securityLookup, log)

	// Create sequence with quantity 13 (should be rounded up to 500)
	sequence := planningdomain.ActionSequence{
		Actions: []planningdomain.ActionCandidate{
			{
				Side:     "SELL",
				Symbol:   "TEST.US",
				Name:     "Test Security",
				Quantity: 13, // Should be rounded to 500
				Price:    36.0,
				ValueEUR: 468.0, // Original value
				Currency: "EUR",
				Priority: 0.8,
				Reason:   "Overweight",
			},
		},
		Priority:    0.8,
		PatternType: "rebalance",
	}

	ctx := createTestOpportunityContext(security)

	// Convert to plan
	plan := planner.convertToPlan(sequence, ctx, 0.0, 100.0)

	// Verify: Quantity should be adjusted to 500, value recalculated
	require.NotNil(t, plan)
	require.Len(t, plan.Steps, 1)
	assert.Equal(t, 500, plan.Steps[0].Quantity, "Quantity should be rounded up to 500")
	assert.Equal(t, 18000.0, plan.Steps[0].EstimatedValue, "Value should be recalculated: 500 * 36.0 = 18000.0")
}

func TestPlanner_ConstraintEnforcement_MultipleConstraints(t *testing.T) {
	// Test multiple constraints: allow_sell=false AND lot size
	mockSecurityRepo := NewMockSecurityRepository()

	bydSecurity := &universe.Security{
		Symbol:    "BYD.285.AS",
		Name:      "BYD Electronic",
		ISIN:      "KYG1170T1067",
		AllowSell: false, // Should be filtered
		AllowBuy:  true,
		MinLot:    500,
	}
	mockSecurityRepo.AddSecurity(bydSecurity)

	lotSizeSecurity := &universe.Security{
		Symbol:    "LOT.US",
		Name:      "Lot Size Security",
		ISIN:      "US9876543210",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    500,
	}
	mockSecurityRepo.AddSecurity(lotSizeSecurity)

	validSecurity := &universe.Security{
		Symbol:    "VALID.US",
		Name:      "Valid Security",
		ISIN:      "US1111111111",
		AllowSell: true,
		AllowBuy:  true,
		MinLot:    1,
	}
	mockSecurityRepo.AddSecurity(validSecurity)

	sequence := planningdomain.ActionSequence{
		Actions: []planningdomain.ActionCandidate{
			{
				Side:     "SELL",
				Symbol:   "BYD.285.AS",
				Quantity: 13,
				Price:    36.0,
				ValueEUR: 468.0,
				Currency: "EUR",
				Priority: 0.8,
				Reason:   "Overweight",
			},
			{
				Side:     "SELL",
				Symbol:   "LOT.US",
				Quantity: 13, // Should be rounded to 500
				Price:    10.0,
				ValueEUR: 130.0,
				Currency: "EUR",
				Priority: 0.7,
				Reason:   "Overweight",
			},
			{
				Side:     "BUY",
				Symbol:   "VALID.US",
				Quantity: 100,
				Price:    50.0,
				ValueEUR: 5000.0,
				Currency: "EUR",
				Priority: 0.5,
				Reason:   "Underweight",
			},
		},
		Priority:    0.8,
		PatternType: "rebalance",
	}

	ctx := createTestOpportunityContext(bydSecurity, lotSizeSecurity, validSecurity)

	// Create planner with security lookup
	log := zerolog.Nop()
	securityLookup := func(symbol, isin string) (*universe.Security, bool) {
		var sec *universe.Security
		var err error
		if isin != "" {
			sec, err = mockSecurityRepo.GetByISIN(isin)
			if err == nil && sec != nil {
				return sec, true
			}
		}
		if symbol != "" {
			sec, err = mockSecurityRepo.GetBySymbol(symbol)
			if err == nil && sec != nil {
				return sec, true
			}
		}
		return nil, false
	}
	testPlanner := createTestPlannerWithLookup(nil, nil, nil, securityLookup, log)

	plan := testPlanner.convertToPlan(sequence, ctx, 0.0, 100.0)

	// Verify: BYD filtered out, LOT adjusted, VALID unchanged
	require.NotNil(t, plan)
	assert.Len(t, plan.Steps, 2, "BYD should be filtered, LOT and VALID should remain")

	// Find LOT and VALID steps
	var lotStep, validStep *planningdomain.HolisticStep
	for i := range plan.Steps {
		if plan.Steps[i].Symbol == "LOT.US" {
			lotStep = &plan.Steps[i]
		}
		if plan.Steps[i].Symbol == "VALID.US" {
			validStep = &plan.Steps[i]
		}
	}

	require.NotNil(t, lotStep, "LOT step should exist")
	require.NotNil(t, validStep, "VALID step should exist")

	assert.Equal(t, 500, lotStep.Quantity, "LOT quantity should be rounded to 500")
	assert.Equal(t, 5000.0, lotStep.EstimatedValue, "LOT value should be recalculated: 500 * 10.0")
	assert.Equal(t, 100, validStep.Quantity, "VALID quantity should remain unchanged")
	assert.Equal(t, 5000.0, validStep.EstimatedValue, "VALID value should remain unchanged")
}

// Helper functions

func createTestOpportunityContext(securities ...*universe.Security) *planningdomain.OpportunityContext {
	// Convert to domain securities
	domainSecurities := make([]domain.Security, len(securities))
	stocksBySymbol := make(map[string]domain.Security)
	stocksByISIN := make(map[string]domain.Security)

	for _, sec := range securities {
		domainSec := domain.Security{
			Symbol: sec.Symbol,
			Name:   sec.Name,
			ISIN:   sec.ISIN,
		}
		domainSecurities = append(domainSecurities, domainSec)

		if sec.Symbol != "" {
			stocksBySymbol[sec.Symbol] = domainSec
		}
		if sec.ISIN != "" {
			stocksByISIN[sec.ISIN] = domainSec
		}
	}

	return &planningdomain.OpportunityContext{
		Securities:     domainSecurities,
		StocksBySymbol: stocksBySymbol,
		StocksByISIN:   stocksByISIN,
		AllowSell:      true,
		AllowBuy:       true,
		CurrentPrices:  make(map[string]float64),
	}
}

// Helper to create planner with custom security lookup for testing
func createTestPlannerWithLookup(
	opportunitiesService *MockOpportunitiesService,
	sequencesService *MockSequencesService,
	evaluationService *MockEvaluationService,
	securityLookup func(string, string) (*universe.Security, bool),
	log zerolog.Logger,
) *Planner {
	constraintEnforcer := planningconstraints.NewEnforcer(log, securityLookup)

	return &Planner{
		opportunitiesService: nil, // Not needed for convertToPlan tests
		sequencesService:     nil,
		evaluationService:    nil,
		constraintEnforcer:   constraintEnforcer,
		log:                  log,
	}
}

// Mock services for testing (minimal implementations)

type MockOpportunitiesService struct{}

type MockSequencesService struct{}

type MockEvaluationService struct{}
