package satellites

import (
	"testing"
	"time"

	"github.com/rs/zerolog"

	"github.com/aristath/arduino-trader/internal/modules/trading"
)

// Helper function to create a test logger that discards output
func testLogger() zerolog.Logger {
	return zerolog.Nop()
}

// Helper function to create a trade
func createTrade(symbol string, side trading.TradeSide, quantity, price float64, executedAt time.Time, bucketID string) trading.Trade {
	valueEUR := quantity * price
	return trading.Trade{
		Symbol:     symbol,
		Side:       side,
		Quantity:   quantity,
		Price:      price,
		ExecutedAt: executedAt,
		BucketID:   bucketID,
		ValueEUR:   &valueEUR,
	}
}

// TestMatchTrades_SimpleBuySell tests a single BUY followed by a single SELL (complete match)
func TestMatchTrades_SimpleBuySell(t *testing.T) {
	time1 := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	time2 := time.Date(2024, 1, 2, 10, 0, 0, 0, time.UTC)

	trades := []trading.Trade{
		createTrade("AAPL", trading.TradeSideBuy, 100, 150, time1, "core"),
		createTrade("AAPL", trading.TradeSideSell, 100, 160, time2, "core"),
	}

	closed := matchTrades(trades, testLogger())

	if len(closed) != 1 {
		t.Fatalf("Expected 1 closed trade, got %d", len(closed))
	}

	ct := closed[0]
	if ct.Symbol != "AAPL" {
		t.Errorf("Expected symbol AAPL, got %s", ct.Symbol)
	}
	if ct.Quantity != 100 {
		t.Errorf("Expected quantity 100, got %f", ct.Quantity)
	}
	if ct.BuyPrice != 150 {
		t.Errorf("Expected buy price 150, got %f", ct.BuyPrice)
	}
	if ct.SellPrice != 160 {
		t.Errorf("Expected sell price 160, got %f", ct.SellPrice)
	}

	expectedPnL := (160.0 - 150.0) * 100.0 // 1000
	if ct.ProfitLoss != expectedPnL {
		t.Errorf("Expected P&L %f, got %f", expectedPnL, ct.ProfitLoss)
	}

	expectedReturn := (160.0 - 150.0) / 150.0 // 0.0667
	tolerance := 0.0001
	if ct.ReturnPct < expectedReturn-tolerance || ct.ReturnPct > expectedReturn+tolerance {
		t.Errorf("Expected return ~%f, got %f", expectedReturn, ct.ReturnPct)
	}
	_ = expectedReturn // Use variable to avoid "declared and not used" error
}

// TestMatchTrades_PartialFill tests BUY 100, SELL 60, SELL 40
func TestMatchTrades_PartialFill(t *testing.T) {
	time1 := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	time2 := time.Date(2024, 1, 2, 10, 0, 0, 0, time.UTC)
	time3 := time.Date(2024, 1, 3, 10, 0, 0, 0, time.UTC)

	trades := []trading.Trade{
		createTrade("AAPL", trading.TradeSideBuy, 100, 150, time1, "core"),
		createTrade("AAPL", trading.TradeSideSell, 60, 160, time2, "core"),
		createTrade("AAPL", trading.TradeSideSell, 40, 170, time3, "core"),
	}

	closed := matchTrades(trades, testLogger())

	if len(closed) != 2 {
		t.Fatalf("Expected 2 closed trades, got %d", len(closed))
	}

	// First trade: 60 shares at 160
	ct1 := closed[0]
	if ct1.Quantity != 60 {
		t.Errorf("Expected first trade quantity 60, got %f", ct1.Quantity)
	}
	if ct1.SellPrice != 160 {
		t.Errorf("Expected first trade sell price 160, got %f", ct1.SellPrice)
	}
	expectedPnL1 := (160.0 - 150.0) * 60.0 // 600
	if ct1.ProfitLoss != expectedPnL1 {
		t.Errorf("Expected first trade P&L %f, got %f", expectedPnL1, ct1.ProfitLoss)
	}

	// Second trade: 40 shares at 170
	ct2 := closed[1]
	if ct2.Quantity != 40 {
		t.Errorf("Expected second trade quantity 40, got %f", ct2.Quantity)
	}
	if ct2.SellPrice != 170 {
		t.Errorf("Expected second trade sell price 170, got %f", ct2.SellPrice)
	}
	expectedPnL2 := (170.0 - 150.0) * 40.0 // 800
	if ct2.ProfitLoss != expectedPnL2 {
		t.Errorf("Expected second trade P&L %f, got %f", expectedPnL2, ct2.ProfitLoss)
	}
}

// TestMatchTrades_MultipleLots tests FIFO ordering: BUY 50, BUY 30, SELL 60 (should sell 50 from first lot + 10 from second)
func TestMatchTrades_MultipleLots(t *testing.T) {
	time1 := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	time2 := time.Date(2024, 1, 2, 10, 0, 0, 0, time.UTC)
	time3 := time.Date(2024, 1, 3, 10, 0, 0, 0, time.UTC)

	trades := []trading.Trade{
		createTrade("AAPL", trading.TradeSideBuy, 50, 150, time1, "core"),
		createTrade("AAPL", trading.TradeSideBuy, 30, 155, time2, "core"),
		createTrade("AAPL", trading.TradeSideSell, 60, 160, time3, "core"),
	}

	closed := matchTrades(trades, testLogger())

	if len(closed) != 2 {
		t.Fatalf("Expected 2 closed trades (FIFO), got %d", len(closed))
	}

	// First match: 50 shares from first lot at 150
	ct1 := closed[0]
	if ct1.Quantity != 50 {
		t.Errorf("Expected first match quantity 50, got %f", ct1.Quantity)
	}
	if ct1.BuyPrice != 150 {
		t.Errorf("Expected first match buy price 150, got %f", ct1.BuyPrice)
	}

	// Second match: 10 shares from second lot at 155
	ct2 := closed[1]
	if ct2.Quantity != 10 {
		t.Errorf("Expected second match quantity 10, got %f", ct2.Quantity)
	}
	if ct2.BuyPrice != 155 {
		t.Errorf("Expected second match buy price 155, got %f", ct2.BuyPrice)
	}
}

// TestMatchTrades_OnlyBuys tests that only BUY trades result in no closed trades
func TestMatchTrades_OnlyBuys(t *testing.T) {
	time1 := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	time2 := time.Date(2024, 1, 2, 10, 0, 0, 0, time.UTC)

	trades := []trading.Trade{
		createTrade("AAPL", trading.TradeSideBuy, 100, 150, time1, "core"),
		createTrade("AAPL", trading.TradeSideBuy, 50, 155, time2, "core"),
	}

	closed := matchTrades(trades, testLogger())

	if len(closed) != 0 {
		t.Errorf("Expected 0 closed trades (no SELLs), got %d", len(closed))
	}
}

// TestMatchTrades_SellExceedsBuy tests data inconsistency handling (SELL more than BUY)
func TestMatchTrades_SellExceedsBuy(t *testing.T) {
	time1 := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	time2 := time.Date(2024, 1, 2, 10, 0, 0, 0, time.UTC)

	trades := []trading.Trade{
		createTrade("AAPL", trading.TradeSideBuy, 50, 150, time1, "core"),
		createTrade("AAPL", trading.TradeSideSell, 100, 160, time2, "core"),
	}

	closed := matchTrades(trades, testLogger())

	// Should only match available quantity (50)
	if len(closed) != 1 {
		t.Fatalf("Expected 1 closed trade (match available), got %d", len(closed))
	}

	ct := closed[0]
	if ct.Quantity != 50 {
		t.Errorf("Expected quantity 50 (available), got %f", ct.Quantity)
	}
}

// TestMatchTrades_MultipleSymbols tests that symbols are isolated
func TestMatchTrades_MultipleSymbols(t *testing.T) {
	time1 := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	time2 := time.Date(2024, 1, 2, 10, 0, 0, 0, time.UTC)
	time3 := time.Date(2024, 1, 3, 10, 0, 0, 0, time.UTC)
	time4 := time.Date(2024, 1, 4, 10, 0, 0, 0, time.UTC)

	trades := []trading.Trade{
		createTrade("AAPL", trading.TradeSideBuy, 100, 150, time1, "core"),
		createTrade("MSFT", trading.TradeSideBuy, 50, 300, time2, "core"),
		createTrade("AAPL", trading.TradeSideSell, 100, 160, time3, "core"),
		createTrade("MSFT", trading.TradeSideSell, 50, 310, time4, "core"),
	}

	closed := matchTrades(trades, testLogger())

	if len(closed) != 2 {
		t.Fatalf("Expected 2 closed trades (one per symbol), got %d", len(closed))
	}

	// Verify both symbols are present
	symbols := make(map[string]bool)
	for _, ct := range closed {
		symbols[ct.Symbol] = true
	}

	if !symbols["AAPL"] {
		t.Error("Expected AAPL in closed trades")
	}
	if !symbols["MSFT"] {
		t.Error("Expected MSFT in closed trades")
	}
}

// TestMatchTrades_ChronologicalOrdering tests that trades are processed chronologically
func TestMatchTrades_ChronologicalOrdering(t *testing.T) {
	// Create trades out of chronological order
	time1 := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	time2 := time.Date(2024, 1, 2, 10, 0, 0, 0, time.UTC)
	time3 := time.Date(2024, 1, 3, 10, 0, 0, 0, time.UTC)

	trades := []trading.Trade{
		createTrade("AAPL", trading.TradeSideSell, 50, 160, time3, "core"), // Out of order
		createTrade("AAPL", trading.TradeSideBuy, 100, 150, time1, "core"),
		createTrade("AAPL", trading.TradeSideBuy, 50, 155, time2, "core"),
	}

	closed := matchTrades(trades, testLogger())

	// Should still match correctly (oldest lot first)
	if len(closed) != 1 {
		t.Fatalf("Expected 1 closed trade, got %d", len(closed))
	}

	ct := closed[0]
	// Should match against first BUY (time1) at 150, not second BUY at 155
	if ct.BuyPrice != 150 {
		t.Errorf("Expected to match oldest lot (price 150), got %f", ct.BuyPrice)
	}
}

// TestBuildEquityCurve tests equity curve construction
func TestBuildEquityCurve(t *testing.T) {
	closedTrades := []ClosedTrade{
		{Symbol: "AAPL", SellDate: "2024-01-02 10:00:00", ProfitLoss: 100},
		{Symbol: "AAPL", SellDate: "2024-01-03 10:00:00", ProfitLoss: 50},
		{Symbol: "MSFT", SellDate: "2024-01-04 10:00:00", ProfitLoss: -30},
	}

	curve := buildEquityCurve(closedTrades)

	// Should have N+1 elements (starting at 0)
	if len(curve) != 4 {
		t.Fatalf("Expected 4 elements in curve, got %d", len(curve))
	}

	if curve[0] != 0 {
		t.Errorf("Expected starting value 0, got %f", curve[0])
	}
	if curve[1] != 100 {
		t.Errorf("Expected curve[1] = 100, got %f", curve[1])
	}
	if curve[2] != 150 {
		t.Errorf("Expected curve[2] = 150, got %f", curve[2])
	}
	if curve[3] != 120 {
		t.Errorf("Expected curve[3] = 120, got %f", curve[3])
	}
}

// TestCalculateReturns tests return calculation
func TestCalculateReturns(t *testing.T) {
	closedTrades := []ClosedTrade{
		{ReturnPct: 0.10},  // 10%
		{ReturnPct: 0.05},  // 5%
		{ReturnPct: -0.02}, // -2%
	}

	returns := calculateReturns(closedTrades)

	if len(returns) != 3 {
		t.Fatalf("Expected 3 returns, got %d", len(returns))
	}
	if returns[0] != 0.10 {
		t.Errorf("Expected returns[0] = 0.10, got %f", returns[0])
	}
	if returns[1] != 0.05 {
		t.Errorf("Expected returns[1] = 0.05, got %f", returns[1])
	}
	if returns[2] != -0.02 {
		t.Errorf("Expected returns[2] = -0.02, got %f", returns[2])
	}
}

// TestCalculateInitialCapital tests initial capital calculation
func TestCalculateInitialCapital(t *testing.T) {
	closedTrades := []ClosedTrade{
		{BuyPrice: 100, Quantity: 10}, // 1000
		{BuyPrice: 200, Quantity: 5},  // 1000
		{BuyPrice: 50, Quantity: 20},  // 1000
	}

	capital := calculateInitialCapital(closedTrades)

	expected := 3000.0
	if capital != expected {
		t.Errorf("Expected initial capital %f, got %f", expected, capital)
	}
}

// TestGetValueEUR tests EUR value extraction
func TestGetValueEUR(t *testing.T) {
	// Test with ValueEUR set
	valueEUR := 1500.0
	trade1 := trading.Trade{
		Price:    150,
		Quantity: 10,
		ValueEUR: &valueEUR,
	}
	result1 := getValueEUR(trade1)
	if result1 != 1500 {
		t.Errorf("Expected 1500 (from ValueEUR), got %f", result1)
	}

	// Test fallback (ValueEUR not set)
	trade2 := trading.Trade{
		Price:    150,
		Quantity: 10,
		ValueEUR: nil,
	}
	result2 := getValueEUR(trade2)
	if result2 != 1500 {
		t.Errorf("Expected 1500 (from Price * Quantity), got %f", result2)
	}
}

// TestMatchTrades_ProfitAndLoss tests both profitable and losing trades
func TestMatchTrades_ProfitAndLoss(t *testing.T) {
	time1 := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	time2 := time.Date(2024, 1, 2, 10, 0, 0, 0, time.UTC)
	time3 := time.Date(2024, 1, 3, 10, 0, 0, 0, time.UTC)
	time4 := time.Date(2024, 1, 4, 10, 0, 0, 0, time.UTC)

	trades := []trading.Trade{
		createTrade("AAPL", trading.TradeSideBuy, 100, 150, time1, "core"),
		createTrade("AAPL", trading.TradeSideSell, 100, 160, time2, "core"), // Profit
		createTrade("MSFT", trading.TradeSideBuy, 50, 300, time3, "core"),
		createTrade("MSFT", trading.TradeSideSell, 50, 290, time4, "core"), // Loss
	}

	closed := matchTrades(trades, testLogger())

	if len(closed) != 2 {
		t.Fatalf("Expected 2 closed trades, got %d", len(closed))
	}

	// Find the AAPL trade (should be profitable)
	var aaplTrade *ClosedTrade
	var msftTrade *ClosedTrade
	for i := range closed {
		if closed[i].Symbol == "AAPL" {
			aaplTrade = &closed[i]
		} else if closed[i].Symbol == "MSFT" {
			msftTrade = &closed[i]
		}
	}

	if aaplTrade == nil || msftTrade == nil {
		t.Fatal("Missing expected trades")
	}

	// AAPL should have profit
	if aaplTrade.ProfitLoss <= 0 {
		t.Errorf("Expected AAPL to have profit, got %f", aaplTrade.ProfitLoss)
	}

	// MSFT should have loss
	if msftTrade.ProfitLoss >= 0 {
		t.Errorf("Expected MSFT to have loss, got %f", msftTrade.ProfitLoss)
	}
}

// TestMatchTrades_EmptyTrades tests empty input
func TestMatchTrades_EmptyTrades(t *testing.T) {
	trades := []trading.Trade{}
	closed := matchTrades(trades, testLogger())

	if len(closed) != 0 {
		t.Errorf("Expected 0 closed trades for empty input, got %d", len(closed))
	}
}

// TestBuildEquityCurve_EmptyTrades tests equity curve with empty input
func TestBuildEquityCurve_EmptyTrades(t *testing.T) {
	closedTrades := []ClosedTrade{}
	curve := buildEquityCurve(closedTrades)

	if len(curve) != 0 {
		t.Errorf("Expected empty curve for empty input, got %d elements", len(curve))
	}
}

// TestMatchTrades_MultipleSellsBeforeBuy tests selling before buying (should log warning)
func TestMatchTrades_MultipleSellsBeforeBuy(t *testing.T) {
	time1 := time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC)
	time2 := time.Date(2024, 1, 2, 10, 0, 0, 0, time.UTC)

	trades := []trading.Trade{
		createTrade("AAPL", trading.TradeSideSell, 50, 160, time1, "core"), // Sell before buy
		createTrade("AAPL", trading.TradeSideBuy, 100, 150, time2, "core"),
	}

	closed := matchTrades(trades, testLogger())

	// Should have 0 closed trades (can't match sell without prior buy)
	if len(closed) != 0 {
		t.Errorf("Expected 0 closed trades (sell before buy), got %d", len(closed))
	}
}
