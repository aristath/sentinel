// Package handlers provides HTTP handlers for risk metrics operations.
package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/pkg/formulas"
	"github.com/rs/zerolog"
)

// Handler handles risk metrics HTTP requests
type Handler struct {
	historyDB    *universe.HistoryDB
	positionRepo portfolio.PositionRepositoryInterface
	log          zerolog.Logger
}

// NewHandler creates a new risk metrics handler
func NewHandler(
	historyDB *universe.HistoryDB,
	positionRepo portfolio.PositionRepositoryInterface,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		historyDB:    historyDB,
		positionRepo: positionRepo,
		log:          log.With().Str("handler", "risk").Logger(),
	}
}

// HandleGetPortfolioVaR handles GET /api/risk/portfolio/var
func (h *Handler) HandleGetPortfolioVaR(w http.ResponseWriter, r *http.Request) {
	// Get all positions
	positions, err := h.positionRepo.GetAll()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get positions")
		http.Error(w, "Failed to get positions", http.StatusInternalServerError)
		return
	}

	if len(positions) == 0 {
		response := map[string]interface{}{
			"data": map[string]interface{}{
				"var_95":          0.0,
				"var_99":          0.0,
				"portfolio_value": 0.0,
				"var_pct_95":      0.0,
				"var_pct_99":      0.0,
			},
			"metadata": map[string]interface{}{
				"timestamp": time.Now().Format(time.RFC3339),
			},
		}
		h.writeJSON(w, http.StatusOK, response)
		return
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

	// Get historical returns for each position
	returns := make(map[string][]float64)
	for _, pos := range positions {
		prices, err := h.historyDB.GetDailyPrices(pos.ISIN, 252)
		if err != nil {
			h.log.Warn().Err(err).Str("isin", pos.ISIN).Msg("Failed to get prices for position")
			continue
		}

		if len(prices) < 2 {
			continue
		}

		priceValues := make([]float64, len(prices))
		for i, p := range prices {
			priceValues[i] = p.Close
		}

		returns[pos.ISIN] = formulas.CalculateReturns(priceValues)
	}

	// Calculate portfolio returns (weighted combination)
	portfolioReturns := h.calculatePortfolioReturns(returns, weights)

	// Calculate VaR at 95% and 99% confidence
	var95 := h.calculateVaR(portfolioReturns, 0.95) * portfolioValue
	var99 := h.calculateVaR(portfolioReturns, 0.99) * portfolioValue

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"var_95":          -var95, // Negative because VaR is a loss
			"var_99":          -var99,
			"portfolio_value": portfolioValue,
			"var_pct_95":      -var95 / portfolioValue * 100,
			"var_pct_99":      -var99 / portfolioValue * 100,
			"method":          "historical",
			"period":          "252d",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPortfolioCVaR handles GET /api/risk/portfolio/cvar
func (h *Handler) HandleGetPortfolioCVaR(w http.ResponseWriter, r *http.Request) {
	// Get all positions
	positions, err := h.positionRepo.GetAll()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get positions")
		http.Error(w, "Failed to get positions", http.StatusInternalServerError)
		return
	}

	if len(positions) == 0 {
		response := map[string]interface{}{
			"data": map[string]interface{}{
				"cvar_95":       0.0,
				"cvar_99":       0.0,
				"contributions": []interface{}{},
			},
			"metadata": map[string]interface{}{
				"timestamp": time.Now().Format(time.RFC3339),
			},
		}
		h.writeJSON(w, http.StatusOK, response)
		return
	}

	// Calculate portfolio value and weights
	portfolioValue := 0.0
	weights := make(map[string]float64)
	positionMap := make(map[string]portfolio.Position)
	for _, pos := range positions {
		portfolioValue += pos.MarketValueEUR
		weights[pos.ISIN] = pos.MarketValueEUR
		positionMap[pos.ISIN] = pos
	}

	// Normalize weights
	for isin := range weights {
		weights[isin] /= portfolioValue
	}

	// Get historical returns for each position
	returns := make(map[string][]float64)
	for _, pos := range positions {
		prices, err := h.historyDB.GetDailyPrices(pos.ISIN, 252)
		if err != nil {
			h.log.Warn().Err(err).Str("isin", pos.ISIN).Msg("Failed to get prices for position")
			continue
		}

		if len(prices) < 2 {
			continue
		}

		priceValues := make([]float64, len(prices))
		for i, p := range prices {
			priceValues[i] = p.Close
		}

		returns[pos.ISIN] = formulas.CalculateReturns(priceValues)
	}

	// Calculate portfolio CVaR
	cvar95 := formulas.CalculatePortfolioCVaR(weights, returns, 0.95) * portfolioValue
	cvar99 := formulas.CalculatePortfolioCVaR(weights, returns, 0.99) * portfolioValue

	// Calculate contributions by position
	contributions := []map[string]interface{}{}
	for isin, weight := range weights {
		if rets, ok := returns[isin]; ok && len(rets) > 0 {
			secCVaR95 := formulas.CalculateCVaR(rets, 0.95)
			contribution := weight * secCVaR95 * portfolioValue

			pos := positionMap[isin]
			contributions = append(contributions, map[string]interface{}{
				"isin":              isin,
				"symbol":            pos.Symbol,
				"contribution":      -contribution, // Negative for loss
				"contribution_pct":  -contribution / cvar95 * 100,
				"weight":            weight,
			})
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"cvar_95":       -cvar95, // Negative because CVaR is a loss
			"cvar_99":       -cvar99,
			"contributions": contributions,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPortfolioVolatility handles GET /api/risk/portfolio/volatility
func (h *Handler) HandleGetPortfolioVolatility(w http.ResponseWriter, r *http.Request) {
	portfolioReturns, err := h.getPortfolioReturns()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get portfolio returns")
		http.Error(w, "Failed to calculate portfolio volatility", http.StatusInternalServerError)
		return
	}

	volatility := formulas.AnnualizedVolatility(portfolioReturns)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"annualized_volatility": volatility,
			"volatility":            volatility,
			"volatility_pct":        volatility * 100,
			"period":                "252d",
			"annualized":            true,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}
	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPortfolioSharpe handles GET /api/risk/portfolio/sharpe
func (h *Handler) HandleGetPortfolioSharpe(w http.ResponseWriter, r *http.Request) {
	portfolioReturns, err := h.getPortfolioReturns()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get portfolio returns")
		http.Error(w, "Failed to calculate portfolio Sharpe", http.StatusInternalServerError)
		return
	}

	riskFreeRate := 0.02 // 2% default
	volatility := formulas.AnnualizedVolatility(portfolioReturns)
	avgReturn := formulas.CalculateAnnualReturn(portfolioReturns)
	sharpe := 0.0
	if volatility > 0 {
		sharpe = (avgReturn - riskFreeRate) / volatility
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sharpe_ratio":   sharpe,
			"return":         avgReturn,
			"volatility":     volatility,
			"risk_free_rate": riskFreeRate,
			"period":         "1y",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}
	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPortfolioSortino handles GET /api/risk/portfolio/sortino
func (h *Handler) HandleGetPortfolioSortino(w http.ResponseWriter, r *http.Request) {
	portfolioReturns, err := h.getPortfolioReturns()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get portfolio returns")
		http.Error(w, "Failed to calculate portfolio Sortino", http.StatusInternalServerError)
		return
	}

	riskFreeRate := 0.02 // 2% default
	sortino := formulas.CalculateSortinoRatio(portfolioReturns, riskFreeRate, 0.0, 252)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"sortino_ratio":  sortino,
			"risk_free_rate": riskFreeRate,
			"period":         "1y",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}
	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPortfolioMaxDrawdown handles GET /api/risk/portfolio/max-drawdown
func (h *Handler) HandleGetPortfolioMaxDrawdown(w http.ResponseWriter, r *http.Request) {
	// Get all positions
	positions, err := h.positionRepo.GetAll()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get positions")
		http.Error(w, "Failed to get positions", http.StatusInternalServerError)
		return
	}

	if len(positions) == 0 {
		response := map[string]interface{}{
			"data": map[string]interface{}{
				"max_drawdown":     0.0,
				"max_drawdown_pct": 0.0,
				"current_drawdown": 0.0,
				"days_in_drawdown": 0,
			},
			"metadata": map[string]interface{}{
				"timestamp": time.Now().Format(time.RFC3339),
			},
		}
		h.writeJSON(w, http.StatusOK, response)
		return
	}

	// Calculate portfolio values over time
	// Get historical prices for all positions and combine into portfolio value series
	portfolioValues := h.calculatePortfolioValueSeries(positions, 1000)

	if len(portfolioValues) == 0 {
		response := map[string]interface{}{
			"data": map[string]interface{}{
				"max_drawdown":     0.0,
				"max_drawdown_pct": 0.0,
				"current_drawdown": 0.0,
				"days_in_drawdown": 0,
			},
			"metadata": map[string]interface{}{
				"timestamp": time.Now().Format(time.RFC3339),
			},
		}
		h.writeJSON(w, http.StatusOK, response)
		return
	}

	metrics := formulas.CalculateDrawdownMetrics(portfolioValues)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"max_drawdown":     metrics.MaxDrawdown,
			"max_drawdown_pct": metrics.MaxDrawdown * 100,
			"current_drawdown": metrics.CurrentDrawdown,
			"days_in_drawdown": metrics.DaysInDrawdown,
			"peak_value":       metrics.PeakValue,
			"current_value":    metrics.CurrentValue,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}
	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetSecurityVolatility handles GET /api/risk/securities/{isin}/volatility
func (h *Handler) HandleGetSecurityVolatility(w http.ResponseWriter, r *http.Request, isin string) {
	prices, err := h.historyDB.GetDailyPrices(isin, 252)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get prices")
		http.Error(w, "Failed to get prices", http.StatusInternalServerError)
		return
	}

	priceValues := make([]float64, len(prices))
	for i, p := range prices {
		priceValues[i] = p.Close
	}

	volatility := formulas.CalculateVolatility(priceValues)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"isin":                  isin,
			"annualized_volatility": volatility,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}
	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetSecuritySharpe handles GET /api/risk/securities/{isin}/sharpe
func (h *Handler) HandleGetSecuritySharpe(w http.ResponseWriter, r *http.Request, isin string) {
	prices, err := h.historyDB.GetDailyPrices(isin, 252)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get prices")
		http.Error(w, "Failed to get prices", http.StatusInternalServerError)
		return
	}

	priceValues := make([]float64, len(prices))
	for i, p := range prices {
		priceValues[i] = p.Close
	}

	riskFreeRate := 0.02 // 2% default
	sharpe := formulas.CalculateSharpeFromPrices(priceValues, riskFreeRate)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"isin":         isin,
			"sharpe_ratio": sharpe,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}
	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetSecuritySortino handles GET /api/risk/securities/{isin}/sortino
func (h *Handler) HandleGetSecuritySortino(w http.ResponseWriter, r *http.Request, isin string) {
	prices, err := h.historyDB.GetDailyPrices(isin, 252)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get prices")
		http.Error(w, "Failed to get prices", http.StatusInternalServerError)
		return
	}

	priceValues := make([]float64, len(prices))
	for i, p := range prices {
		priceValues[i] = p.Close
	}

	returns := formulas.CalculateReturns(priceValues)
	sortino := formulas.CalculateSortinoRatio(returns, 0.02, 0.0, 252)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"isin":          isin,
			"sortino_ratio": sortino,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}
	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetSecurityMaxDrawdown handles GET /api/risk/securities/{isin}/max-drawdown
func (h *Handler) HandleGetSecurityMaxDrawdown(w http.ResponseWriter, r *http.Request, isin string) {
	prices, err := h.historyDB.GetDailyPrices(isin, 1000)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get prices")
		http.Error(w, "Failed to get prices", http.StatusInternalServerError)
		return
	}

	priceValues := make([]float64, len(prices))
	for i, p := range prices {
		priceValues[i] = p.Close
	}

	metrics := formulas.CalculateDrawdownMetrics(priceValues)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"isin":    isin,
			"metrics": metrics,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}
	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetSecurityBeta handles GET /api/risk/securities/{isin}/beta
func (h *Handler) HandleGetSecurityBeta(w http.ResponseWriter, r *http.Request, isin string) {
	response := map[string]interface{}{
		"data": map[string]interface{}{
			"isin": isin,
			"beta": 1.0,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}
	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetKellySizes handles GET /api/risk/kelly-sizes
func (h *Handler) HandleGetKellySizes(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"data": map[string]interface{}{
			"kelly_sizes": []map[string]interface{}{},
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}
	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetKellySize handles GET /api/risk/kelly-sizes/{isin}
func (h *Handler) HandleGetKellySize(w http.ResponseWriter, r *http.Request, isin string) {
	response := map[string]interface{}{
		"data": map[string]interface{}{
			"isin":                 isin,
			"kelly_fraction":       0.0,
			"constrained_fraction": 0.0,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}
	h.writeJSON(w, http.StatusOK, response)
}

// calculateVaR calculates Value at Risk from historical returns
func (h *Handler) calculateVaR(returns []float64, confidence float64) float64 {
	if len(returns) == 0 {
		return 0.0
	}

	// Sort returns in ascending order
	sorted := make([]float64, len(returns))
	copy(sorted, returns)

	// Simple bubble sort for small arrays
	for i := 0; i < len(sorted); i++ {
		for j := i + 1; j < len(sorted); j++ {
			if sorted[i] > sorted[j] {
				sorted[i], sorted[j] = sorted[j], sorted[i]
			}
		}
	}

	// VaR is the loss at the confidence percentile
	// For 95% confidence, we want the 5th percentile (worst 5%)
	percentile := 1.0 - confidence
	index := int(float64(len(sorted)) * percentile)
	if index >= len(sorted) {
		index = len(sorted) - 1
	}

	return sorted[index]
}

// calculatePortfolioReturns calculates weighted portfolio returns
func (h *Handler) calculatePortfolioReturns(returns map[string][]float64, weights map[string]float64) []float64 {
	if len(returns) == 0 {
		return []float64{}
	}

	// Find minimum length across all return series
	minLen := -1
	for _, rets := range returns {
		if minLen == -1 || len(rets) < minLen {
			minLen = len(rets)
		}
	}

	if minLen <= 0 {
		return []float64{}
	}

	// Calculate weighted portfolio returns for each period
	portfolioReturns := make([]float64, minLen)
	for i := 0; i < minLen; i++ {
		portfolioReturn := 0.0
		for isin, rets := range returns {
			if i < len(rets) {
				weight := weights[isin]
				portfolioReturn += weight * rets[i]
			}
		}
		portfolioReturns[i] = portfolioReturn
	}

	return portfolioReturns
}

// getPortfolioReturns is a helper that gets positions and calculates portfolio returns
func (h *Handler) getPortfolioReturns() ([]float64, error) {
	// Get all positions
	positions, err := h.positionRepo.GetAll()
	if err != nil {
		return nil, fmt.Errorf("failed to get positions: %w", err)
	}

	if len(positions) == 0 {
		return []float64{}, nil
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

	// Get historical returns for each position
	returns := make(map[string][]float64)
	for _, pos := range positions {
		prices, err := h.historyDB.GetDailyPrices(pos.ISIN, 252)
		if err != nil {
			h.log.Warn().Err(err).Str("isin", pos.ISIN).Msg("Failed to get prices for position")
			continue
		}

		if len(prices) < 2 {
			continue
		}

		priceValues := make([]float64, len(prices))
		for i, p := range prices {
			priceValues[i] = p.Close
		}

		returns[pos.ISIN] = formulas.CalculateReturns(priceValues)
	}

	return h.calculatePortfolioReturns(returns, weights), nil
}

// calculatePortfolioValueSeries calculates historical portfolio values
func (h *Handler) calculatePortfolioValueSeries(positions []portfolio.Position, limit int) []float64 {
	if len(positions) == 0 {
		return []float64{}
	}

	// Get historical prices for all positions
	pricesByISIN := make(map[string][]universe.DailyPrice)
	minLen := -1

	for _, pos := range positions {
		prices, err := h.historyDB.GetDailyPrices(pos.ISIN, limit)
		if err != nil {
			h.log.Warn().Err(err).Str("isin", pos.ISIN).Msg("Failed to get prices for position")
			continue
		}

		if len(prices) == 0 {
			continue
		}

		pricesByISIN[pos.ISIN] = prices
		if minLen == -1 || len(prices) < minLen {
			minLen = len(prices)
		}
	}

	if minLen <= 0 {
		return []float64{}
	}

	// Calculate portfolio value for each date
	portfolioValues := make([]float64, minLen)
	for i := 0; i < minLen; i++ {
		totalValue := 0.0
		for _, pos := range positions {
			if prices, ok := pricesByISIN[pos.ISIN]; ok && i < len(prices) {
				// Use current quantity with historical price
				totalValue += pos.Quantity * prices[i].Close
			}
		}
		portfolioValues[i] = totalValue
	}

	return portfolioValues
}

// writeJSON writes a JSON response
func (h *Handler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}
