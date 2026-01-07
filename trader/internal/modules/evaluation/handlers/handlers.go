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
