// Package handlers provides HTTP handlers for symbolic regression API.
package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/aristath/sentinel/internal/modules/symbolic_regression"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// Handlers provides HTTP handlers for symbolic regression API
type Handlers struct {
	storage   *symbolic_regression.FormulaStorage
	discovery *symbolic_regression.DiscoveryService
	dataPrep  *symbolic_regression.DataPrep
	log       zerolog.Logger
}

// NewHandlers creates new symbolic regression handlers
func NewHandlers(
	storage *symbolic_regression.FormulaStorage,
	discovery *symbolic_regression.DiscoveryService,
	dataPrep *symbolic_regression.DataPrep,
	log zerolog.Logger,
) *Handlers {
	return &Handlers{
		storage:   storage,
		discovery: discovery,
		dataPrep:  dataPrep,
		log:       log.With().Str("component", "symbolic_regression_handlers").Logger(),
	}
}

// HandleListFormulas lists all formulas (active and inactive)
// GET /api/symbolic-regression/formulas?formula_type=expected_return&security_type=stock
func (h *Handlers) HandleListFormulas(w http.ResponseWriter, r *http.Request) {
	formulaTypeStr := r.URL.Query().Get("formula_type")
	securityTypeStr := r.URL.Query().Get("security_type")

	if formulaTypeStr == "" || securityTypeStr == "" {
		h.respondError(w, http.StatusBadRequest, "formula_type and security_type are required")
		return
	}

	formulaType := symbolic_regression.FormulaType(formulaTypeStr)
	securityType := symbolic_regression.SecurityType(securityTypeStr)

	formulas, err := h.storage.GetAllFormulas(formulaType, securityType)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get formulas")
		h.respondError(w, http.StatusInternalServerError, "Failed to retrieve formulas")
		return
	}

	h.respondJSON(w, http.StatusOK, map[string]interface{}{
		"formulas": formulas,
		"count":    len(formulas),
	})
}

// HandleGetActiveFormula gets the active formula for a type
// GET /api/symbolic-regression/formulas/active?formula_type=expected_return&security_type=stock&regime_score=0.3
func (h *Handlers) HandleGetActiveFormula(w http.ResponseWriter, r *http.Request) {
	formulaTypeStr := r.URL.Query().Get("formula_type")
	securityTypeStr := r.URL.Query().Get("security_type")
	regimeScoreStr := r.URL.Query().Get("regime_score")

	if formulaTypeStr == "" || securityTypeStr == "" {
		h.respondError(w, http.StatusBadRequest, "formula_type and security_type are required")
		return
	}

	formulaType := symbolic_regression.FormulaType(formulaTypeStr)
	securityType := symbolic_regression.SecurityType(securityTypeStr)

	var regimePtr *float64
	if regimeScoreStr != "" {
		regimeScore, err := strconv.ParseFloat(regimeScoreStr, 64)
		if err == nil {
			regimePtr = &regimeScore
		}
	}

	formula, err := h.storage.GetActiveFormula(formulaType, securityType, regimePtr)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get active formula")
		h.respondError(w, http.StatusInternalServerError, "Failed to retrieve formula")
		return
	}

	if formula == nil {
		h.respondJSON(w, http.StatusOK, map[string]interface{}{
			"formula": nil,
			"message": "No active formula found",
		})
		return
	}

	h.respondJSON(w, http.StatusOK, map[string]interface{}{
		"formula": formula,
	})
}

// HandleDeactivateFormula deactivates a formula
// POST /api/symbolic-regression/formulas/{id}/deactivate
func (h *Handlers) HandleDeactivateFormula(w http.ResponseWriter, r *http.Request) {
	idStr := chi.URLParam(r, "id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid formula ID")
		return
	}

	err = h.storage.DeactivateFormula(id)
	if err != nil {
		h.log.Error().Err(err).Int64("id", id).Msg("Failed to deactivate formula")
		h.respondError(w, http.StatusInternalServerError, "Failed to deactivate formula")
		return
	}

	h.respondJSON(w, http.StatusOK, map[string]interface{}{
		"message": "Formula deactivated",
		"id":      id,
	})
}

// HandleRunDiscovery runs formula discovery
// POST /api/symbolic-regression/discover
func (h *Handlers) HandleRunDiscovery(w http.ResponseWriter, r *http.Request) {
	if h.discovery == nil || h.dataPrep == nil {
		h.respondError(w, http.StatusServiceUnavailable, "Discovery service not available")
		return
	}

	var req DiscoveryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Validate request
	if req.FormulaType == "" || req.SecurityType == "" {
		h.respondError(w, http.StatusBadRequest, "formula_type and security_type are required")
		return
	}

	if req.StartDate.IsZero() || req.EndDate.IsZero() {
		h.respondError(w, http.StatusBadRequest, "start_date and end_date are required")
		return
	}

	if req.ForwardMonths <= 0 {
		req.ForwardMonths = 6 // Default to 6 months
	}

	// Run discovery
	// Use default regime ranges for regime-specific discovery
	regimeRanges := symbolic_regression.DefaultRegimeRanges()

	var discoveredFormulas []*symbolic_regression.DiscoveredFormula
	var err error

	securityType := symbolic_regression.SecurityType(req.SecurityType)

	if req.FormulaType == string(symbolic_regression.FormulaTypeExpectedReturn) {
		discoveredFormulas, err = h.discovery.DiscoverExpectedReturnFormula(
			securityType,
			req.StartDate,
			req.EndDate,
			req.ForwardMonths,
			regimeRanges, // Discover separate formulas for each regime
		)
	} else if req.FormulaType == string(symbolic_regression.FormulaTypeScoring) {
		discoveredFormulas, err = h.discovery.DiscoverScoringFormula(
			securityType,
			req.StartDate,
			req.EndDate,
			req.ForwardMonths,
			regimeRanges, // Discover separate formulas for each regime
		)
	} else {
		h.respondError(w, http.StatusBadRequest, "Invalid formula_type")
		return
	}

	if err != nil {
		h.log.Error().Err(err).Msg("Discovery failed")
		h.respondError(w, http.StatusInternalServerError, "Discovery failed: "+err.Error())
		return
	}

	h.respondJSON(w, http.StatusOK, map[string]interface{}{
		"formulas": discoveredFormulas,
		"count":    len(discoveredFormulas),
		"message":  "Discovery completed",
	})
}

// DiscoveryRequest represents a discovery request
type DiscoveryRequest struct {
	FormulaType   string    `json:"formula_type"`  // "expected_return" or "scoring"
	SecurityType  string    `json:"security_type"` // "stock" or "etf"
	StartDate     time.Time `json:"start_date"`
	EndDate       time.Time `json:"end_date"`
	ForwardMonths int       `json:"forward_months"` // 6 or 12
}

// HandleGetFormulasByRegime handles GET /api/symbolic-regression/formulas/by-regime
// Returns formulas filtered by regime range
func (h *Handlers) HandleGetFormulasByRegime(w http.ResponseWriter, r *http.Request) {
	regimeMinStr := r.URL.Query().Get("regime_min")
	regimeMaxStr := r.URL.Query().Get("regime_max")

	if regimeMinStr == "" || regimeMaxStr == "" {
		h.respondError(w, http.StatusBadRequest, "regime_min and regime_max are required")
		return
	}

	regimeMin, err := strconv.ParseFloat(regimeMinStr, 64)
	if err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid regime_min")
		return
	}

	regimeMax, err := strconv.ParseFloat(regimeMaxStr, 64)
	if err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid regime_max")
		return
	}

	// Get formulas filtered by regime range
	formulas, err := h.storage.GetFormulasByRegimeRange(regimeMin, regimeMax)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get formulas by regime")
		h.respondError(w, http.StatusInternalServerError, "Failed to retrieve formulas")
		return
	}

	h.respondJSON(w, http.StatusOK, map[string]interface{}{
		"data": map[string]interface{}{
			"formulas":   formulas,
			"count":      len(formulas),
			"regime_min": regimeMin,
			"regime_max": regimeMax,
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	})
}

// HandleGetFormulaMetrics handles GET /api/symbolic-regression/formulas/{id}/metrics
// Returns detailed validation metrics for a specific formula
func (h *Handlers) HandleGetFormulaMetrics(w http.ResponseWriter, r *http.Request) {
	idStr := chi.URLParam(r, "id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid formula ID")
		return
	}

	formula, err := h.storage.GetFormula(id)
	if err != nil {
		h.log.Error().Err(err).Int64("id", id).Msg("Failed to get formula")
		h.respondError(w, http.StatusInternalServerError, "Failed to retrieve formula")
		return
	}

	if formula == nil {
		h.respondError(w, http.StatusNotFound, "Formula not found")
		return
	}

	h.respondJSON(w, http.StatusOK, map[string]interface{}{
		"data": map[string]interface{}{
			"id":                 id,
			"formula_type":       formula.FormulaType,
			"security_type":      formula.SecurityType,
			"regime_range_min":   formula.RegimeRangeMin,
			"regime_range_max":   formula.RegimeRangeMax,
			"formula_expression": formula.FormulaExpression,
			"validation_metrics": formula.ValidationMetrics,
			"discovered_at":      formula.DiscoveredAt.Format(time.RFC3339),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	})
}

// CompareFormulasRequest represents a request to compare formulas
type CompareFormulasRequest struct {
	FormulaIDs []int64  `json:"formula_ids"`
	ISINs      []string `json:"isins"` // Test ISINs for comparison
}

// HandleCompareFormulas handles POST /api/symbolic-regression/formulas/compare
// Compares multiple formulas side-by-side
func (h *Handlers) HandleCompareFormulas(w http.ResponseWriter, r *http.Request) {
	var req CompareFormulasRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	if len(req.FormulaIDs) == 0 {
		h.respondError(w, http.StatusBadRequest, "formula_ids are required")
		return
	}

	// Get all requested formulas
	var formulas []*symbolic_regression.DiscoveredFormula
	for _, formulaID := range req.FormulaIDs {
		formula, err := h.storage.GetFormula(formulaID)
		if err != nil {
			h.log.Warn().Err(err).Int64("formula_id", formulaID).Msg("Failed to get formula")
			continue
		}
		if formula == nil {
			h.log.Warn().Int64("formula_id", formulaID).Msg("Formula not found")
			continue
		}
		formulas = append(formulas, formula)
	}

	// Convert to response format and find best/worst
	var comparisons []map[string]interface{}
	var bestFormula, worstFormula *symbolic_regression.DiscoveredFormula
	var bestScore, worstScore float64 = -1, 999999

	for _, formula := range formulas {
		fitness := 0.0
		if val, ok := formula.ValidationMetrics["fitness"]; ok {
			fitness = val
		}

		comparison := map[string]interface{}{
			"id":                 formula.ID,
			"formula_type":       formula.FormulaType,
			"security_type":      formula.SecurityType,
			"regime_range_min":   formula.RegimeRangeMin,
			"regime_range_max":   formula.RegimeRangeMax,
			"formula_expression": formula.FormulaExpression,
			"validation_metrics": formula.ValidationMetrics,
			"discovered_at":      formula.DiscoveredAt.Format(time.RFC3339),
		}

		comparisons = append(comparisons, comparison)

		if fitness > bestScore {
			bestScore = fitness
			bestFormula = formula
		}
		if fitness < worstScore {
			worstScore = fitness
			worstFormula = formula
		}
	}

	var bestFormulaData, worstFormulaData map[string]interface{}
	if bestFormula != nil {
		bestFormulaData = map[string]interface{}{
			"id":                 bestFormula.ID,
			"formula_expression": bestFormula.FormulaExpression,
			"fitness_score":      bestScore,
		}
	}
	if worstFormula != nil {
		worstFormulaData = map[string]interface{}{
			"id":                 worstFormula.ID,
			"formula_expression": worstFormula.FormulaExpression,
			"fitness_score":      worstScore,
		}
	}

	h.respondJSON(w, http.StatusOK, map[string]interface{}{
		"data": map[string]interface{}{
			"formulas":      comparisons,
			"count":         len(comparisons),
			"best_formula":  bestFormulaData,
			"worst_formula": worstFormulaData,
			"note":          "Full prediction comparison requires test data evaluation",
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	})
}

// HandleGetTrainingData handles GET /api/symbolic-regression/training-data/{isin}
// Returns training examples for a specific security
func (h *Handlers) HandleGetTrainingData(w http.ResponseWriter, r *http.Request) {
	if h.dataPrep == nil {
		h.respondError(w, http.StatusServiceUnavailable, "Data preparation service not available")
		return
	}

	isin := chi.URLParam(r, "isin")
	if isin == "" {
		h.respondError(w, http.StatusBadRequest, "ISIN is required")
		return
	}

	trainingDateStr := r.URL.Query().Get("training_date")
	forwardMonthsStr := r.URL.Query().Get("forward_months")

	if trainingDateStr == "" {
		h.respondError(w, http.StatusBadRequest, "training_date is required (YYYY-MM-DD)")
		return
	}

	trainingDate, err := time.Parse("2006-01-02", trainingDateStr)
	if err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid training_date format (use YYYY-MM-DD)")
		return
	}

	forwardMonths := 6 // Default
	if forwardMonthsStr != "" {
		forwardMonths, err = strconv.Atoi(forwardMonthsStr)
		if err != nil {
			h.respondError(w, http.StatusBadRequest, "Invalid forward_months")
			return
		}
	}

	// Extract training examples
	examples, err := h.dataPrep.ExtractTrainingExamples(trainingDate, forwardMonths)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to extract training examples")
		h.respondError(w, http.StatusInternalServerError, "Failed to extract training data")
		return
	}

	// Filter to requested ISIN
	var filteredExamples []symbolic_regression.TrainingExample
	for _, ex := range examples {
		if ex.SecurityISIN == isin {
			filteredExamples = append(filteredExamples, ex)
		}
	}

	h.respondJSON(w, http.StatusOK, map[string]interface{}{
		"data": map[string]interface{}{
			"isin":            isin,
			"training_date":   trainingDateStr,
			"forward_months":  forwardMonths,
			"examples":        filteredExamples,
			"examples_count":  len(filteredExamples),
		},
		"metadata": map[string]interface{}{
			"timestamp": time.Now().Format(time.RFC3339),
		},
	})
}

// Helper methods

func (h *Handlers) respondJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}

func (h *Handlers) respondError(w http.ResponseWriter, status int, message string) {
	h.respondJSON(w, status, map[string]interface{}{
		"error":   true,
		"message": message,
	})
}

// RegisterRoutes registers all symbolic regression routes
func (h *Handlers) RegisterRoutes(r chi.Router) {
	r.Route("/symbolic-regression", func(r chi.Router) {
		// Formula management
		r.Get("/formulas", h.HandleListFormulas)
		r.Get("/formulas/active", h.HandleGetActiveFormula)
		r.Get("/formulas/by-regime", h.HandleGetFormulasByRegime)
		r.Get("/formulas/{id}/metrics", h.HandleGetFormulaMetrics)
		r.Post("/formulas/compare", h.HandleCompareFormulas)
		r.Post("/formulas/{id}/deactivate", h.HandleDeactivateFormula)

		// Discovery
		r.Post("/discover", h.HandleRunDiscovery)

		// Training data
		r.Get("/training-data/{isin}", h.HandleGetTrainingData)
	})
}
