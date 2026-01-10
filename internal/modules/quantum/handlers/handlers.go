// Package handlers provides HTTP handlers for quantum probability operations.
package handlers

import (
	"encoding/json"
	"math"
	"net/http"
	"time"

	"github.com/aristath/sentinel/internal/modules/quantum"
	"github.com/rs/zerolog"
)

// Handler handles quantum HTTP requests
type Handler struct {
	calculator *quantum.QuantumProbabilityCalculator
	log        zerolog.Logger
}

// NewHandler creates a new quantum handler
func NewHandler(
	calculator *quantum.QuantumProbabilityCalculator,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		calculator: calculator,
		log:        log.With().Str("handler", "quantum").Logger(),
	}
}

// AmplitudeRequest represents a request to calculate quantum amplitude
type AmplitudeRequest struct {
	Probability float64 `json:"probability"`
	Energy      float64 `json:"energy"`
}

// InterferenceRequest represents a request to calculate interference
type InterferenceRequest struct {
	P1      float64 `json:"p1"`
	P2      float64 `json:"p2"`
	Energy1 float64 `json:"energy1"`
	Energy2 float64 `json:"energy2"`
}

// ProbabilityRequest represents a request to calculate probability from amplitude
type ProbabilityRequest struct {
	AmplitudeReal float64 `json:"amplitude_real"`
	AmplitudeImag float64 `json:"amplitude_imag"`
}

// MultimodalCorrectionRequest represents a request to calculate multimodal correction
type MultimodalCorrectionRequest struct {
	Volatility float64  `json:"volatility"`
	Kurtosis   *float64 `json:"kurtosis,omitempty"`
}

// HandleCalculateAmplitude handles POST /api/quantum/amplitude
func (h *Handler) HandleCalculateAmplitude(w http.ResponseWriter, r *http.Request) {
	var req AmplitudeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	amplitude := h.calculator.CalculateQuantumAmplitude(req.Probability, req.Energy)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"probability": req.Probability,
			"energy":      req.Energy,
			"amplitude": map[string]interface{}{
				"real":      real(amplitude),
				"imaginary": imag(amplitude),
				"magnitude": math.Sqrt(real(amplitude)*real(amplitude) + imag(amplitude)*imag(amplitude)),
				"phase":     math.Atan2(imag(amplitude), real(amplitude)),
			},
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleCalculateInterference handles POST /api/quantum/interference
func (h *Handler) HandleCalculateInterference(w http.ResponseWriter, r *http.Request) {
	var req InterferenceRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.P1 < 0 || req.P1 > 1 || req.P2 < 0 || req.P2 > 1 {
		http.Error(w, "Probabilities must be between 0 and 1", http.StatusBadRequest)
		return
	}

	interference := h.calculator.CalculateInterference(req.P1, req.P2, req.Energy1, req.Energy2)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"p1":           req.P1,
			"p2":           req.P2,
			"energy1":      req.Energy1,
			"energy2":      req.Energy2,
			"energy_diff":  req.Energy2 - req.Energy1,
			"interference": interference,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleCalculateProbability handles POST /api/quantum/probability
func (h *Handler) HandleCalculateProbability(w http.ResponseWriter, r *http.Request) {
	var req ProbabilityRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	amplitude := complex(req.AmplitudeReal, req.AmplitudeImag)
	probability := h.calculator.BornRule(amplitude)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"amplitude": map[string]interface{}{
				"real":      req.AmplitudeReal,
				"imaginary": req.AmplitudeImag,
			},
			"probability": probability,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetEnergyLevels handles GET /api/quantum/energy-levels
func (h *Handler) HandleGetEnergyLevels(w http.ResponseWriter, r *http.Request) {
	// Discrete energy levels used in the quantum calculator
	levels := []map[string]interface{}{
		{
			"level":       -math.Pi,
			"description": "Lowest energy state",
			"numeric":     -math.Pi,
		},
		{
			"level":       -math.Pi / 2.0,
			"description": "Low energy state",
			"numeric":     -math.Pi / 2.0,
		},
		{
			"level":       0.0,
			"description": "Ground state",
			"numeric":     0.0,
		},
		{
			"level":       math.Pi / 2.0,
			"description": "High energy state",
			"numeric":     math.Pi / 2.0,
		},
		{
			"level":       math.Pi,
			"description": "Highest energy state",
			"numeric":     math.Pi,
		},
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"levels":      levels,
			"count":       len(levels),
			"energy_unit": "radians",
			"note":        "Energy levels are quantized to discrete values",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleCalculateMultimodalCorrection handles POST /api/quantum/multimodal-correction
func (h *Handler) HandleCalculateMultimodalCorrection(w http.ResponseWriter, r *http.Request) {
	var req MultimodalCorrectionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.log.Error().Err(err).Msg("Failed to decode request body")
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.Volatility < 0 {
		http.Error(w, "Volatility must be non-negative", http.StatusBadRequest)
		return
	}

	correction := h.calculator.CalculateMultimodalCorrection(req.Volatility, req.Kurtosis)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"volatility": req.Volatility,
			"kurtosis":   req.Kurtosis,
			"correction": correction,
			"note":       "Correction accounts for fat tails in distribution",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// writeJSON writes a JSON response
func (h *Handler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}
