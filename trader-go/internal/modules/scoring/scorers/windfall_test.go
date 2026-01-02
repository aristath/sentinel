package scorers

import (
	"math"
	"testing"
	"time"
)

func TestCalculateExcessGain(t *testing.T) {
	scorer := NewWindfallScorer()

	tests := []struct {
		name           string
		description    string
		currentGain    float64
		yearsHeld      float64
		historicalCAGR float64
		wantExcess     float64
	}{
		{
			name:           "Consistent grower - Python example",
			currentGain:    0.61, // 61% gain
			yearsHeld:      3.0,
			historicalCAGR: 0.17, // 17% CAGR
			wantExcess:     0.01, // ~1% excess (61% - 60%)
			description:    "Stock performing at historical rate",
		},
		{
			name:           "Sudden spike - Python example",
			currentGain:    0.80, // 80% gain
			yearsHeld:      1.0,
			historicalCAGR: 0.10, // 10% CAGR
			wantExcess:     0.70, // 70% excess (80% - 10%)
			description:    "Windfall spike above historical rate",
		},
		{
			name:           "No history (years_held = 0)",
			currentGain:    0.50,
			yearsHeld:      0.0,
			historicalCAGR: 0.10,
			wantExcess:     0.50, // All gain is excess
			description:    "No history = all excess",
		},
		{
			name:           "Invalid CAGR (-1 or below)",
			currentGain:    0.30,
			yearsHeld:      2.0,
			historicalCAGR: -1.5,
			wantExcess:     0.30, // All gain is excess (invalid CAGR)
			description:    "Invalid CAGR returns all gain as excess",
		},
		{
			name:           "Underperforming position",
			currentGain:    0.05, // 5% gain
			yearsHeld:      2.0,
			historicalCAGR: 0.10,  // 10% CAGR (expected ~21%)
			wantExcess:     -0.16, // Negative excess
			description:    "Underperforming vs historical rate",
		},
		{
			name:           "Zero gain",
			currentGain:    0.0,
			yearsHeld:      1.0,
			historicalCAGR: 0.10,
			wantExcess:     -0.10, // Negative excess
			description:    "No gain when growth expected",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := scorer.CalculateExcessGain(tt.currentGain, tt.yearsHeld, tt.historicalCAGR)
			// Allow for small floating point differences
			if math.Abs(got-tt.wantExcess) > 0.01 {
				t.Errorf("CalculateExcessGain() = %v, want %v (diff: %v)\nDescription: %s",
					got, tt.wantExcess, math.Abs(got-tt.wantExcess), tt.description)
			}
		})
	}
}

func TestCalculateWindfallScore(t *testing.T) {
	scorer := NewWindfallScorer()

	tests := []struct {
		currentGain    *float64
		yearsHeld      *float64
		historicalCAGR *float64
		name           string
		wantStatus     string
		description    string
		wantScore      float64
	}{
		{
			name:           "High windfall (50%+ excess)",
			currentGain:    floatPtr(1.0), // 100% gain
			yearsHeld:      floatPtr(1.0),
			historicalCAGR: floatPtr(0.10), // 10% expected, 90% excess
			wantScore:      1.0,
			description:    "90% excess should score 1.0",
		},
		{
			name:           "Medium-high windfall (35% excess)",
			currentGain:    floatPtr(0.45), // 45% gain
			yearsHeld:      floatPtr(1.0),
			historicalCAGR: floatPtr(0.10), // 10% expected, 35% excess
			wantScore:      0.7,            // Interpolate between 0.5 and 1.0
			description:    "35% excess interpolates to ~0.7",
		},
		{
			name:           "Medium windfall (30% excess)",
			currentGain:    floatPtr(0.40), // 40% gain
			yearsHeld:      floatPtr(1.0),
			historicalCAGR: floatPtr(0.10), // 10% expected, 30% excess
			wantScore:      0.6,            // Interpolate
			description:    "30% excess interpolates to ~0.6",
		},
		{
			name:           "Low windfall (10% excess)",
			currentGain:    floatPtr(0.20), // 20% gain
			yearsHeld:      floatPtr(1.0),
			historicalCAGR: floatPtr(0.10), // 10% expected, 10% excess
			wantScore:      0.2,            // 10%/25% * 0.5 = 0.2
			description:    "10% excess should score 0.2",
		},
		{
			name:           "No excess (consistent performer)",
			currentGain:    floatPtr(0.10), // 10% gain
			yearsHeld:      floatPtr(1.0),
			historicalCAGR: floatPtr(0.10), // 10% expected, 0% excess
			wantScore:      0.0,
			description:    "No excess should score 0.0",
		},
		{
			name:           "Underperforming (negative excess)",
			currentGain:    floatPtr(0.05), // 5% gain
			yearsHeld:      floatPtr(1.0),
			historicalCAGR: floatPtr(0.10), // 10% expected, -5% excess
			wantScore:      0.0,
			description:    "Negative excess should score 0.0",
		},
		{
			name:        "Insufficient data (nil gain)",
			currentGain: nil,
			yearsHeld:   floatPtr(1.0),
			wantScore:   0.0,
			wantStatus:  "insufficient_data",
			description: "Missing current gain returns neutral",
		},
		{
			name:        "Insufficient data (nil years)",
			currentGain: floatPtr(0.50),
			yearsHeld:   nil,
			wantScore:   0.0,
			wantStatus:  "insufficient_data",
			description: "Missing years held returns neutral",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := scorer.CalculateWindfallScore(tt.currentGain, tt.yearsHeld, tt.historicalCAGR)

			if math.Abs(result.WindfallScore-tt.wantScore) > 0.05 {
				t.Errorf("WindfallScore = %v, want %v\nDescription: %s",
					result.WindfallScore, tt.wantScore, tt.description)
			}

			if tt.wantStatus != "" && result.Status != tt.wantStatus {
				t.Errorf("Status = %v, want %v", result.Status, tt.wantStatus)
			}
		})
	}
}

func TestShouldTakeProfits(t *testing.T) {
	scorer := NewWindfallScorer()

	tests := []struct {
		name           string
		reasonContains string
		description    string
		currentGain    float64
		yearsHeld      float64
		historicalCAGR float64
		wantPct        float64
		wantSell       bool
	}{
		{
			name:           "Windfall doubler (100%+ gain, 30%+ excess)",
			currentGain:    1.2, // 120% gain
			yearsHeld:      1.0,
			historicalCAGR: 0.10, // 10% expected, 110% excess
			wantSell:       true,
			wantPct:        0.50, // Sell 50%
			reasonContains: "Windfall doubler",
			description:    "High excess doubler sells 50%",
		},
		{
			name:           "Consistent doubler (100%+ gain, low excess)",
			currentGain:    1.1, // 110% gain
			yearsHeld:      5.0,
			historicalCAGR: 0.15, // 15% CAGR = ~101% expected
			wantSell:       true,
			wantPct:        0.30, // Sell 30%
			reasonContains: "Consistent doubler",
			description:    "Low excess doubler sells 30%",
		},
		{
			name:           "High windfall (50%+ excess, not doubled)",
			currentGain:    0.80, // 80% gain
			yearsHeld:      1.0,
			historicalCAGR: 0.10, // 10% expected, 70% excess
			wantSell:       true,
			wantPct:        0.40, // Sell 40%
			reasonContains: "High windfall",
			description:    "High windfall sells 40%",
		},
		{
			name:           "Medium windfall (25-50% excess)",
			currentGain:    0.40, // 40% gain
			yearsHeld:      1.0,
			historicalCAGR: 0.10, // 10% expected, 30% excess
			wantSell:       true,
			wantPct:        0.20, // Sell 20%
			reasonContains: "Medium windfall",
			description:    "Medium windfall sells 20%",
		},
		{
			name:           "Low excess (don't sell)",
			currentGain:    0.20, // 20% gain
			yearsHeld:      1.0,
			historicalCAGR: 0.10, // 10% expected, 10% excess
			wantSell:       false,
			wantPct:        0.0,
			reasonContains: "within normal range",
			description:    "Low excess doesn't trigger sale",
		},
		{
			name:           "Performing near expectations",
			currentGain:    0.12, // 12% gain
			yearsHeld:      1.0,
			historicalCAGR: 0.10, // 10% expected, 2% excess
			wantSell:       false,
			wantPct:        0.0,
			reasonContains: "within normal range",
			description:    "Near expectations doesn't trigger sale",
		},
		{
			name:           "Slightly underperforming",
			currentGain:    0.08, // 8% gain
			yearsHeld:      1.0,
			historicalCAGR: 0.10, // 10% expected, -2% excess
			wantSell:       false,
			wantPct:        0.0,
			reasonContains: "near expectations",
			description:    "Slight underperformance doesn't trigger sale",
		},
		{
			name:           "Significantly underperforming",
			currentGain:    0.0, // 0% gain
			yearsHeld:      1.0,
			historicalCAGR: 0.15, // 15% expected, -15% excess
			wantSell:       false,
			wantPct:        0.0,
			reasonContains: "Underperforming",
			description:    "Significant underperformance doesn't trigger sale",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := scorer.ShouldTakeProfits(tt.currentGain, tt.yearsHeld, tt.historicalCAGR)

			if result.ShouldSell != tt.wantSell {
				t.Errorf("ShouldSell = %v, want %v\nDescription: %s",
					result.ShouldSell, tt.wantSell, tt.description)
			}

			if math.Abs(result.SuggestedSellPct-tt.wantPct) > 0.01 {
				t.Errorf("SuggestedSellPct = %v, want %v\nDescription: %s",
					result.SuggestedSellPct, tt.wantPct, tt.description)
			}

			// Verify reason contains expected text (case-insensitive check would be better but this works)
			if tt.reasonContains != "" && !contains(result.Reason, tt.reasonContains) {
				t.Errorf("Reason = %q, should contain %q\nDescription: %s",
					result.Reason, tt.reasonContains, tt.description)
			}
		})
	}
}

func TestGetWindfallRecommendation(t *testing.T) {
	scorer := NewWindfallScorer()

	tests := []struct {
		firstBoughtAt  *time.Time
		historicalCAGR *float64
		name           string
		description    string
		currentPrice   float64
		avgPrice       float64
		wantError      bool
		checkSell      bool
		wantSell       bool
	}{
		{
			name:           "Valid recommendation - windfall",
			currentPrice:   200.0,
			avgPrice:       100.0,                                   // 100% gain
			firstBoughtAt:  timePtr(time.Now().AddDate(0, 0, -365)), // 1 year ago
			historicalCAGR: floatPtr(0.10),                          // 10% CAGR, 90% excess
			wantError:      false,
			checkSell:      true,
			wantSell:       true, // Should recommend selling
			description:    "100% gain in 1 year with 10% CAGR should trigger sale",
		},
		{
			name:           "Valid recommendation - consistent performer",
			currentPrice:   110.0,
			avgPrice:       100.0,                                   // 10% gain
			firstBoughtAt:  timePtr(time.Now().AddDate(0, 0, -365)), // 1 year ago
			historicalCAGR: floatPtr(0.10),                          // 10% CAGR, 0% excess
			wantError:      false,
			checkSell:      true,
			wantSell:       false, // Should NOT recommend selling
			description:    "Consistent performer should not trigger sale",
		},
		{
			name:          "Invalid average price",
			currentPrice:  100.0,
			avgPrice:      0.0, // Invalid
			firstBoughtAt: nil,
			wantError:     true,
			description:   "Zero average price should error",
		},
		{
			name:          "Negative average price",
			currentPrice:  100.0,
			avgPrice:      -10.0, // Invalid
			firstBoughtAt: nil,
			wantError:     true,
			description:   "Negative average price should error",
		},
		{
			name:           "No first bought date (uses default 1 year)",
			currentPrice:   150.0,
			avgPrice:       100.0,
			firstBoughtAt:  nil,
			historicalCAGR: floatPtr(0.10),
			wantError:      false,
			description:    "Missing date should use default 1 year",
		},
		{
			name:           "No historical CAGR (uses default 10%)",
			currentPrice:   150.0,
			avgPrice:       100.0,
			firstBoughtAt:  timePtr(time.Now().AddDate(0, 0, -365)),
			historicalCAGR: nil,
			wantError:      false,
			description:    "Missing CAGR should use default 10%",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := scorer.GetWindfallRecommendation(
				"TEST",
				tt.currentPrice,
				tt.avgPrice,
				tt.firstBoughtAt,
				tt.historicalCAGR,
			)

			if tt.wantError {
				if result.Error == "" {
					t.Errorf("Expected error but got none\nDescription: %s", tt.description)
				}
			} else {
				if result.Error != "" {
					t.Errorf("Unexpected error: %s\nDescription: %s", result.Error, tt.description)
				}

				if tt.checkSell && result.Recommendation.ShouldSell != tt.wantSell {
					t.Errorf("ShouldSell = %v, want %v\nDescription: %s",
						result.Recommendation.ShouldSell, tt.wantSell, tt.description)
				}

				// Verify basic fields are populated
				if result.Symbol != "TEST" {
					t.Errorf("Symbol = %v, want TEST", result.Symbol)
				}
			}
		})
	}
}

// Helper functions

func floatPtr(f float64) *float64 {
	return &f
}

func timePtr(t time.Time) *time.Time {
	return &t
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > len(substr) &&
		(s[:len(substr)] == substr || s[len(s)-len(substr):] == substr ||
			(len(s) > len(substr)+1 && findSubstr(s, substr))))
}

func findSubstr(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
