// Package handlers provides HTTP handlers for security evaluation.
package handlers

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/aristath/sentinel/internal/modules/evaluation"
	"github.com/rs/zerolog"
)

// Handler handles evaluation HTTP requests
type Handler struct {
	service *evaluation.Service
	log     zerolog.Logger
}

// NewHandler creates a new evaluation handler
func NewHandler(service *evaluation.Service, log zerolog.Logger) *Handler {
	return &Handler{
		service: service,
		log:     log.With().Str("handler", "evaluation").Logger(),
	}
}

// HandleEvaluateBatch handles POST /api/v1/evaluate/batch
func (h *Handler) HandleEvaluateBatch(w http.ResponseWriter, r *http.Request) {
	var request evaluation.BatchEvaluationRequest

	// Parse request body
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	// Validate request
	if len(request.Sequences) == 0 {
		h.writeError(w, http.StatusBadRequest, "No sequences provided")
		return
	}

	// Validate reasonable batch size to prevent resource exhaustion
	if len(request.Sequences) > 10000 {
		h.writeError(w, http.StatusBadRequest, "Too many sequences (max 10000)")
		return
	}

	// Validate transaction costs are non-negative
	if request.EvaluationContext.TransactionCostFixed < 0 {
		h.writeError(w, http.StatusBadRequest, "Transaction cost fixed cannot be negative")
		return
	}

	if request.EvaluationContext.TransactionCostPercent < 0 {
		h.writeError(w, http.StatusBadRequest, "Transaction cost percent cannot be negative")
		return
	}

	// Evaluate sequences using service
	startTime := time.Now()
	results, err := h.service.EvaluateBatch(
		request.Sequences,
		request.EvaluationContext,
	)
	elapsed := time.Since(startTime)

	if err != nil {
		h.writeError(w, http.StatusInternalServerError, "Evaluation failed: "+err.Error())
		return
	}

	// Log performance metrics
	h.log.Info().
		Int("sequences", len(request.Sequences)).
		Dur("elapsed", elapsed).
		Float64("ms_per_sequence", float64(elapsed.Milliseconds())/float64(len(request.Sequences))).
		Msg("Batch evaluation completed")

	// Build response
	response := evaluation.BatchEvaluationResponse{
		Results: results,
		Errors:  []string{}, // Errors per sequence (if any)
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleSimulateBatch handles POST /api/v1/simulate/batch
func (h *Handler) HandleSimulateBatch(w http.ResponseWriter, r *http.Request) {
	var request evaluation.BatchSimulationRequest

	// Parse request body
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	// Validate request
	if len(request.Sequences) == 0 {
		h.writeError(w, http.StatusBadRequest, "No sequences provided")
		return
	}

	// Validate reasonable batch size to prevent resource exhaustion
	if len(request.Sequences) > 10000 {
		h.writeError(w, http.StatusBadRequest, "Too many sequences (max 10000)")
		return
	}

	// Simulate sequences using service
	startTime := time.Now()
	results, err := h.service.SimulateBatch(
		request.Sequences,
		request.EvaluationContext,
	)
	elapsed := time.Since(startTime)

	if err != nil {
		h.writeError(w, http.StatusInternalServerError, "Simulation failed: "+err.Error())
		return
	}

	// Log performance metrics
	h.log.Info().
		Int("sequences", len(request.Sequences)).
		Dur("elapsed", elapsed).
		Float64("ms_per_sequence", float64(elapsed.Milliseconds())/float64(len(request.Sequences))).
		Msg("Batch simulation completed")

	// Build response
	response := evaluation.BatchSimulationResponse{
		Results: results,
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleMonteCarlo handles POST /api/v1/evaluate/monte-carlo
func (h *Handler) HandleMonteCarlo(w http.ResponseWriter, r *http.Request) {
	var request evaluation.MonteCarloRequest

	// Parse request body
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	// Validate request
	if len(request.Sequence) == 0 {
		h.writeError(w, http.StatusBadRequest, "No sequence provided")
		return
	}

	if request.Paths < 1 || request.Paths > 1000 {
		h.writeError(w, http.StatusBadRequest, "Paths must be between 1 and 1000")
		return
	}

	// Evaluate using service
	startTime := time.Now()
	result, err := h.service.EvaluateMonteCarlo(request)
	elapsed := time.Since(startTime)

	if err != nil {
		h.writeError(w, http.StatusInternalServerError, "Monte Carlo evaluation failed: "+err.Error())
		return
	}

	// Log performance metrics
	h.log.Info().
		Int("paths", request.Paths).
		Dur("elapsed", elapsed).
		Float64("final_score", result.FinalScore).
		Msg("Monte Carlo evaluation completed")

	h.writeJSON(w, http.StatusOK, result)
}

// HandleStochastic handles POST /api/v1/evaluate/stochastic
func (h *Handler) HandleStochastic(w http.ResponseWriter, r *http.Request) {
	var request evaluation.StochasticRequest

	// Parse request body
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	// Validate request
	if len(request.Sequence) == 0 {
		h.writeError(w, http.StatusBadRequest, "No sequence provided")
		return
	}

	// Evaluate using service
	startTime := time.Now()
	result, err := h.service.EvaluateStochastic(request)
	elapsed := time.Since(startTime)

	if err != nil {
		h.writeError(w, http.StatusInternalServerError, "Stochastic evaluation failed: "+err.Error())
		return
	}

	// Log performance metrics
	h.log.Info().
		Int("scenarios", result.ScenariosEvaluated).
		Dur("elapsed", elapsed).
		Float64("weighted_score", result.WeightedScore).
		Msg("Stochastic evaluation completed")

	h.writeJSON(w, http.StatusOK, result)
}

// Helper methods

// writeJSON writes a JSON response
func (h *Handler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}

// writeError writes an error response
func (h *Handler) writeError(w http.ResponseWriter, status int, message string) {
	h.writeJSON(w, status, map[string]string{
		"error": message,
	})
}

// HandleEvaluateSingle handles POST /api/v1/evaluate/single
func (h *Handler) HandleEvaluateSingle(w http.ResponseWriter, r *http.Request) {
	var request struct {
		Sequence          []evaluation.ActionCandidate `json:"sequence"`
		EvaluationContext evaluation.EvaluationContext  `json:"evaluation_context"`
	}

	// Parse request body
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	// Validate request
	if len(request.Sequence) == 0 {
		h.writeError(w, http.StatusBadRequest, "No sequence provided")
		return
	}

	// Evaluate using batch service with single sequence
	startTime := time.Now()
	results, err := h.service.EvaluateBatch(
		[][]evaluation.ActionCandidate{request.Sequence},
		request.EvaluationContext,
	)
	elapsed := time.Since(startTime)

	if err != nil {
		h.writeError(w, http.StatusInternalServerError, "Evaluation failed: "+err.Error())
		return
	}

	if len(results) == 0 {
		h.writeError(w, http.StatusInternalServerError, "No result returned")
		return
	}

	// Log performance metrics
	h.log.Info().
		Int("actions", len(request.Sequence)).
		Dur("elapsed", elapsed).
		Float64("score", results[0].Score).
		Msg("Single sequence evaluation completed")

	h.writeJSON(w, http.StatusOK, results[0])
}

// HandleEvaluateCompare handles POST /api/v1/evaluate/compare
func (h *Handler) HandleEvaluateCompare(w http.ResponseWriter, r *http.Request) {
	var request struct {
		Sequences         [][]evaluation.ActionCandidate `json:"sequences"`
		EvaluationContext evaluation.EvaluationContext   `json:"evaluation_context"`
	}

	// Parse request body
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	// Validate request
	if len(request.Sequences) < 2 {
		h.writeError(w, http.StatusBadRequest, "At least 2 sequences required for comparison")
		return
	}

	if len(request.Sequences) > 100 {
		h.writeError(w, http.StatusBadRequest, "Too many sequences for comparison (max 100)")
		return
	}

	// Evaluate using batch service
	startTime := time.Now()
	results, err := h.service.EvaluateBatch(
		request.Sequences,
		request.EvaluationContext,
	)
	elapsed := time.Since(startTime)

	if err != nil {
		h.writeError(w, http.StatusInternalServerError, "Evaluation failed: "+err.Error())
		return
	}

	// Calculate comparison metrics
	var bestIdx, worstIdx int
	bestScore, worstScore := results[0].Score, results[0].Score
	for i, result := range results {
		if result.Score > bestScore {
			bestScore = result.Score
			bestIdx = i
		}
		if result.Score < worstScore {
			worstScore = result.Score
			worstIdx = i
		}
	}

	// Build comparison response
	response := map[string]interface{}{
		"results": results,
		"comparison": map[string]interface{}{
			"count":             len(results),
			"best_index":        bestIdx,
			"worst_index":       worstIdx,
			"best_score":        bestScore,
			"worst_score":       worstScore,
			"score_range":       bestScore - worstScore,
			"all_feasible":      allFeasible(results),
			"evaluation_time_ms": elapsed.Milliseconds(),
		},
	}

	// Log performance metrics
	h.log.Info().
		Int("sequences", len(request.Sequences)).
		Dur("elapsed", elapsed).
		Float64("best_score", bestScore).
		Float64("worst_score", worstScore).
		Msg("Sequence comparison completed")

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetEvaluationCriteria handles GET /api/v1/evaluation/criteria
func (h *Handler) HandleGetEvaluationCriteria(w http.ResponseWriter, r *http.Request) {
	// Return evaluation criteria and weights
	criteria := map[string]interface{}{
		"base_weights": map[string]interface{}{
			"geographic_fit":    0.25,
			"industry_fit":      0.25,
			"quality_score_fit": 0.15,
			"optimizer_fit":     0.35,
		},
		"cost_impact": map[string]interface{}{
			"penalty_factor": "Configurable (default: 1.0)",
			"description":    "Transaction costs reduce final score",
		},
		"feasibility": map[string]interface{}{
			"min_score":      "Must be > 0",
			"cash_sufficiency": "Must have enough cash for all trades",
			"description":    "Infeasible sequences get score of 0",
		},
		"allocation_fit_formula": "Weighted sum of geographic, industry, quality, and optimizer alignment",
		"final_score_formula":    "allocation_fit - (transaction_costs * penalty_factor)",
		"notes":                  "Higher scores indicate better portfolio alignment",
	}

	response := map[string]interface{}{
		"data": criteria,
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleSimulateCustomPrices handles POST /api/v1/simulate/custom-prices
func (h *Handler) HandleSimulateCustomPrices(w http.ResponseWriter, r *http.Request) {
	var request struct {
		Sequence          []evaluation.ActionCandidate `json:"sequence"`
		CustomPrices      map[string]float64           `json:"custom_prices"`
		EvaluationContext evaluation.EvaluationContext  `json:"evaluation_context"`
	}

	// Parse request body
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	// Validate request
	if len(request.Sequence) == 0 {
		h.writeError(w, http.StatusBadRequest, "No sequence provided")
		return
	}

	if len(request.CustomPrices) == 0 {
		h.writeError(w, http.StatusBadRequest, "No custom prices provided")
		return
	}

	// Override current prices with custom prices
	request.EvaluationContext.PriceAdjustments = request.CustomPrices

	// Simulate using batch service
	startTime := time.Now()
	results, err := h.service.SimulateBatch(
		[][]evaluation.ActionCandidate{request.Sequence},
		request.EvaluationContext,
	)
	elapsed := time.Since(startTime)

	if err != nil {
		h.writeError(w, http.StatusInternalServerError, "Simulation failed: "+err.Error())
		return
	}

	if len(results) == 0 {
		h.writeError(w, http.StatusInternalServerError, "No result returned")
		return
	}

	// Build response
	response := map[string]interface{}{
		"result":      results[0],
		"custom_prices": request.CustomPrices,
		"metadata": map[string]interface{}{
			"timestamp":      time.Now().Format(time.RFC3339),
			"elapsed_ms":     elapsed.Milliseconds(),
			"prices_applied": len(request.CustomPrices),
		},
	}

	// Log performance metrics
	h.log.Info().
		Int("actions", len(request.Sequence)).
		Int("custom_prices", len(request.CustomPrices)).
		Dur("elapsed", elapsed).
		Msg("Custom price simulation completed")

	h.writeJSON(w, http.StatusOK, response)
}

// HandleMonteCarloAdvanced handles POST /api/v1/monte-carlo/advanced
func (h *Handler) HandleMonteCarloAdvanced(w http.ResponseWriter, r *http.Request) {
	var request struct {
		Sequence           []evaluation.ActionCandidate `json:"sequence"`
		SymbolVolatilities map[string]float64           `json:"symbol_volatilities"`
		EvaluationContext  evaluation.EvaluationContext  `json:"evaluation_context"`
		Paths              int                          `json:"paths"`
		CustomDrift        map[string]float64           `json:"custom_drift,omitempty"`
		ConservativeWeight float64                      `json:"conservative_weight,omitempty"`
	}

	// Parse request body
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body: "+err.Error())
		return
	}

	// Validate request
	if len(request.Sequence) == 0 {
		h.writeError(w, http.StatusBadRequest, "No sequence provided")
		return
	}

	if request.Paths < 1 || request.Paths > 1000 {
		h.writeError(w, http.StatusBadRequest, "Paths must be between 1 and 1000")
		return
	}

	// Build Monte Carlo request
	mcRequest := evaluation.MonteCarloRequest{
		Sequence:           request.Sequence,
		SymbolVolatilities: request.SymbolVolatilities,
		EvaluationContext:  request.EvaluationContext,
		Paths:              request.Paths,
	}

	// Evaluate using service
	startTime := time.Now()
	result, err := h.service.EvaluateMonteCarlo(mcRequest)
	elapsed := time.Since(startTime)

	if err != nil {
		h.writeError(w, http.StatusInternalServerError, "Monte Carlo evaluation failed: "+err.Error())
		return
	}

	// If custom conservative weight provided, recalculate final score
	if request.ConservativeWeight > 0 && request.ConservativeWeight <= 1 {
		// Recalculate with custom weighting
		customFinalScore := result.WorstScore*request.ConservativeWeight +
			result.P10Score*(1-request.ConservativeWeight)*0.5 +
			result.AvgScore*(1-request.ConservativeWeight)*0.5
		result.FinalScore = customFinalScore
	}

	// Build response with advanced analytics
	response := map[string]interface{}{
		"result": result,
		"advanced_analytics": map[string]interface{}{
			"volatility_applied":   len(request.SymbolVolatilities),
			"custom_drift_applied": len(request.CustomDrift),
			"conservative_weight":  request.ConservativeWeight,
			"score_distribution": map[string]interface{}{
				"range":     result.BestScore - result.WorstScore,
				"p10_to_p90": result.P90Score - result.P10Score,
				"percentile_range_pct": (result.P90Score - result.P10Score) / (result.BestScore - result.WorstScore) * 100,
			},
		},
		"metadata": map[string]interface{}{
			"timestamp":  time.Now().Format(time.RFC3339),
			"elapsed_ms": elapsed.Milliseconds(),
		},
	}

	// Log performance metrics
	h.log.Info().
		Int("paths", request.Paths).
		Int("volatilities", len(request.SymbolVolatilities)).
		Dur("elapsed", elapsed).
		Float64("final_score", result.FinalScore).
		Msg("Advanced Monte Carlo evaluation completed")

	h.writeJSON(w, http.StatusOK, response)
}

// Helper function to check if all results are feasible
func allFeasible(results []evaluation.SequenceEvaluationResult) bool {
	for _, result := range results {
		if !result.Feasible {
			return false
		}
	}
	return true
}
