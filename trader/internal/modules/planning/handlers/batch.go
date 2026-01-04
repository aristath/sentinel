package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/planning/planner"
	"github.com/aristath/arduino-trader/internal/modules/planning/repository"
	"github.com/rs/zerolog"
)

// BatchHandler handles triggering batch plan generation.
type BatchHandler struct {
	planner    *planner.IncrementalPlanner
	configRepo *repository.ConfigRepository
	log        zerolog.Logger
}

// NewBatchHandler creates a new batch handler.
func NewBatchHandler(
	incrementalPlanner *planner.IncrementalPlanner,
	configRepo *repository.ConfigRepository,
	log zerolog.Logger,
) *BatchHandler {
	return &BatchHandler{
		planner:    incrementalPlanner,
		configRepo: configRepo,
		log:        log.With().Str("handler", "batch").Logger(),
	}
}

// BatchRequest represents a request to trigger batch generation.
type BatchRequest struct {
	OpportunityContext *domain.OpportunityContext `json:"opportunity_context"`
	ConfigID           int64                      `json:"config_id,omitempty"`
	ConfigName         string                     `json:"config_name,omitempty"`
	Force              bool                       `json:"force,omitempty"` // Force regeneration
	BatchSize          int                        `json:"batch_size,omitempty"`
}

// BatchResponse represents the batch generation response.
type BatchResponse struct {
	Success        bool   `json:"success"`
	Message        string `json:"message"`
	JobID          string `json:"job_id"`
	PortfolioHash  string `json:"portfolio_hash"`
	SequencesTotal int    `json:"sequences_total,omitempty"`
}

// ServeHTTP handles POST /api/planning/batch requests.
func (h *BatchHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req BatchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.OpportunityContext == nil {
		http.Error(w, "opportunity_context required", http.StatusBadRequest)
		return
	}

	h.log.Info().
		Bool("force", req.Force).
		Int("batch_size", req.BatchSize).
		Msg("Triggering batch plan generation")

	// Load configuration
	var config *domain.PlannerConfiguration
	var err error

	if req.ConfigID > 0 {
		config, err = h.configRepo.GetConfig(req.ConfigID)
	} else if req.ConfigName != "" {
		config, err = h.configRepo.GetConfigByName(req.ConfigName)
	} else {
		config, err = h.configRepo.GetDefaultConfig()
	}

	if err != nil {
		h.log.Error().Err(err).Msg("Failed to load configuration")
		http.Error(w, "Failed to load configuration", http.StatusInternalServerError)
		return
	}

	// Configure batch generation
	batchConfig := planner.DefaultBatchConfig()
	if req.BatchSize > 0 {
		batchConfig.BatchSize = req.BatchSize
	}
	batchConfig.SaveProgress = true // Always save progress for batch jobs

	// Generate job ID
	jobID := fmt.Sprintf("batch_%d", time.Now().Unix())

	// Execute batch generation asynchronously
	go func() {
		h.log.Info().Str("job_id", jobID).Msg("Starting batch generation")

		result, err := h.planner.GenerateBatch(req.OpportunityContext, config, batchConfig)
		if err != nil {
			h.log.Error().
				Err(err).
				Str("job_id", jobID).
				Msg("Batch generation failed")
			return
		}

		h.log.Info().
			Str("job_id", jobID).
			Int("sequences_total", result.SequencesTotal).
			Int("sequences_evaluated", result.SequencesEvaluated).
			Float64("best_score", result.BestScore).
			Float64("elapsed_seconds", result.Elapsed.Seconds()).
			Bool("complete", result.Complete).
			Msg("Batch generation completed")
	}()

	response := BatchResponse{
		Success:        true,
		Message:        "Batch generation initiated",
		JobID:          jobID,
		PortfolioHash:  "", // Would be computed from context
		SequencesTotal: 0,  // Unknown until generation completes
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted) // 202 Accepted for async processing
	json.NewEncoder(w).Encode(response)
}
