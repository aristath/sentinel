package trading

import (
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// SecurityProvider defines the interface for getting security information
// Used to avoid circular dependencies with universe module
type SecurityProvider interface {
	GetISINBySymbol(symbol string) (string, error)
	BatchGetISINsBySymbols(symbols []string) (map[string]string, error)
}

// TradeRepository handles trade database operations
// Faithful translation from Python: app/repositories/trade.py
type TradeRepository struct {
	ledgerDB         *sql.DB          // ledger.db - trades table
	securityProvider SecurityProvider // For symbol->ISIN lookup (optional for backwards compatibility)
	log              zerolog.Logger
}

// tradesColumns is the list of columns for the trades table
// Used to avoid SELECT * which can break when schema changes
// Column order must match scanTrade() and scanTradeFromRows() function expectations
// After migration 017: bucket_id removed, currency_rate not scanned
const tradesColumns = `id, symbol, isin, side, quantity, price, executed_at, order_id, currency, value_eur, source, mode, created_at`

// NewTradeRepository creates a new trade repository
func NewTradeRepository(ledgerDB *sql.DB, securityProvider SecurityProvider, log zerolog.Logger) *TradeRepository {
	return &TradeRepository{
		ledgerDB:         ledgerDB,
		securityProvider: securityProvider,
		log:              log.With().Str("repo", "trade").Logger(),
	}
}

// Create inserts a new trade record
// Faithful translation of Python: async def create(self, trade: Trade) -> None
func (r *TradeRepository) Create(trade Trade) error {
	// Validate trade before database insertion to prevent constraint violations
	if err := trade.Validate(); err != nil {
		return fmt.Errorf("failed to create trade: %w", err)
	}

	// Check for existing trade with same order_id to prevent duplicates
	// This is a safety check in addition to the UNIQUE index constraint
	if trade.OrderID != "" {
		exists, err := r.Exists(trade.OrderID)
		if err != nil {
			return fmt.Errorf("failed to check for existing trade: %w", err)
		}
		if exists {
			r.log.Debug().
				Str("order_id", trade.OrderID).
				Msg("Trade with order_id already exists, skipping duplicate")
			return nil // Silently skip duplicate - trade already recorded
		}
	}

	now := time.Now().Unix()
	executedAt := trade.ExecutedAt.Unix()

	// Table schema: id, symbol, isin, side, quantity, price, executed_at, order_id, currency, value_eur, source, mode, created_at
	query := `
		INSERT INTO trades
		(symbol, isin, side, quantity, price, executed_at, order_id,
		 currency, value_eur, source, mode, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	// Ensure ISIN is populated (required after migration)
	// If not provided, try to lookup from securities via provider
	if trade.ISIN == "" && r.securityProvider != nil {
		isin, err := r.securityProvider.GetISINBySymbol(trade.Symbol)
		if err == nil {
			trade.ISIN = isin
		}
	}

	_, err := r.ledgerDB.Exec(query,
		strings.ToUpper(strings.TrimSpace(trade.Symbol)),
		nullString(trade.ISIN),
		string(trade.Side),
		trade.Quantity,
		trade.Price,
		executedAt,
		nullString(trade.OrderID),
		nullString(trade.Currency),
		nullFloat64Ptr(trade.ValueEUR),
		trade.Source,
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
	query := "SELECT " + tradesColumns + " FROM trades WHERE order_id = ?"

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
		SELECT ` + tradesColumns + ` FROM trades
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
// startDate and endDate are in YYYY-MM-DD format, converted to Unix timestamps at midnight UTC
func (r *TradeRepository) GetAllInRange(startDate, endDate string) ([]Trade, error) {
	// Convert YYYY-MM-DD to Unix timestamps at midnight UTC
	startTime, err := time.Parse("2006-01-02", startDate)
	if err != nil {
		return nil, fmt.Errorf("invalid start_date format (expected YYYY-MM-DD): %w", err)
	}
	startUnix := time.Date(startTime.Year(), startTime.Month(), startTime.Day(), 0, 0, 0, 0, time.UTC).Unix()

	endTime, err := time.Parse("2006-01-02", endDate)
	if err != nil {
		return nil, fmt.Errorf("invalid end_date format (expected YYYY-MM-DD): %w", err)
	}
	// End date should be end of day (23:59:59)
	endUnix := time.Date(endTime.Year(), endTime.Month(), endTime.Day(), 23, 59, 59, 0, time.UTC).Unix()

	query := `
		SELECT ` + tradesColumns + ` FROM trades
		WHERE executed_at >= ? AND executed_at <= ?
		ORDER BY executed_at ASC
	`

	rows, err := r.ledgerDB.Query(query, startUnix, endUnix)
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

// GetBySymbol retrieves trades for a specific symbol (helper method - looks up ISIN first)
// This requires securityProvider to lookup ISIN from securities table
// After migration: prefer GetByISIN for internal operations
func (r *TradeRepository) GetBySymbol(symbol string, limit int) ([]Trade, error) {
	// If security provider is available, lookup ISIN first, then query by ISIN
	if r.securityProvider != nil {
		isin, err := r.securityProvider.GetISINBySymbol(symbol)
		if err == nil && isin != "" {
			// Query by ISIN (preferred after migration)
			return r.GetByISIN(isin, limit)
		}
	}

	// Fallback to symbol lookup (for backward compatibility)
	query := `
		SELECT ` + tradesColumns + ` FROM trades
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
		SELECT ` + tradesColumns + ` FROM trades
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

// GetRecentlyBoughtISINs returns ISINs of securities bought in the last N days
// Excludes RESEARCH trades (order_id starting with 'RESEARCH_')
// Returns map[isin]true for efficient lookup
func (r *TradeRepository) GetRecentlyBoughtISINs(days int) (map[string]bool, error) {
	if r.securityProvider == nil {
		return nil, fmt.Errorf("security provider not available for ISIN lookup")
	}

	cutoff := time.Now().AddDate(0, 0, -days).Unix()

	// Step 1: Get distinct symbols from trades (single query)
	symbolQuery := `
		SELECT DISTINCT symbol FROM trades
		WHERE side = 'BUY'
		  AND executed_at >= ?
		  AND order_id IS NOT NULL
		  AND order_id != ''
		  AND order_id NOT LIKE 'RESEARCH_%'
	`

	rows, err := r.ledgerDB.Query(symbolQuery, cutoff)
	if err != nil {
		return nil, fmt.Errorf("failed to get recently bought symbols: %w", err)
	}
	defer rows.Close()

	var symbols []string
	for rows.Next() {
		var symbol string
		if err := rows.Scan(&symbol); err != nil {
			return nil, fmt.Errorf("failed to scan symbol: %w", err)
		}
		symbols = append(symbols, symbol)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating rows: %w", err)
	}

	if len(symbols) == 0 {
		return make(map[string]bool), nil
	}

	// Step 2: Look up ISINs using batch provider method (single query for all symbols)
	symbolToISIN, err := r.securityProvider.BatchGetISINsBySymbols(symbols)
	if err != nil {
		return nil, fmt.Errorf("failed to lookup ISINs: %w", err)
	}

	// Convert to set of ISINs
	isins := make(map[string]bool)
	for _, isin := range symbolToISIN {
		if isin != "" {
			isins[isin] = true
		}
	}

	return isins, nil
}

// GetRecentlySoldISINs returns ISINs of securities sold in the last N days
// Excludes RESEARCH trades (order_id starting with 'RESEARCH_')
// Returns map[isin]true for efficient lookup
func (r *TradeRepository) GetRecentlySoldISINs(days int) (map[string]bool, error) {
	if r.securityProvider == nil {
		return nil, fmt.Errorf("security provider not available for ISIN lookup")
	}

	cutoff := time.Now().AddDate(0, 0, -days).Unix()

	// Step 1: Get distinct symbols from trades (single query)
	symbolQuery := `
		SELECT DISTINCT symbol FROM trades
		WHERE side = 'SELL'
		  AND executed_at >= ?
		  AND (order_id IS NULL OR order_id NOT LIKE 'RESEARCH_%')
	`

	rows, err := r.ledgerDB.Query(symbolQuery, cutoff)
	if err != nil {
		return nil, fmt.Errorf("failed to get recently sold symbols: %w", err)
	}
	defer rows.Close()

	var symbols []string
	for rows.Next() {
		var symbol string
		if err := rows.Scan(&symbol); err != nil {
			return nil, fmt.Errorf("failed to scan symbol: %w", err)
		}
		symbols = append(symbols, symbol)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating rows: %w", err)
	}

	if len(symbols) == 0 {
		return make(map[string]bool), nil
	}

	// Step 2: Look up ISINs using batch provider method (single query for all symbols)
	symbolToISIN, err := r.securityProvider.BatchGetISINsBySymbols(symbols)
	if err != nil {
		return nil, fmt.Errorf("failed to lookup ISINs: %w", err)
	}

	// Convert to set of ISINs
	isins := make(map[string]bool)
	for _, isin := range symbolToISIN {
		if isin != "" {
			isins[isin] = true
		}
	}

	return isins, nil
}

// HasRecentSellOrder checks if there's a recent SELL order for the symbol
// Faithful translation of Python: async def has_recent_sell_order(self, symbol: str, hours: float = 2.0) -> bool
func (r *TradeRepository) HasRecentSellOrder(symbol string, hours float64) (bool, error) {
	cutoff := time.Now().Add(-time.Duration(hours * float64(time.Hour))).Unix()

	query := `
		SELECT 1 FROM trades
		WHERE symbol = ?
		  AND side = 'SELL'
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
		WHERE symbol = ? AND side = 'BUY'
	`

	var firstBuy sql.NullInt64
	err := r.ledgerDB.QueryRow(query, strings.ToUpper(symbol)).Scan(&firstBuy)
	if err != nil {
		return nil, fmt.Errorf("failed to get first buy date: %w", err)
	}

	if !firstBuy.Valid {
		return nil, nil
	}

	dateStr := time.Unix(firstBuy.Int64, 0).UTC().Format("2006-01-02")
	return &dateStr, nil
}

// GetLastBuyDate returns the date of most recent buy for a symbol
// Faithful translation of Python: async def get_last_buy_date(self, symbol: str) -> Optional[str]
func (r *TradeRepository) GetLastBuyDate(symbol string) (*string, error) {
	query := `
		SELECT MAX(executed_at) as last_buy FROM trades
		WHERE symbol = ? AND side = 'BUY'
	`

	var lastBuy sql.NullInt64
	err := r.ledgerDB.QueryRow(query, strings.ToUpper(symbol)).Scan(&lastBuy)
	if err != nil {
		return nil, fmt.Errorf("failed to get last buy date: %w", err)
	}

	if !lastBuy.Valid {
		return nil, nil
	}

	dateStr := time.Unix(lastBuy.Int64, 0).UTC().Format("2006-01-02")
	return &dateStr, nil
}

// GetLastSellDate returns the date of last sell for a symbol
// Faithful translation of Python: async def get_last_sell_date(self, symbol: str) -> Optional[str]
func (r *TradeRepository) GetLastSellDate(symbol string) (*string, error) {
	query := `
		SELECT MAX(executed_at) as last_sell FROM trades
		WHERE symbol = ? AND side = 'SELL'
	`

	var lastSell sql.NullInt64
	err := r.ledgerDB.QueryRow(query, strings.ToUpper(symbol)).Scan(&lastSell)
	if err != nil {
		return nil, fmt.Errorf("failed to get last sell date: %w", err)
	}

	if !lastSell.Valid {
		return nil, nil
	}

	dateStr := time.Unix(lastSell.Int64, 0).UTC().Format("2006-01-02")
	return &dateStr, nil
}

// GetLastTransactionDate returns the date of most recent transaction (BUY or SELL)
// Faithful translation of Python: async def get_last_transaction_date(self, symbol: str) -> Optional[str]
func (r *TradeRepository) GetLastTransactionDate(symbol string) (*string, error) {
	query := `
		SELECT MAX(executed_at) as last_transaction FROM trades
		WHERE symbol = ?
	`

	var lastTransaction sql.NullInt64
	err := r.ledgerDB.QueryRow(query, strings.ToUpper(symbol)).Scan(&lastTransaction)
	if err != nil {
		return nil, fmt.Errorf("failed to get last transaction date: %w", err)
	}

	if !lastTransaction.Valid {
		return nil, nil
	}

	dateStr := time.Unix(lastTransaction.Int64, 0).UTC().Format("2006-01-02")
	return &dateStr, nil
}

// GetTradeDates returns first_buy and last_sell dates for all symbols
// Faithful translation of Python: async def get_trade_dates(self) -> dict[str, dict]
func (r *TradeRepository) GetTradeDates() (map[string]map[string]*string, error) {
	query := `
		SELECT
			symbol,
			MIN(CASE WHEN side = 'BUY' THEN executed_at END) as first_buy,
			MAX(CASE WHEN side = 'SELL' THEN executed_at END) as last_sell
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
		var firstBuy, lastSell sql.NullInt64

		if err := rows.Scan(&symbol, &firstBuy, &lastSell); err != nil {
			return nil, fmt.Errorf("failed to scan trade dates: %w", err)
		}

		dates := make(map[string]*string)
		if firstBuy.Valid {
			dateStr := time.Unix(firstBuy.Int64, 0).UTC().Format("2006-01-02")
			dates["first_bought_at"] = &dateStr
		} else {
			dates["first_bought_at"] = nil
		}
		if lastSell.Valid {
			dateStr := time.Unix(lastSell.Int64, 0).UTC().Format("2006-01-02")
			dates["last_sold_at"] = &dateStr
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
	cutoff := time.Now().AddDate(0, 0, -days).Unix()

	query := `
		SELECT ` + tradesColumns + ` FROM trades
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

	var executedAt sql.NullInt64
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

	t := time.Unix(executedAt.Int64, 0).UTC()
	return &t, nil
}

// GetTradeCountToday counts trades executed today
// Faithful translation of Python: async def get_trade_count_today(self) -> int
func (r *TradeRepository) GetTradeCountToday() (int, error) {
	now := time.Now().UTC()
	startOfDay := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)
	endOfDay := startOfDay.Add(24 * time.Hour)
	startUnix := startOfDay.Unix()
	endUnix := endOfDay.Unix()

	query := `
		SELECT COUNT(*) as cnt
		FROM trades
		WHERE executed_at >= ? AND executed_at < ?
	`

	var count int
	err := r.ledgerDB.QueryRow(query, startUnix, endUnix).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to get trade count today: %w", err)
	}

	return count, nil
}

// GetTradeCountThisWeek counts trades executed in the last 7 days
// Faithful translation of Python: async def get_trade_count_this_week(self) -> int
func (r *TradeRepository) GetTradeCountThisWeek() (int, error) {
	sevenDaysAgo := time.Now().AddDate(0, 0, -7).Unix()

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

// Helper methods

func (r *TradeRepository) scanTrade(row *sql.Row) (Trade, error) {
	var trade Trade
	var executedAt, createdAt sql.NullInt64
	var isin, orderID, currency sql.NullString
	var valueEUR sql.NullFloat64

	// Table schema: id, symbol, isin, side, quantity, price, executed_at, order_id, currency, value_eur, source, mode, created_at
	err := row.Scan(
		&trade.ID,       // 0: id
		&trade.Symbol,   // 1: symbol
		&isin,           // 2: isin
		&trade.Side,     // 3: side
		&trade.Quantity, // 4: quantity
		&trade.Price,    // 5: price
		&executedAt,     // 6: executed_at (Unix timestamp)
		&orderID,        // 7: order_id
		&currency,       // 8: currency
		&valueEUR,       // 9: value_eur
		&trade.Source,   // 10: source
		&trade.Mode,     // 11: mode
		&createdAt,      // 12: created_at (Unix timestamp)
	)

	if err != nil {
		return trade, err
	}

	// Convert Unix timestamps to time.Time
	if executedAt.Valid {
		trade.ExecutedAt = time.Unix(executedAt.Int64, 0).UTC()
	}

	if createdAt.Valid {
		t := time.Unix(createdAt.Int64, 0).UTC()
		trade.CreatedAt = &t
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
	if valueEUR.Valid {
		trade.ValueEUR = &valueEUR.Float64
	}

	// Normalize symbol
	trade.Symbol = strings.ToUpper(strings.TrimSpace(trade.Symbol))

	return trade, nil
}

func (r *TradeRepository) scanTradeFromRows(rows *sql.Rows) (Trade, error) {
	var trade Trade
	var executedAt, createdAt sql.NullInt64
	var isin, orderID, currency sql.NullString
	var valueEUR sql.NullFloat64

	// Table schema: id, symbol, isin, side, quantity, price, executed_at, order_id, currency, value_eur, source, mode, created_at
	err := rows.Scan(
		&trade.ID,       // 0: id
		&trade.Symbol,   // 1: symbol
		&isin,           // 2: isin
		&trade.Side,     // 3: side
		&trade.Quantity, // 4: quantity
		&trade.Price,    // 5: price
		&executedAt,     // 6: executed_at (Unix timestamp)
		&orderID,        // 7: order_id
		&currency,       // 8: currency
		&valueEUR,       // 9: value_eur
		&trade.Source,   // 10: source
		&trade.Mode,     // 11: mode
		&createdAt,      // 12: created_at (Unix timestamp)
	)

	if err != nil {
		return trade, err
	}

	// Convert Unix timestamps to time.Time
	if executedAt.Valid {
		trade.ExecutedAt = time.Unix(executedAt.Int64, 0).UTC()
	}

	if createdAt.Valid {
		t := time.Unix(createdAt.Int64, 0).UTC()
		trade.CreatedAt = &t
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

// ============================================================================
// Pending Retries Management (for failed trades with 7-hour retry interval)
// ============================================================================

// PendingRetry represents a trade that failed and needs to be retried
type PendingRetry struct {
	ID             int64
	Symbol         string
	Side           string
	Quantity       float64
	EstimatedPrice float64
	Currency       string
	Reason         string
	FailureReason  string
	AttemptCount   int
	MaxAttempts    int
	FailedAt       time.Time
	NextRetryAt    time.Time
	Status         string
	CompletedAt    *time.Time
	CreatedAt      time.Time
	UpdatedAt      time.Time
}

// CreatePendingRetry stores a failed trade for retry (7-hour interval, max 3 attempts)
func (r *TradeRepository) CreatePendingRetry(retry PendingRetry) error {
	now := time.Now()

	// Calculate next retry time (7 hours from now)
	nextRetryAt := now.Add(7 * time.Hour)

	query := `
		INSERT INTO pending_retries (
			symbol, side, quantity, estimated_price, currency, reason,
			failure_reason, attempt_count, max_attempts, failed_at, next_retry_at,
			status, created_at, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err := r.ledgerDB.Exec(
		query,
		retry.Symbol,
		retry.Side,
		retry.Quantity,
		retry.EstimatedPrice,
		retry.Currency,
		retry.Reason,
		retry.FailureReason,
		0, // Initial attempt count
		retry.MaxAttempts,
		now.Unix(),
		nextRetryAt.Unix(),
		"pending",
		now.Unix(),
		now.Unix(),
	)

	if err != nil {
		return fmt.Errorf("failed to create pending retry: %w", err)
	}

	return nil
}

// GetPendingRetries retrieves all retries that are due for retry (next_retry_at <= now and status = 'pending')
func (r *TradeRepository) GetPendingRetries() ([]PendingRetry, error) {
	now := time.Now()

	query := `
		SELECT
			id, symbol, side, quantity, estimated_price, currency, reason,
			failure_reason, attempt_count, max_attempts, failed_at, next_retry_at,
			status, completed_at, created_at, updated_at
		FROM pending_retries
		WHERE status = 'pending' AND next_retry_at <= ?
		ORDER BY next_retry_at ASC
	`

	rows, err := r.ledgerDB.Query(query, now.Unix())
	if err != nil {
		return nil, fmt.Errorf("failed to query pending retries: %w", err)
	}
	defer rows.Close()

	var retries []PendingRetry
	for rows.Next() {
		var retry PendingRetry
		var completedAtUnix sql.NullInt64
		var failedAtUnix, nextRetryAtUnix, createdAtUnix, updatedAtUnix int64

		err := rows.Scan(
			&retry.ID,
			&retry.Symbol,
			&retry.Side,
			&retry.Quantity,
			&retry.EstimatedPrice,
			&retry.Currency,
			&retry.Reason,
			&retry.FailureReason,
			&retry.AttemptCount,
			&retry.MaxAttempts,
			&failedAtUnix,
			&nextRetryAtUnix,
			&retry.Status,
			&completedAtUnix,
			&createdAtUnix,
			&updatedAtUnix,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan pending retry: %w", err)
		}

		retry.FailedAt = time.Unix(failedAtUnix, 0)
		retry.NextRetryAt = time.Unix(nextRetryAtUnix, 0)
		retry.CreatedAt = time.Unix(createdAtUnix, 0)
		retry.UpdatedAt = time.Unix(updatedAtUnix, 0)

		if completedAtUnix.Valid {
			completedAt := time.Unix(completedAtUnix.Int64, 0)
			retry.CompletedAt = &completedAt
		}

		retries = append(retries, retry)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating pending retries: %w", err)
	}

	return retries, nil
}

// UpdateRetryStatus updates the status of a pending retry (succeeded, failed, abandoned)
func (r *TradeRepository) UpdateRetryStatus(id int64, status string) error {
	now := time.Now()

	query := `
		UPDATE pending_retries
		SET status = ?, completed_at = ?, updated_at = ?
		WHERE id = ?
	`

	_, err := r.ledgerDB.Exec(query, status, now.Unix(), now.Unix(), id)
	if err != nil {
		return fmt.Errorf("failed to update retry status: %w", err)
	}

	return nil
}

// IncrementRetryAttempt increments the attempt count and calculates next retry time
// Returns error if max attempts reached
func (r *TradeRepository) IncrementRetryAttempt(id int64) error {
	now := time.Now()

	// Get current retry info
	var attemptCount, maxAttempts int
	err := r.ledgerDB.QueryRow(
		"SELECT attempt_count, max_attempts FROM pending_retries WHERE id = ?",
		id,
	).Scan(&attemptCount, &maxAttempts)

	if err != nil {
		return fmt.Errorf("failed to get retry info: %w", err)
	}

	newAttemptCount := attemptCount + 1

	// Check if max attempts reached
	if newAttemptCount >= maxAttempts {
		// Mark as failed (max attempts exhausted)
		return r.UpdateRetryStatus(id, "failed")
	}

	// Calculate next retry time (7 hours from now)
	nextRetryAt := now.Add(7 * time.Hour)

	query := `
		UPDATE pending_retries
		SET attempt_count = ?, next_retry_at = ?, updated_at = ?
		WHERE id = ?
	`

	_, err = r.ledgerDB.Exec(query, newAttemptCount, nextRetryAt.Unix(), now.Unix(), id)
	if err != nil {
		return fmt.Errorf("failed to increment retry attempt: %w", err)
	}

	return nil
}
