// Package handlers provides HTTP handlers for system snapshot operations.
package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/market_regime"
	"github.com/aristath/sentinel/internal/modules/adaptation"
	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/pkg/formulas"
	"github.com/rs/zerolog"
)

// Handler handles snapshot HTTP requests
type Handler struct {
	positionRepo       *portfolio.PositionRepository
	historyDB          universe.HistoryDBInterface
	ledgerDB           *sql.DB
	regimePersistence  *market_regime.RegimePersistence
	cashManager        domain.CashManager
	adaptiveService    *adaptation.AdaptiveMarketService
	marketHoursService *market_hours.MarketHoursService
	log                zerolog.Logger
}

// NewHandler creates a new snapshot handler
func NewHandler(
	positionRepo *portfolio.PositionRepository,
	historyDB universe.HistoryDBInterface,
	ledgerDB *sql.DB,
	regimePersistence *market_regime.RegimePersistence,
	cashManager domain.CashManager,
	adaptiveService *adaptation.AdaptiveMarketService,
	marketHoursService *market_hours.MarketHoursService,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		positionRepo:       positionRepo,
		historyDB:          historyDB,
		ledgerDB:           ledgerDB,
		regimePersistence:  regimePersistence,
		cashManager:        cashManager,
		adaptiveService:    adaptiveService,
		marketHoursService: marketHoursService,
		log:                log.With().Str("handler", "snapshots").Logger(),
	}
}

// HandleGetComplete handles GET /api/snapshots/complete
func (h *Handler) HandleGetComplete(w http.ResponseWriter, r *http.Request) {
	// Get positions and metrics
	positions, _ := h.positionRepo.GetWithSecurityInfo()
	totalValue := 0.0
	for _, pos := range positions {
		totalValue += pos.MarketValueEUR
	}

	// Get market context
	var smoothedScore float64
	var discreteRegime string
	if h.regimePersistence != nil {
		entry, err := h.regimePersistence.GetLatestEntry()
		if err == nil && entry != nil {
			smoothedScore = float64(entry.SmoothedScore)
			discreteRegime = entry.DiscreteRegime
		} else {
			smoothedScore = 0.0
			discreteRegime = "neutral"
		}
	} else {
		smoothedScore = 0.0
		discreteRegime = "neutral"
	}

	isOpen := false
	status, err := h.marketHoursService.GetMarketStatus("XETRA", time.Now())
	if err == nil {
		isOpen = status.Open
	}

	weights := h.adaptiveService.CalculateAdaptiveWeights(smoothedScore)

	// Get risk metrics
	portfolioRisk := h.calculatePortfolioRisk()

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"portfolio": map[string]interface{}{
				"total_value":    totalValue,
				"cash_balances":  h.getCashBalances(),
				"position_count": len(positions),
			},
			"market_context": map[string]interface{}{
				"regime_score":     smoothedScore,
				"discrete_regime":  discreteRegime,
				"market_open":      isOpen,
				"adaptive_weights": weights,
			},
			"risk": portfolioRisk,
		},
		"metadata": map[string]interface{}{
			"timestamp":   time.Now().Format(time.RFC3339),
			"snapshot_id": time.Now().Unix(),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPortfolioState handles GET /api/snapshots/portfolio-state
func (h *Handler) HandleGetPortfolioState(w http.ResponseWriter, r *http.Request) {
	// Get all positions
	positions, err := h.positionRepo.GetWithSecurityInfo()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get positions")
		http.Error(w, "Failed to get positions", http.StatusInternalServerError)
		return
	}

	// Calculate total metrics
	totalValue := 0.0
	totalCostBasis := 0.0

	positionsData := []map[string]interface{}{}
	for _, pos := range positions {
		totalValue += pos.MarketValueEUR
		totalCostBasis += pos.AvgPrice * pos.Quantity

		positionsData = append(positionsData, map[string]interface{}{
			"symbol":           pos.Symbol,
			"quantity":         pos.Quantity,
			"avg_price":        pos.AvgPrice,
			"current_price":    pos.CurrentPrice,
			"market_value_eur": pos.MarketValueEUR,
			"name":             pos.StockName,
			"geography":        pos.Geography,
			"industry":         pos.Industry,
		})
	}

	// Get cash balances
	cashBalances := h.getCashBalances()

	// Get position scores from portfolio DB
	// Note: We don't have a GetAllScores method on the repository, but scores aren't
	// critical for the snapshot, so we can skip them or return empty array
	scores := []map[string]interface{}{}

	totalUnrealizedPnL := totalValue - totalCostBasis

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"positions":     positionsData,
			"scores":        scores,
			"cash_balances": cashBalances,
			"metrics": map[string]interface{}{
				"total_value_eur":  totalValue,
				"total_cost_basis": totalCostBasis,
				"unrealized_pnl":   totalUnrealizedPnL,
				"position_count":   len(positions),
			},
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetMarketContext handles GET /api/snapshots/market-context
func (h *Handler) HandleGetMarketContext(w http.ResponseWriter, r *http.Request) {
	// Get latest regime score
	var rawScore, smoothedScore float64
	var discreteRegime string

	if h.regimePersistence != nil {
		entry, err := h.regimePersistence.GetLatestEntry()
		if err != nil {
			h.log.Warn().Err(err).Msg("Failed to get regime score")
			rawScore, smoothedScore, discreteRegime = 0.0, 0.0, "neutral"
		} else if entry == nil {
			rawScore, smoothedScore, discreteRegime = 0.0, 0.0, "neutral"
		} else {
			rawScore = float64(entry.RawScore)
			smoothedScore = float64(entry.SmoothedScore)
			discreteRegime = entry.DiscreteRegime
		}
	} else {
		rawScore, smoothedScore, discreteRegime = 0.0, 0.0, "neutral"
	}

	// Get adaptive weights
	weights := h.adaptiveService.CalculateAdaptiveWeights(smoothedScore)
	blend := h.adaptiveService.CalculateAdaptiveBlend(smoothedScore)
	qualityGates := h.adaptiveService.CalculateAdaptiveQualityGates(smoothedScore)

	// Get market hours status (check XETRA as primary market)
	isOpen := false
	status, err := h.marketHoursService.GetMarketStatus("XETRA", time.Now())
	if err == nil {
		isOpen = status.Open
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"regime": map[string]interface{}{
				"raw_score":       rawScore,
				"smoothed_score":  smoothedScore,
				"discrete_regime": discreteRegime,
			},
			"adaptive_weights": weights,
			"market_hours": map[string]interface{}{
				"is_open": isOpen,
			},
			"adaptive_blend": blend,
			"quality_gates": map[string]interface{}{
				"stability": qualityGates.GetStability(),
				"long_term": qualityGates.GetLongTerm(),
			},
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPendingActions handles GET /api/snapshots/pending-actions
func (h *Handler) HandleGetPendingActions(w http.ResponseWriter, r *http.Request) {
	// Get pending retry trades
	pendingRetries := []map[string]interface{}{}
	rows, err := h.ledgerDB.Query(`
		SELECT id, symbol, side, quantity, attempts, last_attempt
		FROM retry_queue
		WHERE status = 'pending'
		ORDER BY last_attempt DESC
		LIMIT 50
	`)

	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var id, attempts int64
			var symbol, side, lastAttempt string
			var quantity float64

			if err := rows.Scan(&id, &symbol, &side, &quantity, &attempts, &lastAttempt); err == nil {
				pendingRetries = append(pendingRetries, map[string]interface{}{
					"id":           id,
					"symbol":       symbol,
					"side":         side,
					"quantity":     quantity,
					"attempts":     attempts,
					"last_attempt": lastAttempt,
				})
			}
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"pending_retries": pendingRetries,
			"retry_count":     len(pendingRetries),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetHistoricalSummary handles GET /api/snapshots/historical-summary
func (h *Handler) HandleGetHistoricalSummary(w http.ResponseWriter, r *http.Request) {
	// Get recent trades (last 30 days)
	rows, err := h.ledgerDB.Query(`
		SELECT id, symbol, side, quantity, price, executed_at
		FROM trades
		WHERE executed_at >= datetime('now', '-30 days')
		ORDER BY executed_at DESC
		LIMIT 100
	`)

	trades := []map[string]interface{}{}
	totalBuys := 0.0
	totalSells := 0.0

	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var id int64
			var symbol, side, executedAt string
			var quantity, price float64

			if err := rows.Scan(&id, &symbol, &side, &quantity, &price, &executedAt); err == nil {
				value := quantity * price
				if side == "BUY" {
					totalBuys += value
				} else {
					totalSells += value
				}

				trades = append(trades, map[string]interface{}{
					"id":          id,
					"symbol":      symbol,
					"side":        side,
					"quantity":    quantity,
					"price":       price,
					"executed_at": executedAt,
				})
			}
		}
	}

	// Get recent dividends
	dividendRows, err := h.ledgerDB.Query(`
		SELECT id, symbol, amount_eur, payment_date
		FROM dividends
		WHERE payment_date >= datetime('now', '-30 days')
		ORDER BY payment_date DESC
		LIMIT 100
	`)

	dividends := []map[string]interface{}{}
	totalDividends := 0.0

	if err == nil {
		defer dividendRows.Close()
		for dividendRows.Next() {
			var id int64
			var symbol, paymentDate string
			var amountEUR float64

			if err := dividendRows.Scan(&id, &symbol, &amountEUR, &paymentDate); err == nil {
				totalDividends += amountEUR
				dividends = append(dividends, map[string]interface{}{
					"id":           id,
					"symbol":       symbol,
					"amount_eur":   amountEUR,
					"payment_date": paymentDate,
				})
			}
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"recent_trades": map[string]interface{}{
				"trades":      trades,
				"count":       len(trades),
				"total_buys":  totalBuys,
				"total_sells": totalSells,
			},
			"recent_dividends": map[string]interface{}{
				"dividends":        dividends,
				"count":            len(dividends),
				"total_amount_eur": totalDividends,
			},
			"period": "last_30_days",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetRiskSnapshot handles GET /api/snapshots/risk-snapshot
func (h *Handler) HandleGetRiskSnapshot(w http.ResponseWriter, r *http.Request) {
	// Get portfolio risk metrics (reuse same logic as risk module)
	portfolioRisk := h.calculatePortfolioRisk()

	// Get concentration metrics
	concentration := h.calculateConcentration()

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"portfolio_risk": portfolioRisk,
			"concentration":  concentration,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// getCashBalances gets cash balances from cash manager
func (h *Handler) getCashBalances() map[string]interface{} {
	balances := make(map[string]interface{})

	defer func() {
		if r := recover(); r != nil {
			h.log.Warn().Interface("panic", r).Msg("Panic getting cash balances")
		}
	}()

	if h.cashManager != nil {
		// Get all balances
		allBalances, err := h.cashManager.GetAllCashBalances()
		if err == nil {
			for currency, balance := range allBalances {
				balances[currency] = balance
			}
		}
	}

	return balances
}

// calculatePortfolioRisk calculates portfolio risk metrics
func (h *Handler) calculatePortfolioRisk() map[string]interface{} {
	positions, err := h.positionRepo.GetAll()
	if err != nil || len(positions) == 0 {
		return map[string]interface{}{
			"var_95":           0.0,
			"cvar_95":          0.0,
			"volatility":       0.0,
			"sharpe_ratio":     0.0,
			"sortino_ratio":    0.0,
			"max_drawdown":     0.0,
			"current_drawdown": 0.0,
		}
	}

	// Calculate portfolio value and weights
	portfolioValue := 0.0
	weights := make(map[string]float64)
	for _, pos := range positions {
		portfolioValue += pos.MarketValueEUR
		weights[pos.ISIN] = pos.MarketValueEUR
	}

	// Normalize weights
	for isin := range weights {
		weights[isin] /= portfolioValue
	}

	// Get historical returns
	returns := make(map[string][]float64)
	for _, pos := range positions {
		prices, err := h.historyDB.GetDailyPrices(pos.ISIN, 252)
		if err != nil || len(prices) < 2 {
			continue
		}

		priceValues := make([]float64, len(prices))
		for i, p := range prices {
			priceValues[i] = p.Close
		}

		returns[pos.ISIN] = formulas.CalculateReturns(priceValues)
	}

	// Calculate weighted portfolio returns
	minLen := -1
	for _, rets := range returns {
		if minLen == -1 || len(rets) < minLen {
			minLen = len(rets)
		}
	}

	portfolioReturns := make([]float64, minLen)
	for i := 0; i < minLen; i++ {
		portfolioReturn := 0.0
		for isin, rets := range returns {
			if i < len(rets) {
				portfolioReturn += weights[isin] * rets[i]
			}
		}
		portfolioReturns[i] = portfolioReturn
	}

	// Calculate metrics
	volatility := formulas.AnnualizedVolatility(portfolioReturns)
	avgReturn := formulas.CalculateAnnualReturn(portfolioReturns)
	riskFreeRate := 0.02
	sharpe := 0.0
	if volatility > 0 {
		sharpe = (avgReturn - riskFreeRate) / volatility
	}
	sortino := formulas.CalculateSortinoRatio(portfolioReturns, riskFreeRate, 0.0, 252)

	// Calculate CVaR
	cvar95 := formulas.CalculatePortfolioCVaR(weights, returns, 0.95) * portfolioValue

	return map[string]interface{}{
		"var_95":           0.0, // Would need VaR calculation
		"cvar_95":          -cvar95,
		"volatility":       volatility,
		"sharpe_ratio":     sharpe,
		"sortino_ratio":    sortino,
		"max_drawdown":     0.0, // Would need drawdown calculation
		"current_drawdown": 0.0,
	}
}

// calculateConcentration calculates concentration metrics
func (h *Handler) calculateConcentration() map[string]interface{} {
	positions, err := h.positionRepo.GetAll()
	if err != nil || len(positions) == 0 {
		return map[string]interface{}{
			"herfindahl_index": 0.0,
			"top_5_weight":     0.0,
			"top_10_weight":    0.0,
		}
	}

	// Calculate total value
	totalValue := 0.0
	for _, pos := range positions {
		totalValue += pos.MarketValueEUR
	}

	// Calculate weights
	weights := make([]float64, len(positions))
	for i, pos := range positions {
		weights[i] = pos.MarketValueEUR / totalValue
	}

	// Sort weights descending
	for i := 0; i < len(weights); i++ {
		for j := i + 1; j < len(weights); j++ {
			if weights[i] < weights[j] {
				weights[i], weights[j] = weights[j], weights[i]
			}
		}
	}

	// Calculate Herfindahl index
	herfindahl := 0.0
	for _, w := range weights {
		herfindahl += w * w
	}

	// Calculate top N weights
	top5 := 0.0
	top10 := 0.0
	for i, w := range weights {
		if i < 5 {
			top5 += w
		}
		if i < 10 {
			top10 += w
		}
	}

	return map[string]interface{}{
		"herfindahl_index": herfindahl,
		"top_5_weight":     top5,
		"top_10_weight":    top10,
	}
}

// writeJSON writes a JSON response
func (h *Handler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}
