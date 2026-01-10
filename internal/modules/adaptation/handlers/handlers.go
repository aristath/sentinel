// Package handlers provides HTTP handlers for market regime and adaptation operations.
package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/aristath/sentinel/internal/modules/adaptation"
	"github.com/rs/zerolog"
)

// Handler handles market regime and adaptation HTTP requests
type Handler struct {
	configDB        *sql.DB
	adaptiveService *adaptation.AdaptiveMarketService
	log             zerolog.Logger
}

// NewHandler creates a new adaptation handler
func NewHandler(
	configDB *sql.DB,
	adaptiveService *adaptation.AdaptiveMarketService,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		configDB:        configDB,
		adaptiveService: adaptiveService,
		log:             log.With().Str("handler", "adaptation").Logger(),
	}
}

// HandleGetCurrent handles GET /api/adaptation/current
func (h *Handler) HandleGetCurrent(w http.ResponseWriter, r *http.Request) {
	// Get latest regime score from history
	query := `SELECT recorded_at, raw_score, smoothed_score, discrete_regime
	          FROM market_regime_history
	          ORDER BY id DESC LIMIT 1`

	var recordedAt int64
	var rawScore, smoothedScore float64
	var discreteRegime string

	err := h.configDB.QueryRow(query).Scan(&recordedAt, &rawScore, &smoothedScore, &discreteRegime)
	if err == sql.ErrNoRows {
		// No regime history yet
		response := map[string]interface{}{
			"data": map[string]interface{}{
				"raw_score":       0.0,
				"smoothed_score":  0.0,
				"discrete_regime": "neutral",
				"recorded_at":     time.Now().Format(time.RFC3339),
			},
			"metadata": map[string]interface{}{
				"timestamp": time.Now().Format(time.RFC3339),
			},
		}
		h.writeJSON(w, http.StatusOK, response)
		return
	}
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get current regime score")
		http.Error(w, "Failed to get current regime score", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"data": map[string]interface{}{
			"raw_score":       rawScore,
			"smoothed_score":  smoothedScore,
			"discrete_regime": discreteRegime,
			"recorded_at":     time.Unix(recordedAt, 0).Format(time.RFC3339),
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

	query := `SELECT recorded_at, raw_score, smoothed_score, discrete_regime
	          FROM market_regime_history
	          ORDER BY id DESC LIMIT ?`

	rows, err := h.configDB.Query(query, limit)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get regime history")
		http.Error(w, "Failed to get regime history", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	history := make([]map[string]interface{}, 0)
	for rows.Next() {
		var recordedAt int64
		var rawScore, smoothedScore float64
		var discreteRegime string

		err := rows.Scan(&recordedAt, &rawScore, &smoothedScore, &discreteRegime)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to scan regime history row")
			continue
		}

		history = append(history, map[string]interface{}{
			"recorded_at":     time.Unix(recordedAt, 0).Format(time.RFC3339),
			"raw_score":       rawScore,
			"smoothed_score":  smoothedScore,
			"discrete_regime": discreteRegime,
		})
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
	err := h.configDB.QueryRow(`SELECT smoothed_score FROM market_regime_history ORDER BY id DESC LIMIT 1`).Scan(&smoothedScore)
	if err == sql.ErrNoRows {
		smoothedScore = 0.0 // Default to neutral
	} else if err != nil {
		h.log.Error().Err(err).Msg("Failed to get regime score")
		http.Error(w, "Failed to get regime score", http.StatusInternalServerError)
		return
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
	err := h.configDB.QueryRow(`SELECT smoothed_score FROM market_regime_history ORDER BY id DESC LIMIT 1`).Scan(&smoothedScore)
	if err == sql.ErrNoRows {
		smoothedScore = 0.0 // Default to neutral
	} else if err != nil {
		h.log.Error().Err(err).Msg("Failed to get regime score")
		http.Error(w, "Failed to get regime score", http.StatusInternalServerError)
		return
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
				"fundamentals": qualityGates.GetFundamentals(),
				"long_term":    qualityGates.GetLongTerm(),
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
