// Package handlers provides HTTP handlers for market regime and adaptation operations.
package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/aristath/sentinel/internal/market_regime"
	"github.com/aristath/sentinel/internal/modules/adaptation"
	"github.com/rs/zerolog"
)

// Handler handles market regime and adaptation HTTP requests
type Handler struct {
	regimePersistence *market_regime.RegimePersistence
	adaptiveService   *adaptation.AdaptiveMarketService
	log               zerolog.Logger
}

// NewHandler creates a new adaptation handler
func NewHandler(
	regimePersistence *market_regime.RegimePersistence,
	adaptiveService *adaptation.AdaptiveMarketService,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		regimePersistence: regimePersistence,
		adaptiveService:   adaptiveService,
		log:               log.With().Str("handler", "adaptation").Logger(),
	}
}

// HandleGetCurrent handles GET /api/adaptation/current
func (h *Handler) HandleGetCurrent(w http.ResponseWriter, r *http.Request) {
	var rawScore, smoothedScore float64
	var discreteRegime string
	var recordedAt time.Time

	if h.regimePersistence != nil {
		entry, err := h.regimePersistence.GetLatestEntry()
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to get current regime score")
			http.Error(w, "Failed to get current regime score", http.StatusInternalServerError)
			return
		}
		if entry == nil {
			// No regime history yet
			rawScore = 0.0
			smoothedScore = 0.0
			discreteRegime = "neutral"
			recordedAt = time.Now()
		} else {
			rawScore = float64(entry.RawScore)
			smoothedScore = float64(entry.SmoothedScore)
			discreteRegime = entry.DiscreteRegime
			recordedAt = entry.RecordedAt
		}
	} else {
		// No regime persistence available
		rawScore = 0.0
		smoothedScore = 0.0
		discreteRegime = "neutral"
		recordedAt = time.Now()
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"raw_score":       rawScore,
			"smoothed_score":  smoothedScore,
			"discrete_regime": discreteRegime,
			"recorded_at":     recordedAt.Format(time.RFC3339),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetHistory handles GET /api/adaptation/history
func (h *Handler) HandleGetHistory(w http.ResponseWriter, r *http.Request) {
	// Parse query parameters
	limit := 100 // default
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit
		}
	}

	var history []map[string]interface{}

	if h.regimePersistence != nil {
		entries, err := h.regimePersistence.GetRegimeHistory(limit)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to get regime history")
			http.Error(w, "Failed to get regime history", http.StatusInternalServerError)
			return
		}

		history = make([]map[string]interface{}, 0, len(entries))
		for _, entry := range entries {
			history = append(history, map[string]interface{}{
				"recorded_at":     entry.RecordedAt.Format(time.RFC3339),
				"raw_score":       float64(entry.RawScore),
				"smoothed_score":  float64(entry.SmoothedScore),
				"discrete_regime": entry.DiscreteRegime,
			})
		}
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"history": history,
			"count":   len(history),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetAdaptiveWeights handles GET /api/adaptation/adaptive-weights
func (h *Handler) HandleGetAdaptiveWeights(w http.ResponseWriter, r *http.Request) {
	// Get current regime score
	var smoothedScore float64
	if h.regimePersistence != nil {
		entry, err := h.regimePersistence.GetLatestEntry()
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to get regime score")
			http.Error(w, "Failed to get regime score", http.StatusInternalServerError)
			return
		}
		if entry != nil {
			smoothedScore = float64(entry.SmoothedScore)
		} else {
			smoothedScore = 0.0 // Default to neutral
		}
	} else {
		smoothedScore = 0.0 // Default to neutral
	}

	// Calculate adaptive weights
	weights := h.adaptiveService.CalculateAdaptiveWeights(smoothedScore)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"regime_score": smoothedScore,
			"weights":      weights,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetAdaptiveParameters handles GET /api/adaptation/adaptive-parameters
func (h *Handler) HandleGetAdaptiveParameters(w http.ResponseWriter, r *http.Request) {
	// Get current regime score
	var smoothedScore float64
	if h.regimePersistence != nil {
		entry, err := h.regimePersistence.GetLatestEntry()
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to get regime score")
			http.Error(w, "Failed to get regime score", http.StatusInternalServerError)
			return
		}
		if entry != nil {
			smoothedScore = float64(entry.SmoothedScore)
		} else {
			smoothedScore = 0.0 // Default to neutral
		}
	} else {
		smoothedScore = 0.0 // Default to neutral
	}

	// Calculate all adaptive parameters
	weights := h.adaptiveService.CalculateAdaptiveWeights(smoothedScore)
	blend := h.adaptiveService.CalculateAdaptiveBlend(smoothedScore)
	qualityGates := h.adaptiveService.CalculateAdaptiveQualityGates(smoothedScore)

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"regime_score": smoothedScore,
			"weights":      weights,
			"blend":        blend,
			"quality_gates": map[string]interface{}{
				"stability": qualityGates.GetStability(),
				"long_term": qualityGates.GetLongTerm(),
			},
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetComponentPerformance handles GET /api/adaptation/component-performance
func (h *Handler) HandleGetComponentPerformance(w http.ResponseWriter, r *http.Request) {
	// Component performance tracking is not yet implemented in the service
	// Return placeholder structure for now
	response := map[string]interface{}{
		"data": map[string]interface{}{
			"components": []map[string]interface{}{},
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
			"note":      "Component performance tracking not yet implemented",
		},
	}

	h.writeJSON(w, http.StatusOK, response)
}

// HandleGetPerformanceHistory handles GET /api/adaptation/performance-history
func (h *Handler) HandleGetPerformanceHistory(w http.ResponseWriter, r *http.Request) {
	// Component performance history tracking is not yet implemented in the service
	// Return placeholder structure for now
	response := map[string]interface{}{
		"data": map[string]interface{}{
			"history": []map[string]interface{}{},
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
			"note":      "Component performance history tracking not yet implemented",
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
