package scheduler

import (
	"testing"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/clients/yahoo"
	"github.com/aristath/arduino-trader/internal/modules/dividends"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/trading"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
)

func TestDividendReinvestmentJob_Name(t *testing.T) {
	job := &DividendReinvestmentJob{
		log: zerolog.Nop(),
	}

	if job.Name() != "dividend_reinvestment" {
		t.Errorf("Expected job name 'dividend_reinvestment', got '%s'", job.Name())
	}
}

func TestCalculateMinTradeAmount(t *testing.T) {
	tests := []struct {
		name               string
		transactionFixed   float64
		transactionPercent float64
		maxCostRatio       float64
		expected           float64
	}{
		{
			name:               "Freedom24 standard costs",
			transactionFixed:   2.0,
			transactionPercent: 0.002, // 0.2%
			maxCostRatio:       0.01,  // 1%
			expected:           250.0, // €2 / (0.01 - 0.002) = €250
		},
		{
			name:               "Higher fixed cost",
			transactionFixed:   5.0,
			transactionPercent: 0.002,
			maxCostRatio:       0.01,
			expected:           625.0, // €5 / (0.01 - 0.002) = €625
		},
		{
			name:               "Lower max cost ratio",
			transactionFixed:   2.0,
			transactionPercent: 0.002,
			maxCostRatio:       0.005,  // 0.5%
			expected:           666.67, // €2 / (0.005 - 0.002) ≈ €666.67
		},
		{
			name:               "Variable cost exceeds max ratio",
			transactionFixed:   2.0,
			transactionPercent: 0.015,  // 1.5%
			maxCostRatio:       0.01,   // 1%
			expected:           1000.0, // Returns high minimum
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			job := &DividendReinvestmentJob{
				transactionCostFixed: tt.transactionFixed,
				transactionCostPct:   tt.transactionPercent,
				maxCostRatio:         tt.maxCostRatio,
			}

			result := job.calculateMinTradeAmount()

			// Allow for small floating point differences
			if abs(result-tt.expected) > 0.1 {
				t.Errorf("calculateMinTradeAmount() = %.2f, want %.2f",
					result, tt.expected)
			}
		})
	}
}

func TestGroupDividendsBySymbol(t *testing.T) {
	job := &DividendReinvestmentJob{
		log: zerolog.Nop(),
	}

	dividends := []dividends.DividendRecord{
		{ID: 1, Symbol: "AAPL", AmountEUR: 10.0},
		{ID: 2, Symbol: "AAPL", AmountEUR: 15.0},
		{ID: 3, Symbol: "MSFT", AmountEUR: 20.0},
		{ID: 4, Symbol: "AAPL", AmountEUR: 5.0},
		{ID: 5, Symbol: "GOOGL", AmountEUR: 12.0},
	}

	grouped := job.groupDividendsBySymbol(dividends)

	// Check AAPL group
	if aaplInfo, ok := grouped["AAPL"]; !ok {
		t.Error("AAPL group not found")
	} else {
		if aaplInfo.DividendCount != 3 {
			t.Errorf("AAPL dividend count = %d, want 3", aaplInfo.DividendCount)
		}
		if aaplInfo.TotalAmount != 30.0 {
			t.Errorf("AAPL total amount = %.2f, want 30.00", aaplInfo.TotalAmount)
		}
		if len(aaplInfo.DividendIDs) != 3 {
			t.Errorf("AAPL dividend IDs count = %d, want 3", len(aaplInfo.DividendIDs))
		}
	}

	// Check MSFT group
	if msftInfo, ok := grouped["MSFT"]; !ok {
		t.Error("MSFT group not found")
	} else {
		if msftInfo.DividendCount != 1 {
			t.Errorf("MSFT dividend count = %d, want 1", msftInfo.DividendCount)
		}
		if msftInfo.TotalAmount != 20.0 {
			t.Errorf("MSFT total amount = %.2f, want 20.00", msftInfo.TotalAmount)
		}
	}

	// Check GOOGL group
	if googlInfo, ok := grouped["GOOGL"]; !ok {
		t.Error("GOOGL group not found")
	} else {
		if googlInfo.DividendCount != 1 {
			t.Errorf("GOOGL dividend count = %d, want 1", googlInfo.DividendCount)
		}
		if googlInfo.TotalAmount != 12.0 {
			t.Errorf("GOOGL total amount = %.2f, want 12.00", googlInfo.TotalAmount)
		}
	}

	// Check total groups
	if len(grouped) != 3 {
		t.Errorf("Total groups = %d, want 3", len(grouped))
	}
}

func TestNewDividendReinvestmentJob(t *testing.T) {
	cfg := DividendReinvestmentConfig{
		Log:              zerolog.Nop(),
		DividendRepo:     &dividends.DividendRepository{},
		SecurityRepo:     &universe.SecurityRepository{},
		ScoreRepo:        &universe.ScoreRepository{},
		PortfolioService: &portfolio.PortfolioService{},
		TradingService:   &trading.TradingService{},
		TradernetClient:  &tradernet.Client{},
		YahooClient:      &yahoo.Client{},
	}

	job := NewDividendReinvestmentJob(cfg)

	if job == nil {
		t.Fatal("NewDividendReinvestmentJob returned nil")
	}

	if job.transactionCostFixed != 2.0 {
		t.Errorf("transactionCostFixed = %.2f, want 2.00", job.transactionCostFixed)
	}

	if job.transactionCostPct != 0.002 {
		t.Errorf("transactionCostPct = %.4f, want 0.0020", job.transactionCostPct)
	}

	if job.maxCostRatio != 0.01 {
		t.Errorf("maxCostRatio = %.4f, want 0.0100", job.maxCostRatio)
	}
}

// Helper function
func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
