package domain

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestPreFilteredReason(t *testing.T) {
	t.Run("creates with reason and dismissed flag", func(t *testing.T) {
		reason := PreFilteredReason{
			Reason:    "score below minimum",
			Dismissed: false,
		}

		assert.Equal(t, "score below minimum", reason.Reason)
		assert.False(t, reason.Dismissed)
	})

	t.Run("dismissed flag can be true", func(t *testing.T) {
		reason := PreFilteredReason{
			Reason:    "value trap detected",
			Dismissed: true,
		}

		assert.Equal(t, "value trap detected", reason.Reason)
		assert.True(t, reason.Dismissed)
	})
}

func TestPreFilteredSecurity(t *testing.T) {
	t.Run("creates with all fields", func(t *testing.T) {
		pf := PreFilteredSecurity{
			ISIN:       "US0378331005",
			Symbol:     "AAPL",
			Name:       "Apple Inc.",
			Calculator: "opportunity_buys",
			Reasons: []PreFilteredReason{
				{Reason: "score 0.45 below minimum 0.65", Dismissed: false},
				{Reason: "quality gate failed", Dismissed: true},
			},
		}

		assert.Equal(t, "US0378331005", pf.ISIN)
		assert.Equal(t, "AAPL", pf.Symbol)
		assert.Equal(t, "Apple Inc.", pf.Name)
		assert.Equal(t, "opportunity_buys", pf.Calculator)
		assert.Len(t, pf.Reasons, 2)
		assert.Equal(t, "score 0.45 below minimum 0.65", pf.Reasons[0].Reason)
		assert.False(t, pf.Reasons[0].Dismissed)
		assert.True(t, pf.Reasons[1].Dismissed)
	})

	t.Run("can have empty reasons", func(t *testing.T) {
		pf := PreFilteredSecurity{
			ISIN:       "US0378331005",
			Symbol:     "AAPL",
			Calculator: "averaging_down",
			Reasons:    []PreFilteredReason{},
		}

		assert.Equal(t, "US0378331005", pf.ISIN)
		assert.Equal(t, "AAPL", pf.Symbol)
		assert.Equal(t, "averaging_down", pf.Calculator)
		assert.Empty(t, pf.Reasons)
	})
}

func TestCalculatorResult(t *testing.T) {
	t.Run("creates with candidates and pre-filtered", func(t *testing.T) {
		result := CalculatorResult{
			Candidates: []ActionCandidate{
				{Symbol: "AAPL", Side: "BUY", Priority: 0.8},
			},
			PreFiltered: []PreFilteredSecurity{
				{Symbol: "MSFT", Calculator: "opportunity_buys", Reasons: []PreFilteredReason{{Reason: "value trap", Dismissed: false}}},
				{Symbol: "GOOG", Calculator: "opportunity_buys", Reasons: []PreFilteredReason{{Reason: "low score", Dismissed: true}}},
			},
		}

		assert.Len(t, result.Candidates, 1)
		assert.Len(t, result.PreFiltered, 2)
		assert.Equal(t, "AAPL", result.Candidates[0].Symbol)
		assert.Equal(t, "MSFT", result.PreFiltered[0].Symbol)
		assert.False(t, result.PreFiltered[0].Reasons[0].Dismissed)
		assert.True(t, result.PreFiltered[1].Reasons[0].Dismissed)
	})

	t.Run("handles empty results", func(t *testing.T) {
		result := CalculatorResult{
			Candidates:  []ActionCandidate{},
			PreFiltered: []PreFilteredSecurity{},
		}

		assert.Empty(t, result.Candidates)
		assert.Empty(t, result.PreFiltered)
	})

	t.Run("nil slices behave correctly", func(t *testing.T) {
		result := CalculatorResult{}

		assert.Nil(t, result.Candidates)
		assert.Nil(t, result.PreFiltered)
	})
}

func TestOpportunitiesResultByCategory(t *testing.T) {
	t.Run("organizes by category with pre-filtered", func(t *testing.T) {
		result := OpportunitiesResultByCategory{
			OpportunityCategoryOpportunityBuys: CalculatorResult{
				Candidates: []ActionCandidate{
					{Symbol: "AAPL", Side: "BUY"},
				},
				PreFiltered: []PreFilteredSecurity{
					{Symbol: "MSFT", Reasons: []PreFilteredReason{{Reason: "value trap", Dismissed: false}}},
				},
			},
			OpportunityCategoryAveragingDown: CalculatorResult{
				Candidates:  []ActionCandidate{},
				PreFiltered: []PreFilteredSecurity{},
			},
		}

		assert.Len(t, result[OpportunityCategoryOpportunityBuys].Candidates, 1)
		assert.Len(t, result[OpportunityCategoryOpportunityBuys].PreFiltered, 1)
		assert.Empty(t, result[OpportunityCategoryAveragingDown].Candidates)
	})

	t.Run("AllPreFiltered aggregates across categories", func(t *testing.T) {
		result := OpportunitiesResultByCategory{
			OpportunityCategoryOpportunityBuys: CalculatorResult{
				PreFiltered: []PreFilteredSecurity{
					{Symbol: "AAPL", Calculator: "opportunity_buys"},
					{Symbol: "MSFT", Calculator: "opportunity_buys"},
				},
			},
			OpportunityCategoryAveragingDown: CalculatorResult{
				PreFiltered: []PreFilteredSecurity{
					{Symbol: "GOOG", Calculator: "averaging_down"},
				},
			},
		}

		all := result.AllPreFiltered()
		assert.Len(t, all, 3)
	})

	t.Run("AllCandidates aggregates across categories", func(t *testing.T) {
		result := OpportunitiesResultByCategory{
			OpportunityCategoryOpportunityBuys: CalculatorResult{
				Candidates: []ActionCandidate{
					{Symbol: "AAPL"},
					{Symbol: "MSFT"},
				},
			},
			OpportunityCategoryProfitTaking: CalculatorResult{
				Candidates: []ActionCandidate{
					{Symbol: "GOOG"},
				},
			},
		}

		all := result.AllCandidates()
		assert.Len(t, all, 3)
	})

	t.Run("ToOpportunitiesByCategory extracts just candidates", func(t *testing.T) {
		result := OpportunitiesResultByCategory{
			OpportunityCategoryOpportunityBuys: CalculatorResult{
				Candidates: []ActionCandidate{
					{Symbol: "AAPL"},
				},
				PreFiltered: []PreFilteredSecurity{
					{Symbol: "MSFT"},
				},
			},
		}

		legacy := result.ToOpportunitiesByCategory()
		assert.Len(t, legacy[OpportunityCategoryOpportunityBuys], 1)
		assert.Equal(t, "AAPL", legacy[OpportunityCategoryOpportunityBuys][0].Symbol)
	})
}
