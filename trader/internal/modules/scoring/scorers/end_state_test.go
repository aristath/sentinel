package scorers

import (
	"math"
	"testing"
)

func TestGetRiskProfileWeights(t *testing.T) {
	scorer := NewEndStateScorer()

	tests := []struct {
		name        string
		riskProfile string
		description string
		wantSum     float64
	}{
		{
			name:        "Conservative profile",
			riskProfile: "conservative",
			wantSum:     1.0,
			description: "Conservative weights should sum to 1.0",
		},
		{
			name:        "Balanced profile",
			riskProfile: "balanced",
			wantSum:     1.0,
			description: "Balanced weights should sum to 1.0",
		},
		{
			name:        "Aggressive profile",
			riskProfile: "aggressive",
			wantSum:     1.0,
			description: "Aggressive weights should sum to 1.0",
		},
		{
			name:        "Unknown profile (defaults to balanced)",
			riskProfile: "unknown",
			wantSum:     1.0,
			description: "Unknown profile should default to balanced",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			weights := scorer.GetRiskProfileWeights(tt.riskProfile)

			sum := weights.WeightTotalReturn +
				weights.WeightDiversification +
				weights.WeightLongTermPromise +
				weights.WeightStability +
				weights.WeightOpinion

			if math.Abs(sum-tt.wantSum) > 0.001 {
				t.Errorf("Weights sum = %v, want %v\nDescription: %s",
					sum, tt.wantSum, tt.description)
			}

			// Conservative should emphasize stability
			if tt.riskProfile == "conservative" && weights.WeightStability < 0.15 {
				t.Errorf("Conservative profile should emphasize stability, got %v",
					weights.WeightStability)
			}

			// Aggressive should emphasize returns
			if tt.riskProfile == "aggressive" && weights.WeightTotalReturn < 0.40 {
				t.Errorf("Aggressive profile should emphasize returns, got %v",
					weights.WeightTotalReturn)
			}
		})
	}
}

func TestScoreTotalReturn(t *testing.T) {
	scorer := NewEndStateScorer()

	tests := []struct {
		name        string
		description string
		totalReturn float64
		target      float64
		wantScore   float64
	}{
		{
			name:        "At target (12%)",
			totalReturn: 0.12,
			target:      0.12,
			wantScore:   1.0,
			description: "Return at target should score 1.0",
		},
		{
			name:        "Slightly above target",
			totalReturn: 0.15,
			target:      0.12,
			wantScore:   0.95, // Close to 1.0, within right sigma
			description: "Return slightly above target should score high",
		},
		{
			name:        "Slightly below target",
			totalReturn: 0.10,
			target:      0.12,
			wantScore:   0.90, // Close to 1.0, within left sigma
			description: "Return slightly below target should score high",
		},
		{
			name:        "Zero return",
			totalReturn: 0.0,
			target:      0.12,
			wantScore:   0.15, // Floor score
			description: "Zero return should score at floor (0.15)",
		},
		{
			name:        "Negative return",
			totalReturn: -0.05,
			target:      0.12,
			wantScore:   0.15, // Floor score
			description: "Negative return should score at floor (0.15)",
		},
		{
			name:        "Very high return (20%)",
			totalReturn: 0.20,
			target:      0.12,
			wantScore:   0.75, // Drops off with right sigma
			description: "Very high return should score less than target",
		},
		{
			name:        "Very low return (2%)",
			totalReturn: 0.02,
			target:      0.12,
			wantScore:   0.25, // Drops off sharply with left sigma
			description: "Very low return should score low",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := scorer.ScoreTotalReturn(tt.totalReturn, tt.target)

			// Allow for some tolerance in bell curve calculations
			if math.Abs(got-tt.wantScore) > 0.15 {
				t.Errorf("ScoreTotalReturn() = %v, want ~%v (diff: %v)\nDescription: %s",
					got, tt.wantScore, math.Abs(got-tt.wantScore), tt.description)
			}

			// Ensure score is in valid range
			if got < 0.15 || got > 1.0 {
				t.Errorf("Score %v out of range [0.15, 1.0]", got)
			}
		})
	}
}

func TestCalculateTotalReturnScore(t *testing.T) {
	scorer := NewEndStateScorer()

	tests := []struct {
		metrics     map[string]float64
		name        string
		description string
		wantScore   float64
	}{
		{
			name: "Good total return (12%)",
			metrics: map[string]float64{
				"CAGR_5Y":        0.10,
				"DIVIDEND_YIELD": 0.02,
			},
			wantScore:   1.0, // 10% + 2% = 12% (target)
			description: "12% total return should score 1.0",
		},
		{
			name: "High CAGR, no dividend",
			metrics: map[string]float64{
				"CAGR_5Y": 0.15,
			},
			wantScore:   0.95, // 15% is good but above target
			description: "15% CAGR with no dividend should score high",
		},
		{
			name: "Low CAGR, high dividend",
			metrics: map[string]float64{
				"CAGR_5Y":        0.05,
				"DIVIDEND_YIELD": 0.05,
			},
			wantScore:   0.95, // 10% total is close to target
			description: "10% total return should score decent",
		},
		{
			name:        "Missing metrics",
			metrics:     map[string]float64{},
			wantScore:   0.15, // Zero return = floor
			description: "Missing metrics should return floor score",
		},
		{
			name: "Only CAGR present",
			metrics: map[string]float64{
				"CAGR_5Y": 0.12,
			},
			wantScore:   1.0, // 12% CAGR alone = target
			description: "12% CAGR alone should score 1.0",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := scorer.CalculateTotalReturnScore(tt.metrics)

			if math.Abs(result.Score-tt.wantScore) > 0.15 {
				t.Errorf("Score = %v, want ~%v\nDescription: %s",
					result.Score, tt.wantScore, tt.description)
			}

			// Verify total return is calculated correctly
			expectedTotal := tt.metrics["CAGR_5Y"] + tt.metrics["DIVIDEND_YIELD"]
			if math.Abs(result.TotalReturn-expectedTotal) > 0.001 {
				t.Errorf("TotalReturn = %v, want %v", result.TotalReturn, expectedTotal)
			}
		})
	}
}

func TestCalculateLongTermPromise(t *testing.T) {
	scorer := NewEndStateScorer()

	tests := []struct {
		metrics     map[string]float64
		name        string
		description string
		wantScore   float64
	}{
		{
			name: "Excellent long-term promise",
			metrics: map[string]float64{
				"CONSISTENCY_SCORE":    1.0,
				"FINANCIAL_STRENGTH":   1.0,
				"DIVIDEND_CONSISTENCY": 1.0,
				"SORTINO":              2.5,
			},
			wantScore:   1.0,
			description: "Perfect metrics should score 1.0",
		},
		{
			name: "Good long-term promise",
			metrics: map[string]float64{
				"CONSISTENCY_SCORE":    0.8,
				"FINANCIAL_STRENGTH":   0.7,
				"DIVIDEND_CONSISTENCY": 0.8,
				"SORTINO":              1.5,
			},
			wantScore:   0.75,
			description: "Good metrics should score ~0.75",
		},
		{
			name: "Average long-term promise",
			metrics: map[string]float64{
				"CONSISTENCY_SCORE":    0.5,
				"FINANCIAL_STRENGTH":   0.5,
				"DIVIDEND_CONSISTENCY": 0.5,
				"SORTINO":              1.0,
			},
			wantScore:   0.55,
			description: "Average metrics should score ~0.55",
		},
		{
			name:        "Missing all metrics (defaults to 0.5)",
			metrics:     map[string]float64{},
			wantScore:   0.5,
			description: "Missing metrics should default to neutral",
		},
		{
			name: "Derive dividend consistency from payout ratio",
			metrics: map[string]float64{
				"CONSISTENCY_SCORE":  0.6,
				"FINANCIAL_STRENGTH": 0.6,
				"PAYOUT_RATIO":       0.5, // Optimal payout = 1.0 consistency
				"SORTINO":            1.2,
			},
			wantScore:   0.65,
			description: "Should derive consistency from payout ratio",
		},
		{
			name: "High Sortino boosts score",
			metrics: map[string]float64{
				"CONSISTENCY_SCORE":    0.5,
				"FINANCIAL_STRENGTH":   0.5,
				"DIVIDEND_CONSISTENCY": 0.5,
				"SORTINO":              3.0, // Excellent Sortino
			},
			wantScore:   0.55,
			description: "High Sortino should boost overall score",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := scorer.CalculateLongTermPromise(tt.metrics)

			if math.Abs(result.Score-tt.wantScore) > 0.10 {
				t.Errorf("Score = %v, want ~%v\nDescription: %s",
					result.Score, tt.wantScore, tt.description)
			}

			// Verify score is in valid range
			if result.Score < 0.0 || result.Score > 1.0 {
				t.Errorf("Score %v out of range [0.0, 1.0]", result.Score)
			}
		})
	}
}

func TestCalculateStabilityScore(t *testing.T) {
	scorer := NewEndStateScorer()

	tests := []struct {
		metrics     map[string]float64
		name        string
		description string
		wantScore   float64
	}{
		{
			name: "Excellent stability",
			metrics: map[string]float64{
				"VOLATILITY_ANNUAL": 0.10,  // Low volatility
				"MAX_DRAWDOWN":      -0.05, // Small drawdown
				"SHARPE":            2.5,   // Excellent Sharpe
			},
			wantScore:   1.0,
			description: "Low volatility, small drawdown, high Sharpe should score 1.0",
		},
		{
			name: "Good stability",
			metrics: map[string]float64{
				"VOLATILITY_ANNUAL": 0.20,  // Moderate volatility
				"MAX_DRAWDOWN":      -0.15, // Moderate drawdown
				"SHARPE":            1.5,   // Good Sharpe
			},
			wantScore:   0.75,
			description: "Moderate metrics should score ~0.75",
		},
		{
			name: "Poor stability",
			metrics: map[string]float64{
				"VOLATILITY_ANNUAL": 0.40,  // High volatility
				"MAX_DRAWDOWN":      -0.40, // Large drawdown
				"SHARPE":            0.3,   // Low Sharpe
			},
			wantScore:   0.30,
			description: "High volatility and drawdown should score low",
		},
		{
			name:        "Missing all metrics (defaults to 0.5)",
			metrics:     map[string]float64{},
			wantScore:   0.5,
			description: "Missing metrics should default to neutral",
		},
		{
			name: "Very low volatility compensates for other factors",
			metrics: map[string]float64{
				"VOLATILITY_ANNUAL": 0.08,  // Very low
				"MAX_DRAWDOWN":      -0.25, // Moderate
				"SHARPE":            0.8,   // Moderate
			},
			wantScore:   0.70,
			description: "Very low volatility should boost score significantly",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := scorer.CalculateStabilityScore(tt.metrics)

			if math.Abs(result.Score-tt.wantScore) > 0.15 {
				t.Errorf("Score = %v, want ~%v\nDescription: %s",
					result.Score, tt.wantScore, tt.description)
			}

			// Verify score is in valid range
			if result.Score < 0.0 || result.Score > 1.0 {
				t.Errorf("Score %v out of range [0.0, 1.0]", result.Score)
			}
		})
	}
}

func TestCalculatePortfolioEndStateScore(t *testing.T) {
	scorer := NewEndStateScorer()

	tests := []struct {
		positions            map[string]float64
		metricsCache         map[string]map[string]float64
		name                 string
		riskProfile          string
		description          string
		totalValue           float64
		diversificationScore float64
		opinionScore         float64
		wantScore            float64
		wantError            bool
	}{
		{
			name: "Excellent portfolio",
			positions: map[string]float64{
				"AAPL": 5000.0,
				"MSFT": 5000.0,
			},
			totalValue:           10000.0,
			diversificationScore: 0.9,
			metricsCache: map[string]map[string]float64{
				"AAPL": {
					"CAGR_5Y":              0.10,
					"DIVIDEND_YIELD":       0.02,
					"CONSISTENCY_SCORE":    0.9,
					"FINANCIAL_STRENGTH":   0.9,
					"DIVIDEND_CONSISTENCY": 0.9,
					"SORTINO":              2.0,
					"VOLATILITY_ANNUAL":    0.15,
					"MAX_DRAWDOWN":         -0.10,
					"SHARPE":               2.0,
				},
				"MSFT": {
					"CAGR_5Y":              0.12,
					"DIVIDEND_YIELD":       0.01,
					"CONSISTENCY_SCORE":    0.85,
					"FINANCIAL_STRENGTH":   0.95,
					"DIVIDEND_CONSISTENCY": 0.85,
					"SORTINO":              1.8,
					"VOLATILITY_ANNUAL":    0.18,
					"MAX_DRAWDOWN":         -0.12,
					"SHARPE":               1.8,
				},
			},
			opinionScore: 0.8,
			riskProfile:  "balanced",
			wantScore:    0.85,
			description:  "Excellent portfolio should score high",
		},
		{
			name: "Average portfolio",
			positions: map[string]float64{
				"STOCK1": 10000.0,
			},
			totalValue:           10000.0,
			diversificationScore: 0.5,
			metricsCache: map[string]map[string]float64{
				"STOCK1": {
					"CAGR_5Y":            0.08,
					"DIVIDEND_YIELD":     0.02,
					"CONSISTENCY_SCORE":  0.5,
					"FINANCIAL_STRENGTH": 0.5,
					"VOLATILITY_ANNUAL":  0.25,
					"MAX_DRAWDOWN":       -0.20,
					"SHARPE":             1.0,
				},
			},
			opinionScore: 0.5,
			riskProfile:  "balanced",
			wantScore:    0.50,
			description:  "Average portfolio should score around 0.5",
		},
		{
			name:                 "Empty portfolio",
			positions:            map[string]float64{},
			totalValue:           0.0,
			diversificationScore: 0.5,
			metricsCache:         map[string]map[string]float64{},
			opinionScore:         0.5,
			riskProfile:          "balanced",
			wantError:            true,
			description:          "Empty portfolio should return error",
		},
		{
			name: "Conservative profile emphasizes stability",
			positions: map[string]float64{
				"STABLE": 10000.0,
			},
			totalValue:           10000.0,
			diversificationScore: 0.7,
			metricsCache: map[string]map[string]float64{
				"STABLE": {
					"CAGR_5Y":           0.06,
					"DIVIDEND_YIELD":    0.04, // 10% total
					"VOLATILITY_ANNUAL": 0.10, // Very stable
					"MAX_DRAWDOWN":      -0.05,
					"SHARPE":            2.0,
				},
			},
			opinionScore: 0.5,
			riskProfile:  "conservative",
			wantScore:    0.70,
			description:  "Conservative profile should favor stable assets",
		},
		{
			name: "Aggressive profile emphasizes returns",
			positions: map[string]float64{
				"GROWTH": 10000.0,
			},
			totalValue:           10000.0,
			diversificationScore: 0.5,
			metricsCache: map[string]map[string]float64{
				"GROWTH": {
					"CAGR_5Y":           0.20, // High growth
					"DIVIDEND_YIELD":    0.00,
					"VOLATILITY_ANNUAL": 0.35, // High volatility
					"MAX_DRAWDOWN":      -0.30,
					"SHARPE":            1.2,
				},
			},
			opinionScore: 0.5,
			riskProfile:  "aggressive",
			wantScore:    0.65,
			description:  "Aggressive profile should favor high-return assets",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := scorer.CalculatePortfolioEndStateScore(
				tt.positions,
				tt.totalValue,
				tt.diversificationScore,
				tt.metricsCache,
				tt.opinionScore,
				tt.riskProfile,
			)

			if tt.wantError {
				if result.Error == "" {
					t.Errorf("Expected error but got none\nDescription: %s", tt.description)
				}
			} else {
				if result.Error != "" {
					t.Errorf("Unexpected error: %s\nDescription: %s", result.Error, tt.description)
				}

				if math.Abs(result.EndStateScore-tt.wantScore) > 0.20 {
					t.Errorf("EndStateScore = %v, want ~%v\nDescription: %s",
						result.EndStateScore, tt.wantScore, tt.description)
				}

				// Verify score is in valid range
				if result.EndStateScore < 0.0 || result.EndStateScore > 1.0 {
					t.Errorf("Score %v out of range [0.0, 1.0]", result.EndStateScore)
				}

				// Verify contributions sum to end state score
				totalContribution := result.TotalReturn.Contribution +
					result.Diversification.Contribution +
					result.LongTermPromise.Contribution +
					result.Stability.Contribution +
					result.Opinion.Contribution

				if math.Abs(totalContribution-result.EndStateScore) > 0.01 {
					t.Errorf("Contributions sum to %v, but EndStateScore is %v",
						totalContribution, result.EndStateScore)
				}
			}
		})
	}
}
