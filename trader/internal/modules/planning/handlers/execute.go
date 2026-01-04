package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/planning/repository"
	"github.com/rs/zerolog"
)

// TradeExecutor defines the interface for executing trades.
// This will be implemented by the trading module.
type TradeExecutor interface {
	ExecuteTrade(step *domain.HolisticStep) error
}

// ExecuteHandler handles executing the next step in a plan.
type ExecuteHandler struct {
	repository *repository.PlannerRepository
	executor   TradeExecutor
	log        zerolog.Logger
}

// NewExecuteHandler creates a new execute handler.
func NewExecuteHandler(
	repo *repository.PlannerRepository,
	executor TradeExecutor,
	log zerolog.Logger,
) *ExecuteHandler {
	return &ExecuteHandler{
		repository: repo,
		executor:   executor,
		log:        log.With().Str("handler", "execute").Logger(),
	}
}

// ExecuteRequest represents the request to execute a plan step.
type ExecuteRequest struct {
	PortfolioHash string `json:"portfolio_hash"`
	StepNumber    int    `json:"step_number"`
}

// ExecuteResponse represents the response after executing a step.
type ExecuteResponse struct {
	Success          bool   `json:"success"`
	Message          string `json:"message"`
	StepNumber       int    `json:"step_number"`
	NextStep         int    `json:"next_step,omitempty"`
	ExecutionDetails string `json:"execution_details,omitempty"`
}

// ServeHTTP handles POST /api/planning/execute requests.
func (h *ExecuteHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req ExecuteRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	h.log.Info().
		Str("portfolio_hash", req.PortfolioHash).
		Int("step_number", req.StepNumber).
		Msg("Executing plan step")

	// 1. Retrieve the best plan from database
	bestResult, err := h.repository.GetBestResult(req.PortfolioHash)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to retrieve best result")
		http.Error(w, "Plan not found", http.StatusNotFound)
		return
	}

	if bestResult == nil {
		h.log.Warn().Str("portfolio_hash", req.PortfolioHash).Msg("No plan found for portfolio")
		http.Error(w, "No plan available for this portfolio", http.StatusNotFound)
		return
	}

	// 2. Validate the step number
	if req.StepNumber < 1 || req.StepNumber > len(bestResult.Steps) {
		h.log.Warn().
			Int("step_number", req.StepNumber).
			Int("total_steps", len(bestResult.Steps)).
			Msg("Invalid step number")
		http.Error(w, fmt.Sprintf("Invalid step number: must be between 1 and %d", len(bestResult.Steps)), http.StatusBadRequest)
		return
	}

	// Get the step (convert to 0-indexed)
	step := bestResult.Steps[req.StepNumber-1]

	// 3. Execute the trade via trading service
	if h.executor != nil {
		if err := h.executor.ExecuteTrade(&step); err != nil {
			h.log.Error().
				Err(err).
				Str("symbol", step.Symbol).
				Str("side", step.Side).
				Msg("Trade execution failed")

			response := ExecuteResponse{
				Success:          false,
				Message:          fmt.Sprintf("Trade execution failed: %v", err),
				StepNumber:       req.StepNumber,
				ExecutionDetails: fmt.Sprintf("Failed to execute %s %s", step.Side, step.Symbol),
			}

			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(response)
			return
		}
	} else {
		h.log.Warn().Msg("No trade executor configured - execution skipped")
	}

	// 4. Build execution details
	executionDetails := fmt.Sprintf(
		"Executed step %d: %s %s (quantity: %d, price: $%.2f, value: $%.2f %s)",
		req.StepNumber,
		step.Side,
		step.Symbol,
		step.Quantity,
		step.EstimatedPrice,
		step.EstimatedValue,
		step.Currency,
	)

	// 5. Return success response
	nextStep := 0
	if req.StepNumber < len(bestResult.Steps) {
		nextStep = req.StepNumber + 1
	}

	response := ExecuteResponse{
		Success:          true,
		Message:          "Step executed successfully",
		StepNumber:       req.StepNumber,
		NextStep:         nextStep,
		ExecutionDetails: executionDetails,
	}

	h.log.Info().
		Str("symbol", step.Symbol).
		Str("side", step.Side).
		Float64("value", step.EstimatedValue).
		Msg("Step executed successfully")

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}
