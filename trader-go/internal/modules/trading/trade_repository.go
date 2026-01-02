package trading

import (
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// TradeRepository handles trade database operations
// Faithful translation from Python: app/repositories/trade.py
type TradeRepository struct {
	ledgerDB *sql.DB // ledger.db - trades table
	log      zerolog.Logger
}

// NewTradeRepository creates a new trade repository
func NewTradeRepository(ledgerDB *sql.DB, log zerolog.Logger) *TradeRepository {
	return &TradeRepository{
		ledgerDB: ledgerDB,
		log:      log.With().Str("repo", "trade").Logger(),
	}
}

// Create inserts a new trade record
// Faithful translation of Python: async def create(self, trade: Trade) -> None
func (r *TradeRepository) Create(trade Trade) error {
	now := time.Now().Format(time.RFC3339)
	executedAt := trade.ExecutedAt.Format(time.RFC3339)

	query := `
		INSERT INTO trades
		(symbol, isin, side, quantity, price, executed_at, order_id,
		 currency, currency_rate, value_eur, source, bucket_id, mode, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err := r.ledgerDB.Exec(query,
		strings.ToUpper(strings.TrimSpace(trade.Symbol)),
		nullString(trade.ISIN),
		strings.ToUpper(string(trade.Side)),
		trade.Quantity,
		trade.Price,
		executedAt,
		nullString(trade.OrderID),
		nullString(trade.Currency),
		nullFloat64Ptr(trade.CurrencyRate),
		nullFloat64Ptr(trade.ValueEUR),
		trade.Source,
		trade.BucketID,
		trade.Mode,
		now,
	)

	if err != nil {
		return fmt.Errorf("failed to create trade: %w", err)
	}

	r.log.Info().
		Str("symbol", trade.Symbol).
		Str("side", string(trade.Side)).
		Float64("quantity", trade.Quantity).
		Msg("Trade created")

	return nil
}

// GetByOrderID retrieves a trade by broker order ID
// Faithful translation of Python: async def get_by_order_id(self, order_id: str) -> Optional[Trade]
func (r *TradeRepository) GetByOrderID(orderID string) (*Trade, error) {
	query := "SELECT * FROM trades WHERE order_id = ?"

	row := r.ledgerDB.QueryRow(query, orderID)
	trade, err := r.scanTrade(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get trade by order_id: %w", err)
	}

	return &trade, nil
}

// Exists checks if a trade with the given order_id already exists
// Faithful translation of Python: async def exists(self, order_id: str) -> bool
func (r *TradeRepository) Exists(orderID string) (bool, error) {
	query := "SELECT 1 FROM trades WHERE order_id = ? LIMIT 1"

	var exists int
	err := r.ledgerDB.QueryRow(query, orderID).Scan(&exists)
	if errors.Is(err, sql.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("failed to check trade existence: %w", err)
	}

	return true, nil
}

// GetHistory retrieves trade history, most recent first
// Faithful translation of Python: async def get_history(self, limit: int = 50) -> List[Trade]
func (r *TradeRepository) GetHistory(limit int) ([]Trade, error) {
	query := `
		SELECT * FROM trades
		ORDER BY executed_at DESC
		LIMIT ?
	`

	rows, err := r.ledgerDB.Query(query, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to get trade history: %w", err)
	}
	defer rows.Close()

	var trades []Trade
	for rows.Next() {
		trade, err := r.scanTradeFromRows(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan trade: %w", err)
		}
		trades = append(trades, trade)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating trades: %w", err)
	}

	return trades, nil
}

// GetAllInRange retrieves all trades within a date range
// Faithful translation of Python: async def get_all_in_range(self, start_date: str, end_date: str) -> List[Trade]
func (r *TradeRepository) GetAllInRange(startDate, endDate string) ([]Trade, error) {
	query := `
		SELECT * FROM trades
		WHERE executed_at >= ? AND executed_at <= ?
		ORDER BY executed_at ASC
	`

	rows, err := r.ledgerDB.Query(query, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to get trades in range: %w", err)
	}
	defer rows.Close()

	var trades []Trade
	for rows.Next() {
		trade, err := r.scanTradeFromRows(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan trade: %w", err)
		}
		trades = append(trades, trade)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating trades: %w", err)
	}

	return trades, nil
}

// GetBySymbol retrieves trades for a specific symbol
// Faithful translation of Python: async def get_by_symbol(self, symbol: str, limit: int = 100) -> List[Trade]
func (r *TradeRepository) GetBySymbol(symbol string, limit int) ([]Trade, error) {
	query := `
		SELECT * FROM trades
		WHERE symbol = ?
		ORDER BY executed_at DESC
		LIMIT ?
	`

	rows, err := r.ledgerDB.Query(query, strings.ToUpper(symbol), limit)
	if err != nil {
		return nil, fmt.Errorf("failed to get trades by symbol: %w", err)
	}
	defer rows.Close()

	var trades []Trade
	for rows.Next() {
		trade, err := r.scanTradeFromRows(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan trade: %w", err)
		}
		trades = append(trades, trade)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating trades: %w", err)
	}

	return trades, nil
}

// GetByISIN retrieves trades for a specific ISIN
// Faithful translation of Python: async def get_by_isin(self, isin: str, limit: int = 100) -> List[Trade]
func (r *TradeRepository) GetByISIN(isin string, limit int) ([]Trade, error) {
	query := `
		SELECT * FROM trades
		WHERE isin = ?
		ORDER BY executed_at DESC
		LIMIT ?
	`

	rows, err := r.ledgerDB.Query(query, strings.ToUpper(isin), limit)
	if err != nil {
		return nil, fmt.Errorf("failed to get trades by ISIN: %w", err)
	}
	defer rows.Close()

	var trades []Trade
	for rows.Next() {
		trade, err := r.scanTradeFromRows(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan trade: %w", err)
		}
		trades = append(trades, trade)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating trades: %w", err)
	}

	return trades, nil
}

// GetByIdentifier retrieves trades by symbol or ISIN
// Faithful translation of Python: async def get_by_identifier(self, identifier: str, limit: int = 100) -> List[Trade]
func (r *TradeRepository) GetByIdentifier(identifier string, limit int) ([]Trade, error) {
	identifier = strings.ToUpper(strings.TrimSpace(identifier))

	// Check if it looks like an ISIN (12 chars, country code + alphanumeric)
	if len(identifier) == 12 && isAlpha(identifier[:2]) {
		trades, err := r.GetByISIN(identifier, limit)
		if err == nil && len(trades) > 0 {
			return trades, nil
		}
	}

	// Try symbol lookup
	return r.GetBySymbol(identifier, limit)
}

// GetRecentlyBoughtSymbols returns symbols bought in the last N days (excluding RESEARCH trades)
// Faithful translation of Python: async def get_recently_bought_symbols(self, days: int = 30) -> Set[str]
func (r *TradeRepository) GetRecentlyBoughtSymbols(days int) (map[string]bool, error) {
	cutoff := time.Now().AddDate(0, 0, -days).Format(time.RFC3339)

	query := `
		SELECT DISTINCT symbol FROM trades
		WHERE UPPER(side) = 'BUY'
		  AND executed_at >= ?
		  AND order_id IS NOT NULL
		  AND order_id != ''
		  AND order_id NOT LIKE 'RESEARCH_%'
	`

	rows, err := r.ledgerDB.Query(query, cutoff)
	if err != nil {
		return nil, fmt.Errorf("failed to get recently bought symbols: %w", err)
	}
	defer rows.Close()

	symbols := make(map[string]bool)
	for rows.Next() {
		var symbol string
		if err := rows.Scan(&symbol); err != nil {
			return nil, fmt.Errorf("failed to scan symbol: %w", err)
		}
		symbols[symbol] = true
	}

	return symbols, nil
}

// GetRecentlySoldSymbols returns symbols sold in the last N days (excluding RESEARCH trades)
// Faithful translation of Python: async def get_recently_sold_symbols(self, days: int = 30) -> Set[str]
func (r *TradeRepository) GetRecentlySoldSymbols(days int) (map[string]bool, error) {
	cutoff := time.Now().AddDate(0, 0, -days).Format(time.RFC3339)

	query := `
		SELECT DISTINCT symbol FROM trades
		WHERE UPPER(side) = 'SELL'
		  AND executed_at >= ?
		  AND (order_id IS NULL OR order_id NOT LIKE 'RESEARCH_%')
	`

	rows, err := r.ledgerDB.Query(query, cutoff)
	if err != nil {
		return nil, fmt.Errorf("failed to get recently sold symbols: %w", err)
	}
	defer rows.Close()

	symbols := make(map[string]bool)
	for rows.Next() {
		var symbol string
		if err := rows.Scan(&symbol); err != nil {
			return nil, fmt.Errorf("failed to scan symbol: %w", err)
		}
		symbols[symbol] = true
	}

	return symbols, nil
}

// HasRecentSellOrder checks if there's a recent SELL order for the symbol
// Faithful translation of Python: async def has_recent_sell_order(self, symbol: str, hours: float = 2.0) -> bool
func (r *TradeRepository) HasRecentSellOrder(symbol string, hours float64) (bool, error) {
	cutoff := time.Now().Add(-time.Duration(hours * float64(time.Hour))).Format(time.RFC3339)

	query := `
		SELECT 1 FROM trades
		WHERE symbol = ?
		  AND UPPER(side) = 'SELL'
		  AND executed_at >= ?
		  AND (order_id IS NULL OR order_id NOT LIKE 'RESEARCH_%')
		LIMIT 1
	`

	var exists int
	err := r.ledgerDB.QueryRow(query, strings.ToUpper(symbol), cutoff).Scan(&exists)
	if errors.Is(err, sql.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("failed to check recent sell order: %w", err)
	}

	return true, nil
}

// GetFirstBuyDate returns the date of first buy for a symbol
// Faithful translation of Python: async def get_first_buy_date(self, symbol: str) -> Optional[str]
func (r *TradeRepository) GetFirstBuyDate(symbol string) (*string, error) {
	query := `
		SELECT MIN(executed_at) as first_buy FROM trades
		WHERE symbol = ? AND UPPER(side) = 'BUY'
	`

	var firstBuy sql.NullString
	err := r.ledgerDB.QueryRow(query, strings.ToUpper(symbol)).Scan(&firstBuy)
	if err != nil {
		return nil, fmt.Errorf("failed to get first buy date: %w", err)
	}

	if !firstBuy.Valid {
		return nil, nil
	}

	return &firstBuy.String, nil
}

// GetLastBuyDate returns the date of most recent buy for a symbol
// Faithful translation of Python: async def get_last_buy_date(self, symbol: str) -> Optional[str]
func (r *TradeRepository) GetLastBuyDate(symbol string) (*string, error) {
	query := `
		SELECT MAX(executed_at) as last_buy FROM trades
		WHERE symbol = ? AND UPPER(side) = 'BUY'
	`

	var lastBuy sql.NullString
	err := r.ledgerDB.QueryRow(query, strings.ToUpper(symbol)).Scan(&lastBuy)
	if err != nil {
		return nil, fmt.Errorf("failed to get last buy date: %w", err)
	}

	if !lastBuy.Valid {
		return nil, nil
	}

	return &lastBuy.String, nil
}

// GetLastSellDate returns the date of last sell for a symbol
// Faithful translation of Python: async def get_last_sell_date(self, symbol: str) -> Optional[str]
func (r *TradeRepository) GetLastSellDate(symbol string) (*string, error) {
	query := `
		SELECT MAX(executed_at) as last_sell FROM trades
		WHERE symbol = ? AND UPPER(side) = 'SELL'
	`

	var lastSell sql.NullString
	err := r.ledgerDB.QueryRow(query, strings.ToUpper(symbol)).Scan(&lastSell)
	if err != nil {
		return nil, fmt.Errorf("failed to get last sell date: %w", err)
	}

	if !lastSell.Valid {
		return nil, nil
	}

	return &lastSell.String, nil
}

// GetLastTransactionDate returns the date of most recent transaction (BUY or SELL)
// Faithful translation of Python: async def get_last_transaction_date(self, symbol: str) -> Optional[str]
func (r *TradeRepository) GetLastTransactionDate(symbol string) (*string, error) {
	query := `
		SELECT MAX(executed_at) as last_transaction FROM trades
		WHERE symbol = ?
	`

	var lastTransaction sql.NullString
	err := r.ledgerDB.QueryRow(query, strings.ToUpper(symbol)).Scan(&lastTransaction)
	if err != nil {
		return nil, fmt.Errorf("failed to get last transaction date: %w", err)
	}

	if !lastTransaction.Valid {
		return nil, nil
	}

	return &lastTransaction.String, nil
}

// GetTradeDates returns first_buy and last_sell dates for all symbols
// Faithful translation of Python: async def get_trade_dates(self) -> dict[str, dict]
func (r *TradeRepository) GetTradeDates() (map[string]map[string]*string, error) {
	query := `
		SELECT
			symbol,
			MIN(CASE WHEN UPPER(side) = 'BUY' THEN executed_at END) as first_buy,
			MAX(CASE WHEN UPPER(side) = 'SELL' THEN executed_at END) as last_sell
		FROM trades
		GROUP BY symbol
	`

	rows, err := r.ledgerDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to get trade dates: %w", err)
	}
	defer rows.Close()

	result := make(map[string]map[string]*string)
	for rows.Next() {
		var symbol string
		var firstBuy, lastSell sql.NullString

		if err := rows.Scan(&symbol, &firstBuy, &lastSell); err != nil {
			return nil, fmt.Errorf("failed to scan trade dates: %w", err)
		}

		dates := make(map[string]*string)
		if firstBuy.Valid {
			dates["first_bought_at"] = &firstBuy.String
		} else {
			dates["first_bought_at"] = nil
		}
		if lastSell.Valid {
			dates["last_sold_at"] = &lastSell.String
		} else {
			dates["last_sold_at"] = nil
		}

		result[symbol] = dates
	}

	return result, nil
}

// GetRecentTrades returns recent trades for a symbol within N days
// Faithful translation of Python: async def get_recent_trades(self, symbol: str, days: int = 30) -> List[Trade]
func (r *TradeRepository) GetRecentTrades(symbol string, days int) ([]Trade, error) {
	cutoff := time.Now().AddDate(0, 0, -days).Format(time.RFC3339)

	query := `
		SELECT * FROM trades
		WHERE symbol = ? AND executed_at >= ?
		ORDER BY executed_at DESC
	`

	rows, err := r.ledgerDB.Query(query, strings.ToUpper(symbol), cutoff)
	if err != nil {
		return nil, fmt.Errorf("failed to get recent trades: %w", err)
	}
	defer rows.Close()

	var trades []Trade
	for rows.Next() {
		trade, err := r.scanTradeFromRows(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan trade: %w", err)
		}
		trades = append(trades, trade)
	}

	return trades, nil
}

// GetLastTradeTimestamp returns timestamp of the most recent trade
// Faithful translation of Python: async def get_last_trade_timestamp(self) -> Optional[datetime]
func (r *TradeRepository) GetLastTradeTimestamp() (*time.Time, error) {
	query := `
		SELECT executed_at
		FROM trades
		ORDER BY executed_at DESC
		LIMIT 1
	`

	var executedAt sql.NullString
	err := r.ledgerDB.QueryRow(query).Scan(&executedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get last trade timestamp: %w", err)
	}

	if !executedAt.Valid {
		return nil, nil
	}

	t, err := time.Parse(time.RFC3339, executedAt.String)
	if err != nil {
		return nil, fmt.Errorf("failed to parse timestamp: %w", err)
	}

	return &t, nil
}

// GetTradeCountToday counts trades executed today
// Faithful translation of Python: async def get_trade_count_today(self) -> int
func (r *TradeRepository) GetTradeCountToday() (int, error) {
	today := time.Now().Format("2006-01-02")

	query := `
		SELECT COUNT(*) as cnt
		FROM trades
		WHERE DATE(executed_at) = ?
	`

	var count int
	err := r.ledgerDB.QueryRow(query, today).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to get trade count today: %w", err)
	}

	return count, nil
}

// GetTradeCountThisWeek counts trades executed in the last 7 days
// Faithful translation of Python: async def get_trade_count_this_week(self) -> int
func (r *TradeRepository) GetTradeCountThisWeek() (int, error) {
	sevenDaysAgo := time.Now().AddDate(0, 0, -7).Format("2006-01-02")

	query := `
		SELECT COUNT(*) as cnt
		FROM trades
		WHERE executed_at >= ?
	`

	var count int
	err := r.ledgerDB.QueryRow(query, sevenDaysAgo).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to get trade count this week: %w", err)
	}

	return count, nil
}

// PositionHistoryEntry represents a position at a specific date
type PositionHistoryEntry struct {
	Date     string  `json:"date"`
	Symbol   string  `json:"symbol"`
	Quantity float64 `json:"quantity"`
}

// tradeRow represents a simplified trade row for position history calculation
type tradeRow struct {
	Symbol     string
	Side       string
	Quantity   float64
	ExecutedAt string
}

// GetPositionHistory retrieves historical position quantities by date for portfolio reconstruction
// Faithful translation of Python: async def get_position_history(self, start_date: str, end_date: str) -> List[dict]
func (r *TradeRepository) GetPositionHistory(startDate, endDate string) ([]PositionHistoryEntry, error) {
	// Get all trades up to end_date to build complete position history
	query := `
		SELECT symbol, side, quantity, executed_at
		FROM trades
		WHERE executed_at <= ?
		ORDER BY executed_at ASC
	`

	rows, err := r.ledgerDB.Query(query, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to get position history: %w", err)
	}
	defer rows.Close()

	// Collect all rows

	var allTrades []tradeRow
	for rows.Next() {
		var row tradeRow
		if err := rows.Scan(&row.Symbol, &row.Side, &row.Quantity, &row.ExecutedAt); err != nil {
			return nil, fmt.Errorf("failed to scan trade row: %w", err)
		}
		allTrades = append(allTrades, row)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating trades: %w", err)
	}

	// Build position state up to start_date
	cumulativePositions := make(map[string]float64) // {symbol: quantity}
	var preStartTrades []tradeRow
	var inRangeTrades []tradeRow

	for _, row := range allTrades {
		date := row.ExecutedAt[:10] // Extract YYYY-MM-DD
		if date < startDate {
			preStartTrades = append(preStartTrades, row)
		} else {
			inRangeTrades = append(inRangeTrades, row)
		}
	}

	// Process trades before start_date
	processPreStartTrades(preStartTrades, cumulativePositions)

	// Build initial positions
	result := buildInitialPositions(cumulativePositions, startDate)

	// Process in-range trades
	processInRangeTrades(inRangeTrades, cumulativePositions, &result)

	return result, nil
}

// processPreStartTrades processes trades before start_date to build initial positions
// Faithful translation from Python: def _process_pre_start_trades
func processPreStartTrades(preStartTrades []tradeRow, cumulativePositions map[string]float64) {
	for _, row := range preStartTrades {
		symbol := row.Symbol
		side := strings.ToUpper(row.Side)
		quantity := row.Quantity

		if _, exists := cumulativePositions[symbol]; !exists {
			cumulativePositions[symbol] = 0.0
		}

		if side == "BUY" {
			cumulativePositions[symbol] += quantity
		} else if side == "SELL" {
			cumulativePositions[symbol] -= quantity
			if cumulativePositions[symbol] < 0 {
				cumulativePositions[symbol] = 0.0
			}
		}
	}
}

// buildInitialPositions builds initial position entries at start_date
// Faithful translation from Python: def _build_initial_positions
func buildInitialPositions(cumulativePositions map[string]float64, startDate string) []PositionHistoryEntry {
	var result []PositionHistoryEntry
	for symbol, quantity := range cumulativePositions {
		if quantity > 0 {
			result = append(result, PositionHistoryEntry{
				Date:     startDate,
				Symbol:   symbol,
				Quantity: quantity,
			})
		}
	}
	return result
}

// buildPositionsByDate builds positions_by_date dictionary from in-range trades
// Faithful translation from Python: def _build_positions_by_date
func buildPositionsByDate(inRangeTrades []tradeRow) map[string]map[string]float64 {
	positionsByDate := make(map[string]map[string]float64)
	for _, row := range inRangeTrades {
		date := row.ExecutedAt[:10]
		symbol := row.Symbol
		side := strings.ToUpper(row.Side)
		quantity := row.Quantity

		if _, exists := positionsByDate[date]; !exists {
			positionsByDate[date] = make(map[string]float64)
		}

		if _, exists := positionsByDate[date][symbol]; !exists {
			positionsByDate[date][symbol] = 0.0
		}

		if side == "BUY" {
			positionsByDate[date][symbol] += quantity
		} else if side == "SELL" {
			positionsByDate[date][symbol] -= quantity
		}
	}
	return positionsByDate
}

// updatePositionsForDate updates cumulative positions for a date and adds to result
// Faithful translation from Python: def _update_positions_for_date
func updatePositionsForDate(
	date string,
	positionsByDate map[string]map[string]float64,
	cumulativePositions map[string]float64,
	result *[]PositionHistoryEntry,
) {
	for symbol, delta := range positionsByDate[date] {
		if _, exists := cumulativePositions[symbol]; !exists {
			cumulativePositions[symbol] = 0.0
		}
		cumulativePositions[symbol] += delta
		if cumulativePositions[symbol] < 0 {
			cumulativePositions[symbol] = 0.0
		}
	}

	for symbol, quantity := range cumulativePositions {
		if quantity > 0 {
			*result = append(*result, PositionHistoryEntry{
				Date:     date,
				Symbol:   symbol,
				Quantity: quantity,
			})
		}
	}
}

// processInRangeTrades processes trades in date range and updates result
// Faithful translation from Python: def _process_in_range_trades
func processInRangeTrades(
	inRangeTrades []tradeRow,
	cumulativePositions map[string]float64,
	result *[]PositionHistoryEntry,
) {
	positionsByDate := buildPositionsByDate(inRangeTrades)

	// Get sorted dates
	var dates []string
	for date := range positionsByDate {
		dates = append(dates, date)
	}

	// Sort dates
	for i := 0; i < len(dates); i++ {
		for j := i + 1; j < len(dates); j++ {
			if dates[i] > dates[j] {
				dates[i], dates[j] = dates[j], dates[i]
			}
		}
	}

	for _, date := range dates {
		updatePositionsForDate(date, positionsByDate, cumulativePositions, result)
	}
}

// Helper methods

func (r *TradeRepository) scanTrade(row *sql.Row) (Trade, error) {
	var trade Trade
	var executedAt, createdAt sql.NullString
	var isin, orderID, currency sql.NullString
	var currencyRate, valueEUR sql.NullFloat64

	err := row.Scan(
		&trade.ID,
		&trade.Symbol,
		&trade.Side,
		&trade.Quantity,
		&trade.Price,
		&executedAt,
		&orderID,
		&currency,
		&currencyRate,
		&valueEUR,
		&trade.Source,
		&createdAt,
		&isin,
		&trade.BucketID,
		&trade.Mode,
	)

	if err != nil {
		return trade, err
	}

	// Parse timestamps
	// Database stores timestamps in two possible formats:
	// 1. "2024-05-14T16:30:06.000" (ISO8601 without timezone)
	// 2. "2025-12-24 16:16:23" (datetime format)
	if executedAt.Valid {
		// Try RFC3339 first
		t, err := time.Parse(time.RFC3339, executedAt.String)
		if err != nil {
			// Try without timezone (add Z suffix)
			t, err = time.Parse(time.RFC3339, executedAt.String+"Z")
		}
		if err != nil {
			// Try datetime format
			t, err = time.Parse("2006-01-02 15:04:05", executedAt.String)
		}
		if err == nil {
			trade.ExecutedAt = t
		}
	}

	if createdAt.Valid {
		// Try RFC3339 first
		t, err := time.Parse(time.RFC3339, createdAt.String)
		if err != nil {
			// Try datetime format
			t, err = time.Parse("2006-01-02 15:04:05", createdAt.String)
		}
		if err != nil {
			// Try with milliseconds
			t, err = time.Parse("2006-01-02 15:04:05.999", createdAt.String)
		}
		if err == nil {
			trade.CreatedAt = &t
		}
	}

	// Handle optional fields
	if isin.Valid {
		trade.ISIN = isin.String
	}
	if orderID.Valid {
		trade.OrderID = orderID.String
	}
	if currency.Valid {
		trade.Currency = currency.String
	}
	if currencyRate.Valid {
		trade.CurrencyRate = &currencyRate.Float64
	}
	if valueEUR.Valid {
		trade.ValueEUR = &valueEUR.Float64
	}

	// Normalize symbol
	trade.Symbol = strings.ToUpper(strings.TrimSpace(trade.Symbol))

	return trade, nil
}

func (r *TradeRepository) scanTradeFromRows(rows *sql.Rows) (Trade, error) {
	var trade Trade
	var executedAt, createdAt sql.NullString
	var isin, orderID, currency sql.NullString
	var currencyRate, valueEUR sql.NullFloat64

	err := rows.Scan(
		&trade.ID,
		&trade.Symbol,
		&trade.Side,
		&trade.Quantity,
		&trade.Price,
		&executedAt,
		&orderID,
		&currency,
		&currencyRate,
		&valueEUR,
		&trade.Source,
		&createdAt,
		&isin,
		&trade.BucketID,
		&trade.Mode,
	)

	if err != nil {
		return trade, err
	}

	// Parse timestamps
	// Database stores timestamps in two possible formats:
	// 1. "2024-05-14T16:30:06.000" (ISO8601 without timezone)
	// 2. "2025-12-24 16:16:23" (datetime format)
	if executedAt.Valid {
		// Try RFC3339 first
		t, err := time.Parse(time.RFC3339, executedAt.String)
		if err != nil {
			// Try without timezone (add Z suffix)
			t, err = time.Parse(time.RFC3339, executedAt.String+"Z")
		}
		if err != nil {
			// Try datetime format
			t, err = time.Parse("2006-01-02 15:04:05", executedAt.String)
		}
		if err == nil {
			trade.ExecutedAt = t
		}
	}

	if createdAt.Valid {
		// Try RFC3339 first
		t, err := time.Parse(time.RFC3339, createdAt.String)
		if err != nil {
			// Try datetime format
			t, err = time.Parse("2006-01-02 15:04:05", createdAt.String)
		}
		if err != nil {
			// Try with milliseconds
			t, err = time.Parse("2006-01-02 15:04:05.999", createdAt.String)
		}
		if err == nil {
			trade.CreatedAt = &t
		}
	}

	// Handle optional fields
	if isin.Valid {
		trade.ISIN = isin.String
	}
	if orderID.Valid {
		trade.OrderID = orderID.String
	}
	if currency.Valid {
		trade.Currency = currency.String
	}
	if currencyRate.Valid {
		trade.CurrencyRate = &currencyRate.Float64
	}
	if valueEUR.Valid {
		trade.ValueEUR = &valueEUR.Float64
	}

	// Normalize symbol
	trade.Symbol = strings.ToUpper(strings.TrimSpace(trade.Symbol))

	return trade, nil
}

// Helper functions

func nullString(s string) sql.NullString {
	if s == "" {
		return sql.NullString{Valid: false}
	}
	return sql.NullString{String: s, Valid: true}
}

func nullFloat64Ptr(f *float64) sql.NullFloat64 {
	if f == nil {
		return sql.NullFloat64{Valid: false}
	}
	return sql.NullFloat64{Float64: *f, Valid: true}
}

func isAlpha(s string) bool {
	for _, r := range s {
		if (r < 'A' || r > 'Z') && (r < 'a' || r > 'z') {
			return false
		}
	}
	return true
}
