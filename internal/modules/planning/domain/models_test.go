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

func TestRejectedSequence(t *testing.T) {
	t.Run("creates with all fields", func(t *testing.T) {
		rs := RejectedSequence{
			Rank: 2,
			Actions: []ActionCandidate{
				{Side: "SELL", Symbol: "AAPL", Quantity: 5, ValueEUR: 875.50},
				{Side: "BUY", Symbol: "GOOGL", Quantity: 3, ValueEUR: 450.25},
			},
			Score:    0.843,
			Feasible: true,
			Reason:   "lower_score",
		}

		assert.Equal(t, 2, rs.Rank)
		assert.Len(t, rs.Actions, 2)
		assert.Equal(t, "SELL", rs.Actions[0].Side)
		assert.Equal(t, "AAPL", rs.Actions[0].Symbol)
		assert.Equal(t, 0.843, rs.Score)
		assert.True(t, rs.Feasible)
		assert.Equal(t, "lower_score", rs.Reason)
	})

	t.Run("infeasible sequence", func(t *testing.T) {
		rs := RejectedSequence{
			Rank: 100,
			Actions: []ActionCandidate{
				{Side: "BUY", Symbol: "NVDA", Quantity: 100, ValueEUR: 50000.00},
			},
			Score:    0.412,
			Feasible: false,
			Reason:   "insufficient_cash",
		}

		assert.Equal(t, 100, rs.Rank)
		assert.Len(t, rs.Actions, 1)
		assert.Equal(t, "NVDA", rs.Actions[0].Symbol)
		assert.Equal(t, 0.412, rs.Score)
		assert.False(t, rs.Feasible)
		assert.Equal(t, "insufficient_cash", rs.Reason)
	})

	t.Run("single action sequence", func(t *testing.T) {
		rs := RejectedSequence{
			Rank: 3,
			Actions: []ActionCandidate{
				{Side: "BUY", Symbol: "MSFT", Quantity: 10, ValueEUR: 3500.00},
			},
			Score:    0.841,
			Feasible: true,
			Reason:   "lower_score",
		}

		assert.Equal(t, 3, rs.Rank)
		assert.Len(t, rs.Actions, 1)
		assert.Equal(t, "BUY", rs.Actions[0].Side)
		assert.Equal(t, 0.841, rs.Score)
		assert.True(t, rs.Feasible)
		assert.Equal(t, "lower_score", rs.Reason)
	})
}

func TestPlannerRunSummary(t *testing.T) {
	t.Run("creates with all metrics", func(t *testing.T) {
		summary := PlannerRunSummary{
			Candidates:          15,
			SequencesTotal:      2500,
			SequencesFeasible:   2100,
			SequencesInfeasible: 400,
			BestScore:           0.847,
			AvgScore:            0.612,
			ThroughputSeqPerSec: 520.5,
			PeakMemoryMB:        45.2,
			TotalDurationMS:     4812,
		}

		assert.Equal(t, 15, summary.Candidates)
		assert.Equal(t, 2500, summary.SequencesTotal)
		assert.Equal(t, 2100, summary.SequencesFeasible)
		assert.Equal(t, 400, summary.SequencesInfeasible)
		assert.Equal(t, 0.847, summary.BestScore)
		assert.Equal(t, 0.612, summary.AvgScore)
		assert.Equal(t, 520.5, summary.ThroughputSeqPerSec)
		assert.Equal(t, 45.2, summary.PeakMemoryMB)
		assert.Equal(t, int64(4812), summary.TotalDurationMS)
	})
}

func TestStageInfo(t *testing.T) {
	t.Run("pending stage", func(t *testing.T) {
		stage := StageInfo{
			Name:   "Store recommendations",
			Status: StageStatusPending,
		}

		assert.Equal(t, "Store recommendations", stage.Name)
		assert.Equal(t, StageStatusPending, stage.Status)
		assert.Equal(t, int64(0), stage.DurationMS)
	})

	t.Run("running stage", func(t *testing.T) {
		stage := StageInfo{
			Name:   "Creating trade plan",
			Status: StageStatusRunning,
		}

		assert.Equal(t, "Creating trade plan", stage.Name)
		assert.Equal(t, StageStatusRunning, stage.Status)
	})

	t.Run("completed stage with duration", func(t *testing.T) {
		stage := StageInfo{
			Name:       "Portfolio hash",
			Status:     StageStatusCompleted,
			DurationMS: 23,
		}

		assert.Equal(t, "Portfolio hash", stage.Name)
		assert.Equal(t, StageStatusCompleted, stage.Status)
		assert.Equal(t, int64(23), stage.DurationMS)
	})

	t.Run("completed stage with details", func(t *testing.T) {
		stage := StageInfo{
			Name:       "Creating trade plan",
			Status:     StageStatusCompleted,
			DurationMS: 4521,
			Details: map[string]any{
				"candidates":         15,
				"sequences_total":    2500,
				"sequences_feasible": 2100,
				"best_score":         0.847,
			},
		}

		assert.Equal(t, "Creating trade plan", stage.Name)
		assert.Equal(t, StageStatusCompleted, stage.Status)
		assert.Equal(t, int64(4521), stage.DurationMS)
		assert.NotNil(t, stage.Details)
		assert.Equal(t, 15, stage.Details["candidates"])
		assert.Equal(t, 0.847, stage.Details["best_score"])
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

		opportunities := result.ToOpportunitiesByCategory()
		assert.Len(t, opportunities[OpportunityCategoryOpportunityBuys], 1)
		assert.Equal(t, "AAPL", opportunities[OpportunityCategoryOpportunityBuys][0].Symbol)
	})
}
