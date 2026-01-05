package ticker

import (
	"database/sql"
	"fmt"
	"strings"

	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/rs/zerolog"
)

// TickerContentService generates ticker display text
type TickerContentService struct {
	portfolioDB *sql.DB
	configDB    *sql.DB
	cacheDB     *sql.DB
	cashManager portfolio.CashManager
	log         zerolog.Logger
}

// NewTickerContentService creates a new ticker content service
func NewTickerContentService(
	portfolioDB, configDB, cacheDB *sql.DB,
	cashManager portfolio.CashManager,
	log zerolog.Logger,
) *TickerContentService {
	return &TickerContentService{
		portfolioDB: portfolioDB,
		configDB:    configDB,
		cacheDB:     cacheDB,
		cashManager: cashManager,
		log:         log.With().Str("service", "ticker_content").Logger(),
	}
}

// GenerateTickerText generates complete ticker text from portfolio state
func (s *TickerContentService) GenerateTickerText() (string, error) {
	// Get settings
	showValue := s.getSetting("ticker_show_value", 1.0) == 1.0
	showCash := s.getSetting("ticker_show_cash", 1.0) == 1.0
	showActions := s.getSetting("ticker_show_actions", 1.0) == 1.0
	showAmounts := s.getSetting("ticker_show_amounts", 1.0) == 1.0
	maxActions := int(s.getSetting("ticker_max_actions", 3.0))

	var parts []string

	// Portfolio value
	if showValue {
		value, err := s.getPortfolioValue()
		if err == nil && value > 0 {
			parts = append(parts, fmt.Sprintf("PORTFOLIO %s", formatCurrency(value, "EUR")))
		}
	}

	// Cash balance
	if showCash {
		cash, err := s.getCashBalance("EUR")
		if err == nil {
			// Show cash even if negative (important info)
			parts = append(parts, fmt.Sprintf("CASH %s", formatCurrency(cash, "EUR")))
		}
	}

	// Recommendations
	if showActions {
		actionsText, err := s.getRecommendationsText(maxActions, showAmounts)
		if err == nil && actionsText != "" {
			parts = append(parts, actionsText)
		}
	}

	// Combine or fallback
	if len(parts) > 0 {
		return strings.Join(parts, " * "), nil
	}

	// Fallback: Check if system has any data
	value, _ := s.getPortfolioValue()
	if value > 0 {
		return "READY", nil
	}

	return "SYSTEM ONLINE", nil
}

// getPortfolioValue queries total portfolio value in EUR
func (s *TickerContentService) getPortfolioValue() (float64, error) {
	var total float64
	err := s.portfolioDB.QueryRow(`
		SELECT COALESCE(SUM(market_value_eur), 0)
		FROM positions
		WHERE quantity > 0
	`).Scan(&total)

	if err != nil {
		s.log.Warn().Err(err).Msg("Failed to get portfolio value for ticker")
		return 0, err
	}

	return total, nil
}

// getCashBalance gets total cash balance for currency from CashManager
func (s *TickerContentService) getCashBalance(currency string) (float64, error) {
	cashBalances, err := s.cashManager.GetAllCashBalances()
	if err != nil {
		s.log.Warn().Err(err).Str("currency", currency).Msg("Failed to get cash balance for ticker")
		return 0, err
	}

	if balance, ok := cashBalances[currency]; ok {
		return balance, nil
	}

	return 0, nil
}

// getRecommendationsText formats pending recommendations from cache database
func (s *TickerContentService) getRecommendationsText(limit int, showAmounts bool) (string, error) {
	query := `
		SELECT symbol, side, estimated_value, currency
		FROM recommendations
		WHERE status = 'pending'
		ORDER BY priority ASC, created_at ASC
	`

	if limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", limit)
	}

	rows, err := s.cacheDB.Query(query)
	if err != nil {
		s.log.Warn().Err(err).Msg("Failed to get recommendations for ticker")
		return "", err
	}
	defer rows.Close()

	var parts []string
	for rows.Next() {
		var symbol, side, currency string
		var estimatedValue float64

		err := rows.Scan(&symbol, &side, &estimatedValue, &currency)
		if err != nil {
			s.log.Warn().Err(err).Msg("Failed to scan recommendation")
			continue
		}

		var text string
		if showAmounts {
			text = fmt.Sprintf("%s %s %s",
				strings.ToUpper(side),
				symbol,
				formatCurrency(estimatedValue, currency),
			)
		} else {
			text = fmt.Sprintf("%s %s", strings.ToUpper(side), symbol)
		}
		parts = append(parts, text)
	}

	if err := rows.Err(); err != nil {
		s.log.Warn().Err(err).Msg("Error iterating recommendations")
		return "", err
	}

	return strings.Join(parts, " * "), nil
}

// formatCurrency formats amount as "€1,234"
func formatCurrency(amount float64, currency string) string {
	symbol := "€"
	if currency == "USD" {
		symbol = "$"
	} else if currency == "RUB" {
		symbol = "₽"
	}

	// Truncate to integer (no rounding)
	rounded := int(amount)

	// Format with thousands separator
	absVal := rounded
	if absVal < 0 {
		absVal = -absVal
	}

	formatted := fmt.Sprintf("%d", absVal)
	if absVal >= 1000 {
		// Add comma separator
		n := len(formatted)
		if n > 6 {
			formatted = formatted[:n-6] + "," + formatted[n-6:n-3] + "," + formatted[n-3:]
		} else if n > 3 {
			formatted = formatted[:n-3] + "," + formatted[n-3:]
		}
	}

	if rounded < 0 {
		return fmt.Sprintf("-%s%s", symbol, formatted)
	}
	return fmt.Sprintf("%s%s", symbol, formatted)
}

// getSetting retrieves setting with fallback to default
func (s *TickerContentService) getSetting(key string, defaultVal float64) float64 {
	var floatVal float64
	err := s.configDB.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&floatVal)
	if err == nil {
		return floatVal
	}

	// Return default
	return defaultVal
}
