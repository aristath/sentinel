package portfolio

import (
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// TurnoverTracker tracks and calculates portfolio turnover rate
// Faithful translation from Python: app/application/services/turnover_tracker.py
type TurnoverTracker struct {
	ledgerDB    *sql.DB // For trades
	portfolioDB *sql.DB // For portfolio snapshots
	log         zerolog.Logger
}

// NewTurnoverTracker creates a new turnover tracker
func NewTurnoverTracker(ledgerDB, portfolioDB *sql.DB, log zerolog.Logger) *TurnoverTracker {
	return &TurnoverTracker{
		ledgerDB:    ledgerDB,
		portfolioDB: portfolioDB,
		log:         log.With().Str("service", "turnover").Logger(),
	}
}

// CalculateAnnualTurnover calculates annual portfolio turnover for the last 365 days
// Faithful translation of Python: async def calculate_annual_turnover(self, end_date: Optional[str] = None) -> Optional[float]
//
// Turnover = (total_buy_value + total_sell_value) / 2 / average_portfolio_value
func (t *TurnoverTracker) CalculateAnnualTurnover(endDate string) (*float64, error) {
	if endDate == "" {
		endDate = time.Now().Format("2006-01-02")
	}

	// Calculate start date (365 days ago)
	endDt, err := time.Parse("2006-01-02", endDate)
	if err != nil {
		return nil, fmt.Errorf("invalid end_date format: %w", err)
	}

	startDt := endDt.AddDate(0, 0, -365)
	startDate := startDt.Format("2006-01-02")
	// Use next day for end_date to include all trades on end_date
	endDateNext := endDt.AddDate(0, 0, 1).Format("2006-01-02")

	// Get all trades in the 365-day window
	trades, err := t.getTradesInRange(startDate, endDateNext)
	if err != nil {
		return nil, fmt.Errorf("failed to get trades: %w", err)
	}

	if len(trades) == 0 {
		t.log.Debug().Msg("No trades found for turnover calculation")
		return nil, nil
	}

	// Calculate total buy and sell values in EUR
	totalBuyValue := 0.0
	totalSellValue := 0.0

	for _, trade := range trades {
		side := strings.ToUpper(trade.Side)
		tradeValueEUR := trade.ValueEUR

		// Fallback: calculate from quantity * price * currency_rate
		if tradeValueEUR <= 0 {
			currencyRate := trade.CurrencyRate
			if currencyRate == 0 {
				currencyRate = 1.0
			}
			tradeValueEUR = trade.Quantity * trade.Price * currencyRate
		}

		if side == "BUY" {
			totalBuyValue += tradeValueEUR
		} else if side == "SELL" {
			totalSellValue += tradeValueEUR
		}
	}

	// Calculate average portfolio value from snapshots
	snapshots, err := t.getSnapshotsInRange(startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to get snapshots: %w", err)
	}

	if len(snapshots) == 0 {
		t.log.Debug().Msg("No portfolio snapshots found for turnover calculation")
		return nil, nil
	}

	// Calculate average portfolio value
	totalValueSum := 0.0
	for _, snap := range snapshots {
		totalValueSum += snap.TotalValue
	}
	averagePortfolioValue := totalValueSum / float64(len(snapshots))

	if averagePortfolioValue <= 0 {
		t.log.Warn().Msg("Average portfolio value is zero or negative")
		return nil, nil
	}

	// Calculate turnover: (buys + sells) / 2 / average_value
	turnover := (totalBuyValue + totalSellValue) / 2.0 / averagePortfolioValue

	t.log.Debug().
		Float64("buys", totalBuyValue).
		Float64("sells", totalSellValue).
		Float64("avg_value", averagePortfolioValue).
		Float64("turnover", turnover*100).
		Msg("Turnover calculation")

	return &turnover, nil
}

// GetTurnoverStatus formats turnover with alerts
// Faithful translation of Python: async def get_turnover_status(self, turnover: Optional[float]) -> dict
func (t *TurnoverTracker) GetTurnoverStatus(turnover *float64) TurnoverInfo {
	if turnover == nil {
		return TurnoverInfo{
			AnnualTurnover:  nil,
			TurnoverDisplay: "N/A",
			Status:          "unknown",
			Alert:           nil,
			Reason:          "Insufficient data to calculate turnover",
		}
	}

	// Alert thresholds
	const (
		warningThreshold  = 0.50 // 50% annual turnover
		criticalThreshold = 1.00 // 100% annual turnover
	)

	var status, reason string
	var alert *string

	if *turnover >= criticalThreshold {
		status = "critical"
		alertStr := "critical"
		alert = &alertStr
		reason = fmt.Sprintf("Very high turnover: %.1f%% (exceeds %.0f%% threshold)", *turnover*100, criticalThreshold*100)
	} else if *turnover >= warningThreshold {
		status = "warning"
		alertStr := "warning"
		alert = &alertStr
		reason = fmt.Sprintf("High turnover: %.1f%% (exceeds %.0f%% threshold)", *turnover*100, warningThreshold*100)
	} else {
		status = "normal"
		alert = nil
		reason = fmt.Sprintf("Normal turnover: %.1f%%", *turnover*100)
	}

	return TurnoverInfo{
		AnnualTurnover:  turnover,
		TurnoverDisplay: fmt.Sprintf("%.2f%%", *turnover*100),
		Status:          status,
		Alert:           alert,
		Reason:          reason,
	}
}

// tradeRow represents simplified trade data for turnover calculation
type tradeRow struct {
	Side         string
	Quantity     float64
	Price        float64
	CurrencyRate float64
	ValueEUR     float64
}

// getTradesInRange retrieves trades within date range
func (t *TurnoverTracker) getTradesInRange(startDate, endDate string) ([]tradeRow, error) {
	query := `
		SELECT side, quantity, price, currency_rate, value_eur
		FROM trades
		WHERE executed_at >= ? AND executed_at < ?
		ORDER BY executed_at
	`

	rows, err := t.ledgerDB.Query(query, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to query trades: %w", err)
	}
	defer rows.Close()

	var trades []tradeRow
	for rows.Next() {
		var trade tradeRow
		var currencyRate, valueEUR sql.NullFloat64

		if err := rows.Scan(&trade.Side, &trade.Quantity, &trade.Price, &currencyRate, &valueEUR); err != nil {
			return nil, fmt.Errorf("failed to scan trade: %w", err)
		}

		if currencyRate.Valid {
			trade.CurrencyRate = currencyRate.Float64
		} else {
			trade.CurrencyRate = 1.0
		}

		if valueEUR.Valid {
			trade.ValueEUR = valueEUR.Float64
		}

		trades = append(trades, trade)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating trades: %w", err)
	}

	return trades, nil
}

// snapshotRow represents simplified snapshot data for turnover calculation
type snapshotRow struct {
	TotalValue float64
}

// getSnapshotsInRange retrieves snapshots within date range
func (t *TurnoverTracker) getSnapshotsInRange(startDate, endDate string) ([]snapshotRow, error) {
	query := `
		SELECT total_value
		FROM portfolio_snapshots
		WHERE date >= ? AND date <= ?
		ORDER BY date
	`

	rows, err := t.portfolioDB.Query(query, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to query snapshots: %w", err)
	}
	defer rows.Close()

	var snapshots []snapshotRow
	for rows.Next() {
		var snap snapshotRow
		if err := rows.Scan(&snap.TotalValue); err != nil {
			return nil, fmt.Errorf("failed to scan snapshot: %w", err)
		}
		snapshots = append(snapshots, snap)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating snapshots: %w", err)
	}

	return snapshots, nil
}
