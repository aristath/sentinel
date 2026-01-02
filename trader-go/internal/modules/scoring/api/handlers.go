package api

import (
	"encoding/json"
	"net/http"

	"github.com/aristath/arduino-trader/internal/modules/scoring/domain"
	"github.com/aristath/arduino-trader/internal/modules/scoring/scorers"
	"github.com/aristath/arduino-trader/pkg/formulas"
	"github.com/rs/zerolog"
)

// Handlers provides HTTP handlers for scoring module
type Handlers struct {
	scorer *scorers.SecurityScorer
	log    zerolog.Logger
}

// NewHandlers creates a new scoring handlers instance
func NewHandlers(log zerolog.Logger) *Handlers {
	return &Handlers{
		scorer: scorers.NewSecurityScorer(),
		log:    log.With().Str("module", "scoring_handlers").Logger(),
	}
}

// ScoreRequest represents a request to score a security
type ScoreRequest struct {
	CurrentRatio          *float64                `json:"current_ratio,omitempty"`
	FiveYearAvgDivYield   *float64                `json:"five_year_avg_div_yield,omitempty"`
	MaxDrawdown           *float64                `json:"max_drawdown,omitempty"`
	SortinoRatio          *float64                `json:"sortino_ratio,omitempty"`
	UpsidePct             *float64                `json:"upside_pct,omitempty"`
	PERatio               *float64                `json:"pe_ratio,omitempty"`
	ForwardPE             *float64                `json:"forward_pe,omitempty"`
	DividendYield         *float64                `json:"dividend_yield,omitempty"`
	AnalystRecommendation *float64                `json:"analyst_recommendation,omitempty"`
	ProfitMargin          *float64                `json:"profit_margin,omitempty"`
	PayoutRatio           *float64                `json:"payout_ratio,omitempty"`
	DebtToEquity          *float64                `json:"debt_to_equity,omitempty"`
	Symbol                string                  `json:"symbol"`
	DailyPrices           []float64               `json:"daily_prices"`
	MonthlyPrices         []formulas.MonthlyPrice `json:"monthly_prices"`
	MarketAvgPE           float64                 `json:"market_avg_pe,omitempty"`
	TargetAnnualReturn    float64                 `json:"target_annual_return,omitempty"`
}

// ScoreResponse represents the response from scoring
type ScoreResponse struct {
	Score *domain.CalculatedSecurityScore `json:"score,omitempty"`
	Error *string                         `json:"error,omitempty"`
}

// HandleScoreSecurity handles POST /api/scoring/score
// Calculates the complete security score
func (h *Handlers) HandleScoreSecurity(w http.ResponseWriter, r *http.Request) {
	var req ScoreRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode score request")
		h.writeError(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate required fields
	if req.Symbol == "" {
		h.writeError(w, "Symbol is required", http.StatusBadRequest)
		return
	}

	if len(req.DailyPrices) == 0 {
		h.writeError(w, "Daily prices are required", http.StatusBadRequest)
		return
	}

	// Build scorer input
	input := scorers.ScoreSecurityInput{
		Symbol:                req.Symbol,
		DailyPrices:           req.DailyPrices,
		MonthlyPrices:         req.MonthlyPrices,
		TargetAnnualReturn:    req.TargetAnnualReturn,
		MarketAvgPE:           req.MarketAvgPE,
		PERatio:               req.PERatio,
		ForwardPE:             req.ForwardPE,
		DividendYield:         req.DividendYield,
		PayoutRatio:           req.PayoutRatio,
		FiveYearAvgDivYield:   req.FiveYearAvgDivYield,
		ProfitMargin:          req.ProfitMargin,
		DebtToEquity:          req.DebtToEquity,
		CurrentRatio:          req.CurrentRatio,
		AnalystRecommendation: req.AnalystRecommendation,
		UpsidePct:             req.UpsidePct,
		SortinoRatio:          req.SortinoRatio,
		MaxDrawdown:           req.MaxDrawdown,
	}

	// Calculate score
	score := h.scorer.ScoreSecurityWithDefaults(input)

	h.writeJSON(w, ScoreResponse{Score: score})
}

// writeJSON writes a JSON response
func (h *Handlers) writeJSON(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}

// writeError writes an error response
func (h *Handlers) writeError(w http.ResponseWriter, message string, status int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	errMsg := message
	h.writeJSON(w, ScoreResponse{Error: &errMsg})
}
