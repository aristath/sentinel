package testing

import (
	"time"

	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/aristath/sentinel/internal/modules/cash_flows"
	"github.com/aristath/sentinel/internal/modules/dividends"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/trading"
	"github.com/aristath/sentinel/internal/modules/universe"
)

// NewSecurityFixtures returns a set of test securities for use in tests
func NewSecurityFixtures() []*universe.Security {
	now := time.Now().Unix()
	return []*universe.Security{
		{
			ISIN:               "US0378331005",
			Symbol:             "AAPL",
			Name:               "Apple Inc.",
			ProductType:        "EQUITY",
			Industry:           "Technology",
			Geography:          "US",
			FullExchangeName:   "NASDAQ",
			Currency:           "USD",
			AllowBuy:           true,
			AllowSell:          true,
			MinLot:             1,
			PriorityMultiplier: 1.0,
			LastSynced:         &now,
		},
		{
			ISIN:               "US5949181045",
			Symbol:             "MSFT",
			Name:               "Microsoft Corporation",
			ProductType:        "EQUITY",
			Industry:           "Technology",
			Geography:          "US",
			FullExchangeName:   "NASDAQ",
			Currency:           "USD",
			AllowBuy:           true,
			AllowSell:          true,
			MinLot:             1,
			PriorityMultiplier: 1.0,
			LastSynced:         &now,
		},
		{
			ISIN:               "US30303M1027",
			Symbol:             "META",
			Name:               "Meta Platforms Inc.",
			ProductType:        "EQUITY",
			Industry:           "Technology",
			Geography:          "US",
			FullExchangeName:   "NASDAQ",
			Currency:           "USD",
			AllowBuy:           true,
			AllowSell:          true,
			MinLot:             1,
			PriorityMultiplier: 1.0,
			LastSynced:         &now,
		},
		{
			ISIN:               "IE00B52VJ196",
			Symbol:             "VWCE",
			Name:               "Vanguard FTSE All-World UCITS ETF",
			ProductType:        "ETF",
			Industry:           "Diversified",
			Geography:          "IE",
			FullExchangeName:   "XETR",
			Currency:           "EUR",
			AllowBuy:           true,
			AllowSell:          true,
			MinLot:             1,
			PriorityMultiplier: 1.0,
			LastSynced:         &now,
		},
		{
			ISIN:               "US0231351067",
			Symbol:             "AMZN",
			Name:               "Amazon.com Inc.",
			ProductType:        "EQUITY",
			Industry:           "Consumer Cyclical",
			Geography:          "US",
			FullExchangeName:   "NASDAQ",
			Currency:           "USD",
			AllowBuy:           true,
			AllowSell:          true,
			MinLot:             1,
			PriorityMultiplier: 1.0,
			LastSynced:         &now,
		},
	}
}

// NewPositionFixtures returns a set of test positions for use in tests
func NewPositionFixtures() []portfolio.Position {
	now := time.Now().Unix()
	yesterday := now - 86400 // 24 hours ago
	lastWeek := now - (7 * 86400)
	return []portfolio.Position{
		{
			ISIN:             "US0378331005",
			Symbol:           "AAPL",
			Quantity:         10.0,
			AvgPrice:         150.0,
			CurrentPrice:     175.0,
			Currency:         "USD",
			CurrencyRate:     0.85,
			MarketValueEUR:   1487.50, // 10 * 175 * 0.85
			CostBasisEUR:     1275.0,  // 10 * 150 * 0.85
			UnrealizedPnL:    212.50,
			UnrealizedPnLPct: 16.67,
			LastUpdated:      &now,
			FirstBoughtAt:    &lastWeek,
		},
		{
			ISIN:             "US5949181045",
			Symbol:           "MSFT",
			Quantity:         5.0,
			AvgPrice:         300.0,
			CurrentPrice:     380.0,
			Currency:         "USD",
			CurrencyRate:     0.85,
			MarketValueEUR:   1615.0, // 5 * 380 * 0.85
			CostBasisEUR:     1275.0, // 5 * 300 * 0.85
			UnrealizedPnL:    340.0,
			UnrealizedPnLPct: 26.67,
			LastUpdated:      &yesterday,
			FirstBoughtAt:    &lastWeek,
		},
		{
			ISIN:             "IE00B52VJ196",
			Symbol:           "VWCE",
			Quantity:         50.0,
			AvgPrice:         95.0,
			CurrentPrice:     100.0,
			Currency:         "EUR",
			CurrencyRate:     1.0,
			MarketValueEUR:   5000.0, // 50 * 100
			CostBasisEUR:     4750.0, // 50 * 95
			UnrealizedPnL:    250.0,
			UnrealizedPnLPct: 5.26,
			LastUpdated:      &now,
			FirstBoughtAt:    &lastWeek,
		},
	}
}

// NewTradeFixtures returns a set of test trades for use in tests
func NewTradeFixtures() []trading.Trade {
	now := time.Now()
	yesterday := now.AddDate(0, 0, -1)
	lastWeek := now.AddDate(0, 0, -7)
	lastMonth := now.AddDate(0, -1, 0)

	return []trading.Trade{
		{
			ID:           1,
			Symbol:       "AAPL",
			ISIN:         "US0378331005",
			Side:         trading.TradeSideBuy,
			Quantity:     10.0,
			Price:        150.0,
			Currency:     "USD",
			CurrencyRate: floatPtr(0.85),
			ValueEUR:     floatPtr(1275.0),
			ExecutedAt:   lastMonth,
			Source:       "tradernet",
			Mode:         "live",
		},
		{
			ID:           2,
			Symbol:       "MSFT",
			ISIN:         "US5949181045",
			Side:         trading.TradeSideBuy,
			Quantity:     5.0,
			Price:        300.0,
			Currency:     "USD",
			CurrencyRate: floatPtr(0.85),
			ValueEUR:     floatPtr(1275.0),
			ExecutedAt:   lastWeek,
			Source:       "tradernet",
			Mode:         "live",
		},
		{
			ID:           3,
			Symbol:       "VWCE",
			ISIN:         "IE00B52VJ196",
			Side:         trading.TradeSideBuy,
			Quantity:     50.0,
			Price:        95.0,
			Currency:     "EUR",
			CurrencyRate: floatPtr(1.0),
			ValueEUR:     floatPtr(4750.0),
			ExecutedAt:   lastWeek,
			Source:       "tradernet",
			Mode:         "live",
		},
		{
			ID:           4,
			Symbol:       "AAPL",
			ISIN:         "US0378331005",
			Side:         trading.TradeSideSell,
			Quantity:     2.0,
			Price:        170.0,
			Currency:     "USD",
			CurrencyRate: floatPtr(0.85),
			ValueEUR:     floatPtr(289.0),
			ExecutedAt:   yesterday,
			Source:       "tradernet",
			Mode:         "live",
			OrderID:      "order_123",
		},
	}
}

// NewCashFlowFixtures returns a set of test cash flows for use in tests
func NewCashFlowFixtures() []cash_flows.CashFlow {
	now := time.Now()
	lastWeek := now.AddDate(0, 0, -7)
	lastMonth := now.AddDate(0, -1, 0)
	threeMonthsAgo := now.AddDate(0, -3, 0)

	depositType := "DEPOSIT"
	withdrawalType := "WITHDRAWAL"
	dividendType := "DIVIDEND"

	return []cash_flows.CashFlow{
		{
			ID:              1,
			TransactionID:   "deposit_001",
			TransactionType: &depositType,
			Amount:          10000.0,
			Currency:        "EUR",
			AmountEUR:       10000.0,
			Date:            threeMonthsAgo.Format("2006-01-02"),
			CreatedAt:       threeMonthsAgo,
		},
		{
			ID:              2,
			TransactionID:   "deposit_002",
			TransactionType: &depositType,
			Amount:          5000.0,
			Currency:        "EUR",
			AmountEUR:       5000.0,
			Date:            lastMonth.Format("2006-01-02"),
			CreatedAt:       lastMonth,
		},
		{
			ID:              3,
			TransactionID:   "withdrawal_001",
			TransactionType: &withdrawalType,
			Amount:          -1000.0,
			Currency:        "EUR",
			AmountEUR:       -1000.0,
			Date:            lastWeek.Format("2006-01-02"),
			CreatedAt:       lastWeek,
		},
		{
			ID:              4,
			TransactionID:   "dividend_001",
			TransactionType: &dividendType,
			Amount:          150.0,
			Currency:        "EUR",
			AmountEUR:       150.0,
			Date:            lastWeek.Format("2006-01-02"),
			CreatedAt:       lastWeek,
		},
	}
}

// NewDividendFixtures returns a set of test dividends for use in tests
func NewDividendFixtures() []dividends.DividendRecord {
	now := time.Now()
	lastWeek := now.AddDate(0, 0, -7)
	lastMonth := now.AddDate(0, -1, 0)

	// Convert time.Time to Unix timestamp at midnight UTC
	lastWeekUnix := time.Date(lastWeek.Year(), lastWeek.Month(), lastWeek.Day(), 0, 0, 0, 0, time.UTC).Unix()
	lastMonthUnix := time.Date(lastMonth.Year(), lastMonth.Month(), lastMonth.Day(), 0, 0, 0, 0, time.UTC).Unix()

	reinvestedQty1 := 2

	return []dividends.DividendRecord{
		{
			ID:          1,
			Symbol:      "AAPL",
			ISIN:        "US0378331005",
			Amount:      50.0,
			Currency:    "USD",
			AmountEUR:   42.5,
			PaymentDate: intPtr(lastMonthUnix),
			Reinvested:  false,
		},
		{
			ID:                 2,
			Symbol:             "MSFT",
			ISIN:               "US5949181045",
			Amount:             25.0,
			Currency:           "USD",
			AmountEUR:          21.25,
			PaymentDate:        intPtr(lastMonthUnix),
			Reinvested:         true,
			ReinvestedQuantity: &reinvestedQty1,
		},
		{
			ID:          3,
			Symbol:      "VWCE",
			ISIN:        "IE00B52VJ196",
			Amount:      75.0,
			Currency:    "EUR",
			AmountEUR:   75.0,
			PaymentDate: intPtr(lastWeekUnix),
			Reinvested:  false,
		},
	}
}

// NewAllocationTargetFixtures returns a set of test allocation targets for use in tests
func NewAllocationTargetFixtures() []allocation.AllocationTarget {
	now := time.Now()
	return []allocation.AllocationTarget{
		{
			ID:        1,
			Type:      "geography",
			Name:      "EU",
			TargetPct: 0.40,
			CreatedAt: now,
			UpdatedAt: now,
		},
		{
			ID:        2,
			Type:      "geography",
			Name:      "US",
			TargetPct: 0.40,
			CreatedAt: now,
			UpdatedAt: now,
		},
		{
			ID:        3,
			Type:      "geography",
			Name:      "ASIA",
			TargetPct: 0.20,
			CreatedAt: now,
			UpdatedAt: now,
		},
		{
			ID:        4,
			Type:      "industry",
			Name:      "Technology",
			TargetPct: 0.30,
			CreatedAt: now,
			UpdatedAt: now,
		},
		{
			ID:        5,
			Type:      "industry",
			Name:      "Finance",
			TargetPct: 0.20,
			CreatedAt: now,
			UpdatedAt: now,
		},
	}
}

// NewCurrencyFixtures returns a set of test currency codes for use in tests
func NewCurrencyFixtures() []string {
	return []string{"EUR", "USD", "GBP", "JPY", "CHF"}
}

// NewISINFuxtures returns a set of test ISINs for use in tests
func NewISINFuxtures() []string {
	return []string{
		"US0378331005", // AAPL
		"US5949181045", // MSFT
		"US30303M1027", // META
		"IE00B52VJ196", // VWCE
		"US0231351067", // AMZN
	}
}

// floatPtr returns a pointer to the given float64 value
func floatPtr(f float64) *float64 {
	return &f
}

// intPtr returns a pointer to the given int64 value
func intPtr(i int64) *int64 {
	return &i
}
