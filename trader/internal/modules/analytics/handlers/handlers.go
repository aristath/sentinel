package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/aristath/sentinel/internal/modules/analytics"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// Handler provides HTTP handlers for analytics endpoints
type Handler struct {
	factorTracker   *analytics.FactorExposureTracker
	portfolioService *portfolio.Service
	positionRepo    interface{} // TODO: Replace with actual position repository type
	scoreRepo       interface{} // TODO: Replace with actual score repository type
	portfolioDB     *sql.DB
	log             zerolog.Logger
}

// NewHandler creates a new analytics handler
func NewHandler(
	factorTracker *analytics.FactorExposureTracker,
	portfolioService *portfolio.Service,
	positionRepo interface{},
	scoreRepo interface{},
	portfolioDB *sql.DB,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		factorTracker:    factorTracker,
		portfolioService: portfolioService,
		positionRepo:     positionRepo,
		scoreRepo:        scoreRepo,
		portfolioDB:      portfolioDB,
		log:              log.With().Str("handler", "analytics").Logger(),
	}
}

// HandleGetFactorExposures handles GET /api/analytics/factor-exposures
func (h *Handler) HandleGetFactorExposures(w http.ResponseWriter, r *http.Request) {
	// Get positions (simplified - would use positionRepo in production)
	positions, err := h.getPositionsForFactorExposure()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get positions for factor exposure")
		http.Error(w, "Failed to get portfolio positions", http.StatusInternalServerError)
		return
	}

	// Calculate portfolio weights
	weights, totalValue := h.calculatePortfolioWeights(positions)
	if totalValue == 0 {
		// Empty portfolio
		response := map[string]interface{}{
			"value":    0.0,
			"quality":  0.0,
			"momentum": 0.0,
			"size":     0.0,
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
		return
	}

	// Get security metrics from scores table
	securityMetrics, err := h.getSecurityMetricsForFactorExposure(positions)
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get security metrics, using defaults")
		// Continue with default metrics
		securityMetrics = make(map[string]analytics.SecurityMetrics)
	}

	// Calculate factor exposures
	exposures, err := h.factorTracker.CalculateFactorExposures(weights, securityMetrics)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to calculate factor exposures")
		http.Error(w, "Failed to calculate factor exposures", http.StatusInternalServerError)
		return
	}

	// Build response
	response := map[string]interface{}{
		"value":    exposures["value"].Exposure,
		"quality":  exposures["quality"].Exposure,
		"momentum": exposures["momentum"].Exposure,
		"size":     exposures["size"].Exposure,
		"contributions": map[string]map[string]float64{
			"value":    exposures["value"].Contributions,
			"quality":  exposures["quality"].Contributions,
			"momentum": exposures["momentum"].Contributions,
			"size":     exposures["size"].Contributions,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(response); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode factor exposures response")
		http.Error(w, "Internal server error", http.StatusInternalServerError)
	}
}

// HandleGetFactorExposureHistory handles GET /api/analytics/factor-exposures/history
func (h *Handler) HandleGetFactorExposureHistory(w http.ResponseWriter, r *http.Request) {
	// Query factor_exposures table
	rows, err := h.portfolioDB.Query(`
		SELECT calculated_at, factor_name, exposure, contribution, portfolio_value
		FROM factor_exposures
		ORDER BY calculated_at DESC
		LIMIT 100
	`)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to query factor exposure history")
		http.Error(w, "Failed to retrieve factor exposure history", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	type FactorExposureRecord struct {
		CalculatedAt   int64                  `json:"calculated_at"`
		FactorName     string                 `json:"factor_name"`
		Exposure       float64                `json:"exposure"`
		Contribution   map[string]interface{} `json:"contribution"`
		PortfolioValue float64                `json:"portfolio_value"`
	}

	history := make([]FactorExposureRecord, 0)
	for rows.Next() {
		var record FactorExposureRecord
		var contributionJSON string
		if err := rows.Scan(&record.CalculatedAt, &record.FactorName, &record.Exposure, &contributionJSON, &record.PortfolioValue); err != nil {
			h.log.Warn().Err(err).Msg("Failed to scan factor exposure record")
			continue
		}

		// Parse contribution JSON
		if contributionJSON != "" {
			if err := json.Unmarshal([]byte(contributionJSON), &record.Contribution); err != nil {
				h.log.Warn().Err(err).Msg("Failed to parse contribution JSON")
			}
		}

		history = append(history, record)
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(history); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode factor exposure history response")
		http.Error(w, "Internal server error", http.StatusInternalServerError)
	}
}

// Helper functions

type positionForFactorExposure struct {
	Symbol   string
	ISIN     string
	ValueEUR float64
}

func (h *Handler) getPositionsForFactorExposure() ([]positionForFactorExposure, error) {
	rows, err := h.portfolioDB.Query(`
		SELECT symbol, isin, market_value_eur
		FROM positions
		WHERE market_value_eur > 0
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	positions := make([]positionForFactorExposure, 0)
	for rows.Next() {
		var pos positionForFactorExposure
		if err := rows.Scan(&pos.Symbol, &pos.ISIN, &pos.ValueEUR); err != nil {
			continue
		}
		positions = append(positions, pos)
	}

	return positions, nil
}

func (h *Handler) calculatePortfolioWeights(positions []positionForFactorExposure) (map[string]float64, float64) {
	totalValue := 0.0
	for _, pos := range positions {
		totalValue += pos.ValueEUR
	}

	if totalValue == 0 {
		return make(map[string]float64), 0.0
	}

	weights := make(map[string]float64)
	for _, pos := range positions {
		weights[pos.Symbol] = pos.ValueEUR / totalValue
	}

	return weights, totalValue
}

func (h *Handler) getSecurityMetricsForFactorExposure(positions []positionForFactorExposure) (map[string]analytics.SecurityMetrics, error) {
	metrics := make(map[string]analytics.SecurityMetrics)

	// Get ISINs from positions
	isins := make([]string, 0, len(positions))
	for _, pos := range positions {
		if pos.ISIN != "" {
			isins = append(isins, pos.ISIN)
		}
	}

	if len(isins) == 0 {
		return metrics, nil
	}

	// Query scores table for metrics
	// Note: Scores table doesn't have all metrics (PE, PB, etc.), so we use available data
	placeholders := make([]string, len(isins))
	args := make([]interface{}, len(isins))
	for i, isin := range isins {
		placeholders[i] = "?"
		args[i] = isin
	}

	query := `
		SELECT isin, volatility, cagr_score, sharpe_score, drawdown_score,
		       financial_strength_score, dividend_bonus
		FROM scores
		WHERE isin IN (` + strings.Join(placeholders, ",") + `)
	`

	rows, err := h.portfolioDB.Query(query, args...)
	if err != nil {
		return metrics, err
	}
	defer rows.Close()

	// Map ISINs to symbols
	isinToSymbol := make(map[string]string)
	for _, pos := range positions {
		if pos.ISIN != "" {
			isinToSymbol[pos.ISIN] = pos.Symbol
		}
	}

	for rows.Next() {
		var isin string
		var volatility, cagrScore, sharpeScore, drawdownScore, financialStrength, dividendBonus sql.NullFloat64

		if err := rows.Scan(&isin, &volatility, &cagrScore, &sharpeScore, &drawdownScore, &financialStrength, &dividendBonus); err != nil {
			continue
		}

		symbol, hasSymbol := isinToSymbol[isin]
		if !hasSymbol {
			continue
		}

		// Map available metrics to SecurityMetrics
		// Note: Some metrics (PE, PB, ROE, etc.) are not in scores table
		// In production, these would come from a fundamentals table or external API
		metric := analytics.SecurityMetrics{
			PE:            0.0, // Not available in scores
			PB:            0.0, // Not available in scores
			DividendYield: 0.0,
			ProfitMargin:  0.0, // Not available in scores
			ROE:           0.0, // Not available in scores
			DebtEquity:    0.0, // Not available in scores
			Return12M:     0.0, // Could derive from CAGR
			Return6M:      0.0, // Not available
			MarketCap:     0.0, // Not available
		}

		// Use available metrics
		if dividendBonus.Valid {
			metric.DividendYield = dividendBonus.Float64 / 100.0 // Convert percentage
		}
		if cagrScore.Valid {
			metric.Return12M = cagrScore.Float64 // Approximate 12M return with CAGR
		}
		if financialStrength.Valid {
			// Use financial strength as proxy for quality metrics
			metric.ROE = financialStrength.Float64 * 0.1 // Rough approximation
			metric.ProfitMargin = financialStrength.Float64 * 0.05
		}

		metrics[symbol] = metric
	}

	return metrics, nil
}

