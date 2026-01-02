package optimization

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"sync"
	"time"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/clients/yahoo"
	"github.com/aristath/arduino-trader/internal/modules/dividends"
	"github.com/rs/zerolog"
)

// OptimizationCache stores the last optimization result.
type OptimizationCache struct {
	mu          sync.RWMutex
	lastResult  *Result
	lastUpdated time.Time
}

// Handler handles HTTP requests for the optimization module.
type Handler struct {
	service         *OptimizerService
	db              *sql.DB
	yahooClient     *yahoo.Client
	tradernetClient *tradernet.Client
	dividendRepo    *dividends.DividendRepository
	cache           *OptimizationCache
	log             zerolog.Logger
}

// NewHandler creates a new optimization handler.
func NewHandler(
	service *OptimizerService,
	db *sql.DB,
	yahooClient *yahoo.Client,
	tradernetClient *tradernet.Client,
	dividendRepo *dividends.DividendRepository,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		service:         service,
		db:              db,
		yahooClient:     yahooClient,
		tradernetClient: tradernetClient,
		dividendRepo:    dividendRepo,
		cache: &OptimizationCache{
			lastResult:  nil,
			lastUpdated: time.Time{},
		},
		log: log.With().Str("component", "optimizer_handler").Logger(),
	}
}

// HandleGetStatus handles GET /api/optimizer - returns optimizer status and last run.
func (h *Handler) HandleGetStatus(w http.ResponseWriter, r *http.Request) {
	h.cache.mu.RLock()
	defer h.cache.mu.RUnlock()

	// Fetch settings from database
	settings, err := h.getSettings()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get settings")
		h.writeError(w, http.StatusInternalServerError, "Failed to get settings")
		return
	}

	// Calculate min trade amount from transaction costs
	minTradeAmount := h.calculateMinTradeAmount(DefaultTransactionCostFixed, DefaultTransactionCostPct)

	response := map[string]interface{}{
		"settings": map[string]interface{}{
			"optimizer_blend":         settings.Blend,
			"optimizer_target_return": settings.TargetReturn,
			"min_cash_reserve":        settings.MinCashReserve,
			"min_trade_amount":        math.Round(minTradeAmount*100) / 100,
		},
		"last_run": nil,
		"status":   "ready",
	}

	if h.cache.lastResult != nil {
		resultDict := h.optimizationResultToDict(h.cache.lastResult, 0) // Portfolio value not available in cache
		response["last_run"] = resultDict
		response["last_run_time"] = h.cache.lastUpdated.Format(time.RFC3339)
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleRun handles POST /api/optimizer/run - runs optimization and returns results.
func (h *Handler) HandleRun(w http.ResponseWriter, r *http.Request) {
	h.log.Info().Msg("Running portfolio optimization")

	// 1. Fetch settings
	settings, err := h.getSettings()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get settings")
		h.writeError(w, http.StatusInternalServerError, "Failed to get settings")
		return
	}

	// 2. Fetch securities
	securities, err := h.getSecurities()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get securities")
		h.writeError(w, http.StatusInternalServerError, "Failed to get securities")
		return
	}

	if len(securities) == 0 {
		h.writeError(w, http.StatusBadRequest, "No securities in universe")
		return
	}

	// 3. Fetch positions
	positions, err := h.getPositions()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get positions")
		h.writeError(w, http.StatusInternalServerError, "Failed to get positions")
		return
	}

	// 4. Fetch current prices (stub - would call Yahoo Finance or other price source)
	currentPrices, err := h.getCurrentPrices(securities)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get current prices")
		h.writeError(w, http.StatusInternalServerError, "Failed to get current prices")
		return
	}

	// 5. Calculate portfolio value
	portfolioValue := h.calculatePortfolioValue(positions, currentPrices)

	// 6. Get cash balance (stub - would call Tradernet API)
	cashBalance, err := h.getCashBalance()
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get cash balance, using 0")
		cashBalance = 0.0
	}

	portfolioValue += cashBalance

	// 7. Get allocation targets
	countryTargets, err := h.getCountryTargets()
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get country targets")
		countryTargets = make(map[string]float64)
	}

	industryTargets, err := h.getIndustryTargets()
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get industry targets")
		industryTargets = make(map[string]float64)
	}

	// 8. Get dividend bonuses
	dividendBonuses, err := h.getDividendBonuses()
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get dividend bonuses")
		dividendBonuses = make(map[string]float64)
	}

	// 9. Build portfolio state
	state := PortfolioState{
		Securities:      securities,
		Positions:       positions,
		PortfolioValue:  portfolioValue,
		CurrentPrices:   currentPrices,
		CashBalance:     cashBalance,
		CountryTargets:  countryTargets,
		IndustryTargets: industryTargets,
		DividendBonuses: dividendBonuses,
	}

	// 10. Run optimization
	result, err := h.service.Optimize(state, settings)
	if err != nil {
		h.log.Error().Err(err).Msg("Optimization failed")
		h.writeError(w, http.StatusInternalServerError, fmt.Sprintf("Optimization failed: %v", err))
		return
	}

	// 11. Update cache
	h.cache.mu.Lock()
	h.cache.lastResult = result
	h.cache.lastUpdated = time.Now()
	h.cache.mu.Unlock()

	// 12. Format result
	resultDict := h.optimizationResultToDict(result, portfolioValue)

	response := map[string]interface{}{
		"success":   result.Success,
		"result":    resultDict,
		"timestamp": h.cache.lastUpdated.Format(time.RFC3339),
	}

	h.writeJSON(w, http.StatusOK, response)
}

// Helper methods for data fetching

func (h *Handler) getSettings() (Settings, error) {
	// Query settings from database
	query := `
		SELECT
			COALESCE((SELECT value FROM settings WHERE key = 'optimizer_blend'), '0.5') as blend,
			COALESCE((SELECT value FROM settings WHERE key = 'optimizer_target_return'), '0.11') as target_return,
			COALESCE((SELECT value FROM settings WHERE key = 'min_cash_reserve'), '500.0') as min_cash_reserve
	`

	var blendStr, targetReturnStr, minCashReserveStr string
	err := h.db.QueryRow(query).Scan(&blendStr, &targetReturnStr, &minCashReserveStr)
	if err != nil {
		return Settings{}, fmt.Errorf("failed to query settings: %w", err)
	}

	blend := 0.5
	fmt.Sscanf(blendStr, "%f", &blend)

	targetReturn := OptimizerTargetReturn
	fmt.Sscanf(targetReturnStr, "%f", &targetReturn)

	minCashReserve := DefaultMinCashReserve
	fmt.Sscanf(minCashReserveStr, "%f", &minCashReserve)

	return Settings{
		Blend:              blend,
		TargetReturn:       targetReturn,
		MinCashReserve:     minCashReserve,
		MinTradeAmount:     0.0, // Calculated separately
		TransactionCostPct: DefaultTransactionCostPct,
		MaxConcentration:   MaxConcentration,
	}, nil
}

func (h *Handler) getSecurities() ([]Security, error) {
	query := `
		SELECT
			symbol,
			COALESCE(country, 'OTHER') as country,
			COALESCE(industry, 'OTHER') as industry,
			COALESCE(min_portfolio_target, 0.0) as min_portfolio_target,
			COALESCE(max_portfolio_target, 0.0) as max_portfolio_target,
			COALESCE(allow_buy, 1) as allow_buy,
			COALESCE(allow_sell, 1) as allow_sell,
			COALESCE(min_lot, 0.0) as min_lot,
			COALESCE(priority_multiplier, 1.0) as priority_multiplier,
			COALESCE(target_price_eur, 0.0) as target_price_eur
		FROM securities
		WHERE active = 1
	`

	rows, err := h.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query securities: %w", err)
	}
	defer rows.Close()

	securities := make([]Security, 0)
	for rows.Next() {
		var sec Security
		var allowBuyInt, allowSellInt int

		err := rows.Scan(
			&sec.Symbol,
			&sec.Country,
			&sec.Industry,
			&sec.MinPortfolioTarget,
			&sec.MaxPortfolioTarget,
			&allowBuyInt,
			&allowSellInt,
			&sec.MinLot,
			&sec.PriorityMultiplier,
			&sec.TargetPriceEUR,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan security: %w", err)
		}

		sec.AllowBuy = allowBuyInt == 1
		sec.AllowSell = allowSellInt == 1

		securities = append(securities, sec)
	}

	return securities, rows.Err()
}

func (h *Handler) getPositions() (map[string]Position, error) {
	query := `
		SELECT
			symbol,
			COALESCE(quantity, 0.0) as quantity,
			COALESCE(market_value_eur, 0.0) as value_eur
		FROM positions
		WHERE quantity > 0
	`

	rows, err := h.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query positions: %w", err)
	}
	defer rows.Close()

	positions := make(map[string]Position)
	for rows.Next() {
		var pos Position
		err := rows.Scan(&pos.Symbol, &pos.Quantity, &pos.ValueEUR)
		if err != nil {
			return nil, fmt.Errorf("failed to scan position: %w", err)
		}
		positions[pos.Symbol] = pos
	}

	return positions, rows.Err()
}

func (h *Handler) getCurrentPrices(securities []Security) (map[string]float64, error) {
	// Fetch current prices from Yahoo Finance with fallback to price_history table
	prices := make(map[string]float64)

	for _, sec := range securities {
		// Try to get current price from Yahoo Finance
		price, err := h.yahooClient.GetCurrentPrice(sec.Symbol, nil, 3)
		if err != nil {
			h.log.Debug().
				Str("symbol", sec.Symbol).
				Err(err).
				Msg("Failed to get price from Yahoo Finance, falling back to price_history")

			// Fallback: use last known price from price_history table
			query := `
				SELECT close
				FROM price_history
				WHERE symbol = ?
				ORDER BY date DESC
				LIMIT 1
			`

			var fallbackPrice float64
			err := h.db.QueryRow(query, sec.Symbol).Scan(&fallbackPrice)
			if err != nil && err != sql.ErrNoRows {
				h.log.Warn().
					Str("symbol", sec.Symbol).
					Err(err).
					Msg("Failed to get price from both Yahoo and price_history")
				continue
			}
			if err == nil {
				prices[sec.Symbol] = fallbackPrice
			}
		} else if price != nil {
			prices[sec.Symbol] = *price
		}
	}

	return prices, nil
}

func (h *Handler) getCashBalance() (float64, error) {
	// Get cash balances from Tradernet API
	balances, err := h.tradernetClient.GetCashBalances()
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get cash balances from Tradernet, returning 0")
		return 0.0, nil // Gracefully return 0 on error
	}

	var totalEUR float64
	for _, balance := range balances {
		if balance.Currency == "EUR" {
			totalEUR += balance.Amount
		} else {
			// For non-EUR currencies, we would need exchange rate conversion
			// For now, only include EUR balances
			h.log.Debug().
				Str("currency", balance.Currency).
				Float64("amount", balance.Amount).
				Msg("Skipping non-EUR balance (exchange rate conversion not implemented)")
		}
	}

	return totalEUR, nil
}

func (h *Handler) getDividendBonuses() (map[string]float64, error) {
	// Get pending dividend bonuses from dividend repository
	bonuses, err := h.dividendRepo.GetPendingBonuses()
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get dividend bonuses")
		return make(map[string]float64), nil // Return empty map on error
	}

	return bonuses, nil
}

func (h *Handler) getCountryTargets() (map[string]float64, error) {
	query := `
		SELECT country, target_allocation
		FROM allocation_targets
		WHERE type = 'country'
	`

	rows, err := h.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query country targets: %w", err)
	}
	defer rows.Close()

	targets := make(map[string]float64)
	for rows.Next() {
		var country string
		var target float64
		if err := rows.Scan(&country, &target); err != nil {
			return nil, fmt.Errorf("failed to scan country target: %w", err)
		}
		targets[country] = target
	}

	return targets, rows.Err()
}

func (h *Handler) getIndustryTargets() (map[string]float64, error) {
	query := `
		SELECT industry, target_allocation
		FROM allocation_targets
		WHERE type = 'industry'
	`

	rows, err := h.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query industry targets: %w", err)
	}
	defer rows.Close()

	targets := make(map[string]float64)
	for rows.Next() {
		var industry string
		var target float64
		if err := rows.Scan(&industry, &target); err != nil {
			return nil, fmt.Errorf("failed to scan industry target: %w", err)
		}
		targets[industry] = target
	}

	return targets, rows.Err()
}

func (h *Handler) calculatePortfolioValue(positions map[string]Position, prices map[string]float64) float64 {
	total := 0.0
	for symbol, pos := range positions {
		if price, ok := prices[symbol]; ok {
			total += pos.Quantity * price
		} else if pos.ValueEUR > 0 {
			// Fallback to stored market value if price not available
			total += pos.ValueEUR
		}
	}
	return total
}

func (h *Handler) calculateMinTradeAmount(fixedCost, pctCost float64) float64 {
	// Trade where cost = 1% of value
	return fixedCost / (0.01 - pctCost)
}

// Result formatting

func (h *Handler) optimizationResultToDict(result *Result, portfolioValue float64) map[string]interface{} {
	// Get top 5 weight changes
	topChanges := make([]map[string]interface{}, 0)
	maxChanges := 5
	if len(result.WeightChanges) < maxChanges {
		maxChanges = len(result.WeightChanges)
	}

	for i := 0; i < maxChanges; i++ {
		wc := result.WeightChanges[i]
		changeEUR := wc.Change * portfolioValue
		direction := "sell"
		if wc.Change > 0 {
			direction = "buy"
		}

		topChanges = append(topChanges, map[string]interface{}{
			"symbol":      wc.Symbol,
			"current_pct": math.Round(wc.CurrentWeight*1000) / 10,
			"target_pct":  math.Round(wc.TargetWeight*1000) / 10,
			"change_pct":  math.Round(wc.Change*1000) / 10,
			"change_eur":  math.Round(changeEUR),
			"direction":   direction,
		})
	}

	// Determine next action
	var nextAction *string
	if len(topChanges) > 0 {
		top := topChanges[0]
		action := "Buy"
		if top["direction"] == "sell" {
			action = "Sell"
		}
		changeEUR := top["change_eur"].(float64)
		actionStr := fmt.Sprintf("%s %s ~€%.0f", action, top["symbol"], math.Abs(changeEUR))
		nextAction = &actionStr
	}

	// Format achieved return
	var achievedReturnPct *float64
	if result.AchievedExpectedReturn != nil {
		pct := *result.AchievedExpectedReturn * 100
		roundedPct := math.Round(pct*10) / 10
		achievedReturnPct = &roundedPct
	}

	return map[string]interface{}{
		"success":                result.Success,
		"error":                  result.Error,
		"target_return_pct":      math.Round(result.TargetReturn*1000) / 10,
		"achieved_return_pct":    achievedReturnPct,
		"blend_used":             result.BlendUsed,
		"fallback_used":          result.FallbackUsed,
		"total_stocks_optimized": len(result.TargetWeights),
		"top_adjustments":        topChanges,
		"next_action":            nextAction,
		"high_correlations":      result.HighCorrelations,
		"constraints":            result.ConstraintsSummary,
	}
}

// HTTP helpers

func (h *Handler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}

func (h *Handler) writeError(w http.ResponseWriter, status int, message string) {
	h.writeJSON(w, status, map[string]interface{}{
		"error": message,
	})
}
