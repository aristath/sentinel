// Package handlers provides HTTP handlers for ledger operations.
package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/rs/zerolog"
)

// Handler handles ledger HTTP requests
type Handler struct {
	ledgerDB *sql.DB
	log      zerolog.Logger
}

// NewHandler creates a new ledger handler
func NewHandler(
	ledgerDB *sql.DB,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		ledgerDB: ledgerDB,
		log:      log.With().Str("handler", "ledger").Logger(),
	}
}

// HandleGetTrades handles GET /api/ledger/trades
func (h *Handler) HandleGetTrades(w http.ResponseWriter, r *http.Request) {
	// Parse query parameters
	limit := 100 // default
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit
		}
	}

	symbol := r.URL.Query().Get("symbol")
	side := r.URL.Query().Get("side")

	// Build query
	query := `SELECT id, symbol, isin, side, quantity, price, executed_at, order_id,
	                 currency, currency_rate, value_eur, source, created_at
	          FROM trades WHERE 1=1`
	args := []interface{}{}

	if symbol != "" {
		query += " AND symbol = ?"
		args = append(args, symbol)
	}
	if side != "" {
		query += " AND side = ?"
		args = append(args, side)
	}

	query += " ORDER BY executed_at DESC LIMIT ?"
	args = append(args, limit)

	rows, err := h.ledgerDB.Query(query, args...)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to query trades")
		http.Error(w, "Failed to query trades", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	trades := make([]map[string]interface{}, 0)
	for rows.Next() {
		var id int64
		var symbol, isin, side, executedAt, orderID, source, createdAt string
		var quantity, price, valueEur float64
		var currency sql.NullString
		var currencyRate sql.NullFloat64

		err := rows.Scan(&id, &symbol, &isin, &side, &quantity, &price, &executedAt,
			&orderID, &currency, &currencyRate, &valueEur, &source, &createdAt)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to scan trade row")
			continue
		}

		trade := map[string]interface{}{
			"id":          id,
			"symbol":      symbol,
			"isin":        isin,
			"side":        side,
			"quantity":    quantity,
			"price":       price,
			"executed_at": executedAt,
			"order_id":    orderID,
			"value_eur":   valueEur,
			"source":      source,
			"created_at":  createdAt,
		}

		if currency.Valid {
			trade["currency"] = currency.String
		}
		if currencyRate.Valid {
			trade["currency_rate"] = currencyRate.Float64
		}

		trades = append(trades, trade)
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"trades": trades,
			"count":  len(trades),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetTradeByID handles GET /api/ledger/trades/{id}
func (h *Handler) HandleGetTradeByID(w http.ResponseWriter, r *http.Request, idStr string) {
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		http.Error(w, "Invalid trade ID", http.StatusBadRequest)
		return
	}

	query := `SELECT id, symbol, isin, side, quantity, price, executed_at, order_id,
	                 currency, currency_rate, value_eur, source, created_at
	          FROM trades WHERE id = ?`

	var symbol, isin, side, executedAt, orderID, source, createdAt string
	var quantity, price, valueEur float64
	var currency sql.NullString
	var currencyRate sql.NullFloat64

	err = h.ledgerDB.QueryRow(query, id).Scan(&id, &symbol, &isin, &side, &quantity,
		&price, &executedAt, &orderID, &currency, &currencyRate, &valueEur, &source, &createdAt)
	if err == sql.ErrNoRows {
		http.Error(w, "Trade not found", http.StatusNotFound)
		return
	}
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to query trade")
		http.Error(w, "Failed to query trade", http.StatusInternalServerError)
		return
	}

	trade := map[string]interface{}{
		"id":          id,
		"symbol":      symbol,
		"isin":        isin,
		"side":        side,
		"quantity":    quantity,
		"price":       price,
		"executed_at": executedAt,
		"order_id":    orderID,
		"value_eur":   valueEur,
		"source":      source,
		"created_at":  createdAt,
	}

	if currency.Valid {
		trade["currency"] = currency.String
	}
	if currencyRate.Valid {
		trade["currency_rate"] = currencyRate.Float64
	}

	response := map[string]interface{}{
		"data": trade,
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetTradesSummary handles GET /api/ledger/trades/summary
func (h *Handler) HandleGetTradesSummary(w http.ResponseWriter, r *http.Request) {
	query := `
		SELECT
			COUNT(*) as total_trades,
			SUM(CASE WHEN side = 'BUY' THEN 1 ELSE 0 END) as buy_count,
			SUM(CASE WHEN side = 'SELL' THEN 1 ELSE 0 END) as sell_count,
			SUM(CASE WHEN side = 'BUY' THEN value_eur ELSE 0 END) as total_bought_eur,
			SUM(CASE WHEN side = 'SELL' THEN value_eur ELSE 0 END) as total_sold_eur
		FROM trades
	`

	var totalTrades, buyCount, sellCount int64
	var totalBoughtEUR, totalSoldEUR float64

	err := h.ledgerDB.QueryRow(query).Scan(&totalTrades, &buyCount, &sellCount,
		&totalBoughtEUR, &totalSoldEUR)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to query trades summary")
		http.Error(w, "Failed to query trades summary", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"total_trades":     totalTrades,
			"buy_count":        buyCount,
			"sell_count":       sellCount,
			"total_bought_eur": totalBoughtEUR,
			"total_sold_eur":   totalSoldEUR,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetAllCashFlows handles GET /api/ledger/cash-flows/all
func (h *Handler) HandleGetAllCashFlows(w http.ResponseWriter, r *http.Request) {
	h.getCashFlowsByType(w, r, "")
}

// HandleGetDeposits handles GET /api/ledger/cash-flows/deposits
func (h *Handler) HandleGetDeposits(w http.ResponseWriter, r *http.Request) {
	h.getCashFlowsByType(w, r, "DEPOSIT")
}

// HandleGetWithdrawals handles GET /api/ledger/cash-flows/withdrawals
func (h *Handler) HandleGetWithdrawals(w http.ResponseWriter, r *http.Request) {
	h.getCashFlowsByType(w, r, "WITHDRAWAL")
}

// HandleGetFees handles GET /api/ledger/cash-flows/fees
func (h *Handler) HandleGetFees(w http.ResponseWriter, r *http.Request) {
	h.getCashFlowsByType(w, r, "FEE")
}

// getCashFlowsByType is a helper function to get cash flows by type
func (h *Handler) getCashFlowsByType(w http.ResponseWriter, r *http.Request, flowType string) {
	limit := 100 // default
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit
		}
	}

	query := `SELECT id, transaction_id, transaction_type, date, amount, currency,
	                 amount_eur, status, description, created_at
	          FROM cash_flows WHERE 1=1`
	args := []interface{}{}

	if flowType != "" {
		query += " AND transaction_type = ?"
		args = append(args, flowType)
	}

	query += " ORDER BY date DESC LIMIT ?"
	args = append(args, limit)

	rows, err := h.ledgerDB.Query(query, args...)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to query cash flows")
		http.Error(w, "Failed to query cash flows", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	cashFlows := make([]map[string]interface{}, 0)
	for rows.Next() {
		var id int64
		var transactionID, transactionType, date, currency, createdAt string
		var amount, amountEUR float64
		var status, description sql.NullString

		err := rows.Scan(&id, &transactionID, &transactionType, &date, &amount,
			&currency, &amountEUR, &status, &description, &createdAt)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to scan cash flow row")
			continue
		}

		cf := map[string]interface{}{
			"id":               id,
			"transaction_id":   transactionID,
			"transaction_type": transactionType,
			"date":             date,
			"amount":           amount,
			"currency":         currency,
			"amount_eur":       amountEUR,
			"created_at":       createdAt,
		}

		if status.Valid {
			cf["status"] = status.String
		}
		if description.Valid {
			cf["description"] = description.String
		}

		cashFlows = append(cashFlows, cf)
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"cash_flows": cashFlows,
			"count":      len(cashFlows),
			"type":       flowType,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetCashFlowsSummary handles GET /api/ledger/cash-flows/summary
func (h *Handler) HandleGetCashFlowsSummary(w http.ResponseWriter, r *http.Request) {
	query := `
		SELECT
			COUNT(*) as total_count,
			SUM(CASE WHEN transaction_type = 'DEPOSIT' THEN amount_eur ELSE 0 END) as total_deposits,
			SUM(CASE WHEN transaction_type = 'WITHDRAWAL' THEN amount_eur ELSE 0 END) as total_withdrawals,
			SUM(CASE WHEN transaction_type = 'DIVIDEND' THEN amount_eur ELSE 0 END) as total_dividends,
			SUM(CASE WHEN transaction_type = 'FEE' THEN amount_eur ELSE 0 END) as total_fees
		FROM cash_flows
	`

	var totalCount int64
	var totalDeposits, totalWithdrawals, totalDividends, totalFees float64

	err := h.ledgerDB.QueryRow(query).Scan(&totalCount, &totalDeposits,
		&totalWithdrawals, &totalDividends, &totalFees)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to query cash flows summary")
		http.Error(w, "Failed to query cash flows summary", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"total_count":       totalCount,
			"total_deposits":    totalDeposits,
			"total_withdrawals": totalWithdrawals,
			"total_dividends":   totalDividends,
			"total_fees":        totalFees,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetDividendHistory handles GET /api/ledger/dividends/history
func (h *Handler) HandleGetDividendHistory(w http.ResponseWriter, r *http.Request) {
	limit := 100 // default
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit
		}
	}

	query := `SELECT id, symbol, amount, currency, amount_eur, payment_date,
	                 reinvested, reinvested_at, reinvested_quantity, created_at
	          FROM dividend_history
	          ORDER BY payment_date DESC LIMIT ?`

	rows, err := h.ledgerDB.Query(query, limit)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to query dividend history")
		http.Error(w, "Failed to query dividend history", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	dividends := make([]map[string]interface{}, 0)
	for rows.Next() {
		var id int64
		var symbol, currency, paymentDate, createdAt string
		var amount, amountEUR float64
		var reinvested int
		var reinvestedAt sql.NullString
		var reinvestedQuantity sql.NullInt64

		err := rows.Scan(&id, &symbol, &amount, &currency, &amountEUR, &paymentDate,
			&reinvested, &reinvestedAt, &reinvestedQuantity, &createdAt)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to scan dividend row")
			continue
		}

		div := map[string]interface{}{
			"id":           id,
			"symbol":       symbol,
			"amount":       amount,
			"currency":     currency,
			"amount_eur":   amountEUR,
			"payment_date": paymentDate,
			"reinvested":   reinvested == 1,
			"created_at":   createdAt,
		}

		if reinvestedAt.Valid {
			div["reinvested_at"] = reinvestedAt.String
		}
		if reinvestedQuantity.Valid {
			div["reinvested_quantity"] = reinvestedQuantity.Int64
		}

		dividends = append(dividends, div)
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"dividends": dividends,
			"count":     len(dividends),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetDividendReinvestmentStats handles GET /api/ledger/dividends/reinvestment-stats
func (h *Handler) HandleGetDividendReinvestmentStats(w http.ResponseWriter, r *http.Request) {
	query := `
		SELECT
			COUNT(*) as total_dividends,
			SUM(CASE WHEN reinvested = 1 THEN 1 ELSE 0 END) as reinvested_count,
			SUM(CASE WHEN reinvested = 0 THEN 1 ELSE 0 END) as pending_count,
			SUM(CASE WHEN reinvested = 1 THEN amount_eur ELSE 0 END) as total_reinvested_eur,
			SUM(CASE WHEN reinvested = 0 THEN amount_eur ELSE 0 END) as pending_reinvestment_eur
		FROM dividend_history
	`

	var totalDividends, reinvestedCount, pendingCount int64
	var totalReinvestedEUR, pendingReinvestmentEUR float64

	err := h.ledgerDB.QueryRow(query).Scan(&totalDividends, &reinvestedCount,
		&pendingCount, &totalReinvestedEUR, &pendingReinvestmentEUR)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to query dividend reinvestment stats")
		http.Error(w, "Failed to query dividend reinvestment stats", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"total_dividends":         totalDividends,
			"reinvested_count":        reinvestedCount,
			"pending_count":           pendingCount,
			"total_reinvested_eur":    totalReinvestedEUR,
			"pending_reinvestment_eur": pendingReinvestmentEUR,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPendingReinvestments handles GET /api/ledger/dividends/pending-reinvestments
func (h *Handler) HandleGetPendingReinvestments(w http.ResponseWriter, r *http.Request) {
	query := `SELECT id, symbol, amount, currency, amount_eur, payment_date, created_at
	          FROM dividend_history
	          WHERE reinvested = 0
	          ORDER BY payment_date DESC`

	rows, err := h.ledgerDB.Query(query)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to query pending reinvestments")
		http.Error(w, "Failed to query pending reinvestments", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	pending := make([]map[string]interface{}, 0)
	for rows.Next() {
		var id int64
		var symbol, currency, paymentDate, createdAt string
		var amount, amountEUR float64

		err := rows.Scan(&id, &symbol, &amount, &currency, &amountEUR, &paymentDate, &createdAt)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to scan pending reinvestment row")
			continue
		}

		pending = append(pending, map[string]interface{}{
			"id":           id,
			"symbol":       symbol,
			"amount":       amount,
			"currency":     currency,
			"amount_eur":   amountEUR,
			"payment_date": paymentDate,
			"created_at":   createdAt,
		})
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"pending_reinvestments": pending,
			"count":                 len(pending),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetDRIPTracking handles GET /api/ledger/drip-tracking
func (h *Handler) HandleGetDRIPTracking(w http.ResponseWriter, r *http.Request) {
	query := `
		SELECT
			symbol,
			COUNT(*) as total_dividends,
			SUM(CASE WHEN reinvested = 1 THEN 1 ELSE 0 END) as reinvested_count,
			SUM(amount_eur) as total_amount_eur,
			MAX(payment_date) as last_dividend_date
		FROM dividend_history
		GROUP BY symbol
		ORDER BY total_amount_eur DESC
	`

	rows, err := h.ledgerDB.Query(query)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to query DRIP tracking")
		http.Error(w, "Failed to query DRIP tracking", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	tracking := make([]map[string]interface{}, 0)
	for rows.Next() {
		var symbol, lastDividendDate string
		var totalDividends, reinvestedCount int64
		var totalAmountEUR float64

		err := rows.Scan(&symbol, &totalDividends, &reinvestedCount, &totalAmountEUR, &lastDividendDate)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to scan DRIP tracking row")
			continue
		}

		reinvestmentRate := 0.0
		if totalDividends > 0 {
			reinvestmentRate = float64(reinvestedCount) / float64(totalDividends) * 100
		}

		tracking = append(tracking, map[string]interface{}{
			"symbol":             symbol,
			"total_dividends":    totalDividends,
			"reinvested_count":   reinvestedCount,
			"total_amount_eur":   totalAmountEUR,
			"last_dividend_date": lastDividendDate,
			"reinvestment_rate":  reinvestmentRate,
		})
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"drip_tracking": tracking,
			"count":         len(tracking),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// writeJSON writes a JSON response
func (h *Handler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}
