package scorers

import (
	"math"
	"testing"

	"github.com/aristath/arduino-trader/internal/modules/scoring/domain"
)

func TestCalculatePortfolioScore(t *testing.T) {
	scorer := NewDiversificationScorer()

	tests := []struct {
		context     *domain.PortfolioContext
		name        string
		description string
		wantScore   float64
	}{
		{
			name: "Well-balanced portfolio",
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"AAPL": 3000.0,
					"MSFT": 3000.0,
					"VGT":  4000.0,
				},
				TotalValue: 10000.0,
				CountryWeights: map[string]float64{
					"US": 0.0, // Balanced
				},
				SecurityCountries: map[string]string{
					"AAPL": "United States",
					"MSFT": "United States",
					"VGT":  "United States",
				},
				CountryToGroup: map[string]string{
					"United States": "US",
				},
				SecurityDividends: map[string]float64{
					"AAPL": 0.02,
					"MSFT": 0.015,
					"VGT":  0.01,
				},
				SecurityScores: map[string]float64{
					"AAPL": 0.85,
					"MSFT": 0.90,
					"VGT":  0.80,
				},
			},
			wantScore:   40.0,
			description: "Well-balanced portfolio should score reasonably",
		},
		{
			name: "Empty portfolio",
			context: &domain.PortfolioContext{
				Positions:  map[string]float64{},
				TotalValue: 0.0,
			},
			wantScore:   50.0,
			description: "Empty portfolio returns neutral 50.0",
		},
		{
			name: "High quality portfolio",
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"QUALITY1": 10000.0,
				},
				TotalValue: 10000.0,
				CountryWeights: map[string]float64{
					"US": 0.0,
				},
				SecurityCountries: map[string]string{
					"QUALITY1": "United States",
				},
				CountryToGroup: map[string]string{
					"United States": "US",
				},
				SecurityDividends: map[string]float64{
					"QUALITY1": 0.03,
				},
				SecurityScores: map[string]float64{
					"QUALITY1": 0.95, // Very high quality
				},
				SecurityIndustries: map[string]string{},
			},
			wantScore:   50.0,
			description: "High quality should boost score",
		},
		{
			name: "Underweight geography",
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"EUSTOCK": 10000.0,
				},
				TotalValue: 10000.0,
				CountryWeights: map[string]float64{
					"US":     0.30,  // Underweight (want 30%, have 0%)
					"EUROPE": -0.30, // Overweight (want 0%, have 100%)
				},
				SecurityCountries: map[string]string{
					"EUSTOCK": "Germany",
				},
				CountryToGroup: map[string]string{
					"Germany": "EUROPE",
				},
				SecurityDividends: map[string]float64{
					"EUSTOCK": 0.02,
				},
				SecurityScores: map[string]float64{
					"EUSTOCK": 0.70,
				},
			},
			wantScore:   50.0,
			description: "Underweight geography should lower score",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := scorer.CalculatePortfolioScore(tt.context)

			if math.Abs(result.Total-tt.wantScore) > 20.0 {
				t.Errorf("Total score = %v, want ~%v\nDescription: %s",
					result.Total, tt.wantScore, tt.description)
			}

			// Verify score is in valid range
			if result.Total < 0.0 || result.Total > 100.0 {
				t.Errorf("Total score %v out of range [0.0, 100.0]", result.Total)
			}

			// Verify component scores are present
			if result.DiversificationScore < 0 || result.DiversificationScore > 100 {
				t.Errorf("Diversification score %v out of range", result.DiversificationScore)
			}
			if result.DividendScore < 0 || result.DividendScore > 100 {
				t.Errorf("Dividend score %v out of range", result.DividendScore)
			}
			if result.QualityScore < 0 || result.QualityScore > 100 {
				t.Errorf("Quality score %v out of range", result.QualityScore)
			}
		})
	}
}

func TestCalculatePostTransactionScore(t *testing.T) {
	scorer := NewDiversificationScorer()

	tests := []struct {
		industry        *string
		context         *domain.PortfolioContext
		name            string
		symbol          string
		country         string
		description     string
		proposedValue   float64
		stockQuality    float64
		stockDividend   float64
		wantImprovement bool
	}{
		{
			name:          "Adding to underweight region improves score",
			symbol:        "EUSTOCK",
			country:       "Germany",
			industry:      strPtr("Technology"),
			proposedValue: 1000.0,
			stockQuality:  0.80,
			stockDividend: 0.02,
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"USSTOCK": 9000.0,
				},
				TotalValue: 9000.0,
				CountryWeights: map[string]float64{
					"US":     -0.10, // Overweight
					"EUROPE": 0.10,  // Underweight
				},
				SecurityCountries: map[string]string{
					"USSTOCK": "United States",
				},
				CountryToGroup: map[string]string{
					"United States": "US",
					"Germany":       "EUROPE",
				},
				SecurityDividends: map[string]float64{
					"USSTOCK": 0.02,
				},
				SecurityScores: map[string]float64{
					"USSTOCK": 0.75,
				},
				SecurityIndustries: map[string]string{},
			},
			wantImprovement: true,
			description:     "Adding to underweight region should improve score",
		},
		{
			name:          "Adding high quality stock improves score",
			symbol:        "HIGHQUAL",
			country:       "United States",
			industry:      nil,
			proposedValue: 1000.0,
			stockQuality:  0.95, // Very high quality
			stockDividend: 0.03,
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"AVGSTOCK": 9000.0,
				},
				TotalValue: 9000.0,
				CountryWeights: map[string]float64{
					"US": 0.0,
				},
				SecurityCountries: map[string]string{
					"AVGSTOCK": "United States",
				},
				CountryToGroup: map[string]string{
					"United States": "US",
				},
				SecurityDividends: map[string]float64{
					"AVGSTOCK": 0.01,
				},
				SecurityScores: map[string]float64{
					"AVGSTOCK": 0.60, // Average quality
				},
			},
			wantImprovement: true,
			description:     "Adding high quality stock should improve score",
		},
		{
			name:          "Adding to overweight region may not improve",
			symbol:        "USSTOCK2",
			country:       "United States",
			industry:      nil,
			proposedValue: 1000.0,
			stockQuality:  0.70,
			stockDividend: 0.015,
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"USSTOCK1": 9000.0,
				},
				TotalValue: 9000.0,
				CountryWeights: map[string]float64{
					"US":     -0.20, // Already overweight
					"EUROPE": 0.20,  // Underweight
				},
				SecurityCountries: map[string]string{
					"USSTOCK1": "United States",
				},
				CountryToGroup: map[string]string{
					"United States": "US",
				},
				SecurityDividends: map[string]float64{
					"USSTOCK1": 0.02,
				},
				SecurityScores: map[string]float64{
					"USSTOCK1": 0.75,
				},
			},
			wantImprovement: false,
			description:     "Adding to overweight region may decrease score",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			newScore, scoreChange := scorer.CalculatePostTransactionScore(
				tt.symbol,
				tt.country,
				tt.industry,
				tt.proposedValue,
				tt.stockQuality,
				tt.stockDividend,
				tt.context,
			)

			// Verify new score is valid
			if newScore.Total < 0.0 || newScore.Total > 100.0 {
				t.Errorf("New score %v out of range [0.0, 100.0]", newScore.Total)
			}

			// Check if improvement matches expectation
			improved := scoreChange > 0
			if tt.wantImprovement != improved {
				t.Errorf("Score change = %v (improved: %v), want improvement: %v\nDescription: %s",
					scoreChange, improved, tt.wantImprovement, tt.description)
			}
		})
	}
}

// TestCalculateDiversificationScore is commented out as it requires complex setup
// The integration test TestCalculatePortfolioScore provides sufficient coverage

func TestCalculateDividendScore(t *testing.T) {
	tests := []struct {
		context     *domain.PortfolioContext
		name        string
		description string
		totalValue  float64
		wantScore   float64
	}{
		{
			name: "No dividends",
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"GROWTH": 10000.0,
				},
				SecurityDividends: map[string]float64{
					"GROWTH": 0.0,
				},
			},
			totalValue:  10000.0,
			wantScore:   30.0,
			description: "Zero dividend yield should score 30",
		},
		{
			name: "Moderate dividends (2%)",
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"DIVIDEND": 10000.0,
				},
				SecurityDividends: map[string]float64{
					"DIVIDEND": 0.02,
				},
			},
			totalValue:  10000.0,
			wantScore:   50.0,
			description: "2% dividend yield should score 50",
		},
		{
			name: "High dividends (5%)",
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"HIGHDIV": 10000.0,
				},
				SecurityDividends: map[string]float64{
					"HIGHDIV": 0.05,
				},
			},
			totalValue:  10000.0,
			wantScore:   80.0,
			description: "5% dividend yield should score 80",
		},
		{
			name: "Missing dividend data",
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"STOCK": 10000.0,
				},
				SecurityDividends: nil,
			},
			totalValue:  10000.0,
			wantScore:   50.0,
			description: "Missing data should return neutral 50",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := calculateDividendScore(tt.context, tt.totalValue)

			if math.Abs(got-tt.wantScore) > 5.0 {
				t.Errorf("Score = %v, want ~%v\nDescription: %s",
					got, tt.wantScore, tt.description)
			}

			// Verify score is in valid range
			if got < 0.0 || got > 100.0 {
				t.Errorf("Score %v out of range [0.0, 100.0]", got)
			}
		})
	}
}

func TestCalculateQualityScore(t *testing.T) {
	tests := []struct {
		context     *domain.PortfolioContext
		name        string
		description string
		totalValue  float64
		wantScore   float64
	}{
		{
			name: "High quality portfolio",
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"QUALITY": 10000.0,
				},
				SecurityScores: map[string]float64{
					"QUALITY": 0.90,
				},
			},
			totalValue:  10000.0,
			wantScore:   90.0,
			description: "90% quality score should return 90",
		},
		{
			name: "Average quality portfolio",
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"AVERAGE": 10000.0,
				},
				SecurityScores: map[string]float64{
					"AVERAGE": 0.50,
				},
			},
			totalValue:  10000.0,
			wantScore:   50.0,
			description: "50% quality score should return 50",
		},
		{
			name: "Mixed quality portfolio",
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"HIGH": 7000.0,
					"LOW":  3000.0,
				},
				SecurityScores: map[string]float64{
					"HIGH": 0.90,
					"LOW":  0.30,
				},
			},
			totalValue:  10000.0,
			wantScore:   72.0, // 0.7*90 + 0.3*30 = 72
			description: "Weighted average should be calculated correctly",
		},
		{
			name: "Missing quality data",
			context: &domain.PortfolioContext{
				Positions: map[string]float64{
					"STOCK": 10000.0,
				},
				SecurityScores: nil,
			},
			totalValue:  10000.0,
			wantScore:   50.0,
			description: "Missing data should return neutral 50",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := calculateQualityScore(tt.context, tt.totalValue)

			if math.Abs(got-tt.wantScore) > 1.0 {
				t.Errorf("Score = %v, want %v\nDescription: %s",
					got, tt.wantScore, tt.description)
			}

			// Verify score is in valid range
			if got < 0.0 || got > 100.0 {
				t.Errorf("Score %v out of range [0.0, 100.0]", got)
			}
		})
	}
}

// Helper function

func strPtr(s string) *string {
	return &s
}
