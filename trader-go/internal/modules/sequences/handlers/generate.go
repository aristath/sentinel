package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/sequences"
	"github.com/rs/zerolog"
)

type GenerateHandler struct {
	service *sequences.Service
	log     zerolog.Logger
}

func NewGenerateHandler(service *sequences.Service, log zerolog.Logger) *GenerateHandler {
	return &GenerateHandler{
		service: service,
		log:     log.With().Str("handler", "generate_sequences").Logger(),
	}
}

type GenerateRequest struct {
	Opportunities domain.OpportunitiesByCategory `json:"opportunities"`
	Config        *domain.PlannerConfiguration   `json:"config"`
}

type GenerateResponse struct {
	Sequences []domain.ActionSequence `json:"sequences"`
	Count     int                     `json:"count"`
}

func (h *GenerateHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req GenerateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	sequences, err := h.service.GenerateSequences(req.Opportunities, req.Config)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to generate sequences")
		http.Error(w, "Failed to generate sequences", http.StatusInternalServerError)
		return
	}

	response := GenerateResponse{
		Sequences: sequences,
		Count:     len(sequences),
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}
