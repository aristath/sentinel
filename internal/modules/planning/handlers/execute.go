package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/aristath/arduino-trader/internal/modules/planning"
	"github.com/rs/zerolog"
)

// ExecuteHandler handles executing the next step in a plan.
type ExecuteHandler struct {
	service *planning.Service
	log     zerolog.Logger
}

// NewExecuteHandler creates a new execute handler.
func NewExecuteHandler(service *planning.Service, log zerolog.Logger) *ExecuteHandler {
	return &ExecuteHandler{
		service: service,
		log:     log.With().Str("handler", "execute").Logger(),
	}
}

// ExecuteRequest represents the request to execute a plan step.
type ExecuteRequest struct {
	PlanID     string `json:"plan_id"`
	StepNumber int    `json:"step_number"`
}

// ExecuteResponse represents the response after executing a step.
type ExecuteResponse struct {
	Success    bool   `json:"success"`
	Message    string `json:"message"`
	StepNumber int    `json:"step_number"`
	NextStep   int    `json:"next_step,omitempty"`
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
		Str("plan_id", req.PlanID).
		Int("step_number", req.StepNumber).
		Msg("Executing plan step")

	// TODO: Implement actual execution logic
	// This would:
	// 1. Retrieve the plan from database
	// 2. Validate the step number
	// 3. Execute the trade via trading service
	// 4. Update plan execution status
	// 5. Return result

	// For now, return a placeholder response
	response := ExecuteResponse{
		Success:    true,
		Message:    "Step execution initiated (placeholder)",
		StepNumber: req.StepNumber,
		NextStep:   req.StepNumber + 1,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}
