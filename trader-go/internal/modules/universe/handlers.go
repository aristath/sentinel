package universe

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// ISIN validation pattern
var isinPattern = regexp.MustCompile(`^[A-Z]{2}[A-Z0-9]{9}[0-9]$`)

// isISIN checks if identifier is a valid ISIN
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> is_isin()
func isISIN(identifier string) bool {
	identifier = strings.TrimSpace(strings.ToUpper(identifier))
	if len(identifier) != 12 {
		return false
	}
	return isinPattern.MatchString(identifier)
}

// PriorityInput represents input data for priority calculation
// Faithful translation from Python: app/modules/universe/domain/priority_calculator.py -> PriorityInput
type PriorityInput struct {
	Symbol             string
	Name               string
	StockScore         float64
	Multiplier         float64
	Country            string
	Industry           string
	Volatility         *float64
	QualityScore       *float64
	OpportunityScore   *float64
	AllocationFitScore *float64
}

// PriorityResult represents the result of priority calculation
// Faithful translation from Python: app/modules/universe/domain/priority_calculator.py -> PriorityResult
type PriorityResult struct {
	Symbol             string
	Name               string
	StockScore         float64
	Multiplier         float64
	CombinedPriority   float64
	Country            string
	Industry           string
	Volatility         *float64
	QualityScore       *float64
	OpportunityScore   *float64
	AllocationFitScore *float64
}

// calculatePriority calculates priority score for a security
// Faithful translation from Python: PriorityCalculator.calculate_priority()
func calculatePriority(input PriorityInput) PriorityResult {
	// The security score already includes all factors from scorer.py
	// Just apply the manual multiplier
	combinedPriority := input.StockScore * input.Multiplier

	return PriorityResult{
		Symbol:             input.Symbol,
		Name:               input.Name,
		Country:            input.Country,
		Industry:           input.Industry,
		StockScore:         input.StockScore,
		Volatility:         input.Volatility,
		Multiplier:         input.Multiplier,
		CombinedPriority:   roundFloat(combinedPriority, 4),
		QualityScore:       input.QualityScore,
		OpportunityScore:   input.OpportunityScore,
		AllocationFitScore: input.AllocationFitScore,
	}
}

// calculatePriorities calculates priorities for multiple securities
// Faithful translation from Python: PriorityCalculator.calculate_priorities()
func calculatePriorities(inputs []PriorityInput) []PriorityResult {
	results := make([]PriorityResult, len(inputs))
	for i, input := range inputs {
		results[i] = calculatePriority(input)
	}

	// Sort by combined priority (highest first)
	sort.Slice(results, func(i, j int) bool {
		return results[i].CombinedPriority > results[j].CombinedPriority
	})

	return results
}

// roundFloat rounds a float to a specific number of decimal places
func roundFloat(val float64, precision int) float64 {
	multiplier := 1.0
	for i := 0; i < precision; i++ {
		multiplier *= 10
	}
	return float64(int(val*multiplier+0.5)) / multiplier
}

// UniverseHandlers contains HTTP handlers for universe API
type UniverseHandlers struct {
	securityRepo *SecurityRepository
	scoreRepo    *ScoreRepository
	stateDB      interface{} // sql.DB for state.db (passed to GetWithScores)
	positionRepo interface{} // Will be *portfolio.PositionRepository when wired
	pythonURL    string      // URL of Python service for proxied endpoints
	log          zerolog.Logger
}

// NewUniverseHandlers creates a new universe handlers instance
func NewUniverseHandlers(
	securityRepo *SecurityRepository,
	scoreRepo *ScoreRepository,
	stateDB interface{},
	positionRepo interface{},
	pythonURL string,
	log zerolog.Logger,
) *UniverseHandlers {
	return &UniverseHandlers{
		securityRepo: securityRepo,
		scoreRepo:    scoreRepo,
		stateDB:      stateDB,
		positionRepo: positionRepo,
		pythonURL:    pythonURL,
		log:          log.With().Str("module", "universe_handlers").Logger(),
	}
}

// HandleGetStocks returns all securities with scores and priority
// Faithful translation from Python: app/modules/universe/api/securities.py -> get_stocks()
// GET /api/securities
func (h *UniverseHandlers) HandleGetStocks(w http.ResponseWriter, r *http.Request) {
	// Fetch securities with scores from repository
	// This method joins data from config.db (securities), state.db (scores and positions)
	// Type assertion for stateDB
	stateDB, ok := h.stateDB.(*sql.DB)
	if !ok {
		h.log.Error().Msg("Invalid stateDB type")
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	securitiesData, err := h.securityRepo.GetWithScores(stateDB)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to fetch securities with scores")
		http.Error(w, "Failed to fetch securities", http.StatusInternalServerError)
		return
	}

	// Prepare priority inputs
	priorityInputs := make([]PriorityInput, 0, len(securitiesData))

	for _, sec := range securitiesData {
		stockScore := 0.0
		if sec.TotalScore != nil {
			stockScore = *sec.TotalScore
		}

		multiplier := sec.PriorityMultiplier
		if multiplier == 0 {
			multiplier = 1.0
		}

		priorityInputs = append(priorityInputs, PriorityInput{
			Symbol:             sec.Symbol,
			Name:               sec.Name,
			Country:            sec.Country,
			Industry:           sec.Industry,
			StockScore:         stockScore,
			Volatility:         sec.Volatility,
			Multiplier:         multiplier,
			QualityScore:       sec.QualityScore,
			OpportunityScore:   sec.OpportunityScore,
			AllocationFitScore: sec.AllocationFitScore,
		})
	}

	// Calculate priorities
	priorityResults := calculatePriorities(priorityInputs)

	// Build priority map for quick lookup
	priorityMap := make(map[string]float64)
	for _, pr := range priorityResults {
		priorityMap[pr.Symbol] = pr.CombinedPriority
	}

	// Convert to response format (map[string]interface{} to match Python's dict response)
	response := make([]map[string]interface{}, 0, len(securitiesData))
	for _, sec := range securitiesData {
		stockDict := map[string]interface{}{
			"symbol":               sec.Symbol,
			"name":                 sec.Name,
			"isin":                 sec.ISIN,
			"yahoo_symbol":         sec.YahooSymbol,
			"product_type":         sec.ProductType,
			"country":              sec.Country,
			"fullExchangeName":     sec.FullExchangeName,
			"industry":             sec.Industry,
			"priority_multiplier":  sec.PriorityMultiplier,
			"min_lot":              sec.MinLot,
			"active":               sec.Active,
			"allow_buy":            sec.AllowBuy,
			"allow_sell":           sec.AllowSell,
			"currency":             sec.Currency,
			"last_synced":          sec.LastSynced,
			"min_portfolio_target": sec.MinPortfolioTarget,
			"max_portfolio_target": sec.MaxPortfolioTarget,
			"bucket_id":            sec.BucketID,
		}

		// Add score fields (only if not nil)
		if sec.QualityScore != nil {
			stockDict["quality_score"] = *sec.QualityScore
		}
		if sec.OpportunityScore != nil {
			stockDict["opportunity_score"] = *sec.OpportunityScore
		}
		if sec.AnalystScore != nil {
			stockDict["analyst_score"] = *sec.AnalystScore
		}
		if sec.AllocationFitScore != nil {
			stockDict["allocation_fit_score"] = *sec.AllocationFitScore
		}
		if sec.TotalScore != nil {
			stockDict["total_score"] = *sec.TotalScore
		}
		if sec.CAGRScore != nil {
			stockDict["cagr_score"] = *sec.CAGRScore
		}
		if sec.ConsistencyScore != nil {
			stockDict["consistency_score"] = *sec.ConsistencyScore
		}
		if sec.HistoryYears != nil {
			stockDict["history_years"] = *sec.HistoryYears
		}
		if sec.Volatility != nil {
			stockDict["volatility"] = *sec.Volatility
		}
		if sec.TechnicalScore != nil {
			stockDict["technical_score"] = *sec.TechnicalScore
		}
		if sec.FundamentalScore != nil {
			stockDict["fundamental_score"] = *sec.FundamentalScore
		}

		// Add position fields (only if not nil)
		if sec.PositionValue != nil {
			stockDict["position_value"] = *sec.PositionValue
		}
		if sec.PositionQuantity != nil {
			stockDict["position_quantity"] = *sec.PositionQuantity
		}

		// Add priority score
		if priority, found := priorityMap[sec.Symbol]; found {
			stockDict["priority_score"] = roundFloat(priority, 3)
		} else {
			stockDict["priority_score"] = 0.0
		}

		response = append(response, stockDict)
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(response) // Ignore encode error - already committed response
}

// HandleGetStock returns detailed security info with score breakdown
// Faithful translation from Python: app/modules/universe/api/securities.py -> get_stock()
// GET /api/securities/{isin}
func (h *UniverseHandlers) HandleGetStock(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")
	isin = strings.TrimSpace(strings.ToUpper(isin))

	// Validate ISIN format
	if !isISIN(isin) {
		http.Error(w, "Invalid ISIN format", http.StatusBadRequest)
		return
	}

	// Get security by ISIN
	security, err := h.securityRepo.GetByISIN(isin)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to fetch security")
		http.Error(w, "Failed to fetch security", http.StatusInternalServerError)
		return
	}
	if security == nil {
		http.Error(w, "Security not found", http.StatusNotFound)
		return
	}

	symbol := security.Symbol

	// Get score
	score, err := h.scoreRepo.GetBySymbol(symbol)
	if err != nil {
		h.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to fetch score")
		// Continue without score rather than failing
		score = nil
	}

	// Build response
	result := map[string]interface{}{
		"symbol":               security.Symbol,
		"isin":                 security.ISIN,
		"yahoo_symbol":         security.YahooSymbol,
		"name":                 security.Name,
		"industry":             security.Industry,
		"country":              security.Country,
		"fullExchangeName":     security.FullExchangeName,
		"priority_multiplier":  security.PriorityMultiplier,
		"min_lot":              security.MinLot,
		"active":               security.Active,
		"allow_buy":            security.AllowBuy,
		"allow_sell":           security.AllowSell,
		"min_portfolio_target": security.MinPortfolioTarget,
		"max_portfolio_target": security.MaxPortfolioTarget,
	}

	// Add score data if available
	if score != nil {
		result["quality_score"] = score.QualityScore
		result["opportunity_score"] = score.OpportunityScore
		result["analyst_score"] = score.AnalystScore
		result["allocation_fit_score"] = score.AllocationFitScore
		result["total_score"] = score.TotalScore
		result["cagr_score"] = score.CAGRScore
		result["consistency_score"] = score.ConsistencyScore
		result["history_years"] = score.HistoryYears
		result["volatility"] = score.Volatility
		result["technical_score"] = score.TechnicalScore
		result["fundamental_score"] = score.FundamentalScore

		if score.CalculatedAt != nil {
			result["calculated_at"] = score.CalculatedAt.Format("2006-01-02T15:04:05Z07:00")
		} else {
			result["calculated_at"] = nil
		}
	}

	// Position data would be fetched here when position repo is wired
	// For now, set to nil
	result["position"] = nil

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(result) // Ignore encode error - already committed response
}

// HandleCreateStock proxies to Python for security creation
// POST /api/securities
func (h *UniverseHandlers) HandleCreateStock(w http.ResponseWriter, r *http.Request) {
	// Proxy to Python - requires Yahoo Finance integration
	h.proxyToPython(w, r, "/api/securities")
}

// HandleAddStockByIdentifier proxies to Python for auto-setup by identifier
// POST /api/securities/add-by-identifier
func (h *UniverseHandlers) HandleAddStockByIdentifier(w http.ResponseWriter, r *http.Request) {
	// Proxy to Python - requires Tradernet + Yahoo Finance + scoring
	h.proxyToPython(w, r, "/api/securities/add-by-identifier")
}

// HandleRefreshAllScores proxies to Python for score recalculation
// POST /api/securities/refresh-all
func (h *UniverseHandlers) HandleRefreshAllScores(w http.ResponseWriter, r *http.Request) {
	// Proxy to Python - requires scoring service
	h.proxyToPython(w, r, "/api/securities/refresh-all")
}

// HandleRefreshSecurityData proxies to Python for full data refresh
// POST /api/securities/{isin}/refresh-data
func (h *UniverseHandlers) HandleRefreshSecurityData(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")
	h.log.Info().Str("isin", isin).Msg("Proxying refresh data request to Python")
	// Proxy to Python - requires full pipeline (Yahoo sync + scoring)
	h.proxyToPython(w, r, fmt.Sprintf("/api/securities/%s/refresh-data", isin))
}

// HandleRefreshStockScore proxies to Python for single score refresh
// POST /api/securities/{isin}/refresh
func (h *UniverseHandlers) HandleRefreshStockScore(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")
	h.log.Info().Str("isin", isin).Msg("Proxying refresh score request to Python")
	// Proxy to Python - requires scoring service
	h.proxyToPython(w, r, fmt.Sprintf("/api/securities/%s/refresh", isin))
}

// HandleUpdateStock proxies to Python for security update
// PUT /api/securities/{isin}
func (h *UniverseHandlers) HandleUpdateStock(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")
	h.log.Info().Str("isin", isin).Msg("Proxying update request to Python")
	// Proxy to Python - requires score recalculation
	h.proxyToPython(w, r, fmt.Sprintf("/api/securities/%s", isin))
}

// HandleDeleteStock soft-deletes a security (sets active=0)
// DELETE /api/securities/{isin}
func (h *UniverseHandlers) HandleDeleteStock(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")
	isin = strings.TrimSpace(strings.ToUpper(isin))

	// Validate ISIN format
	if !isISIN(isin) {
		http.Error(w, "Invalid ISIN format", http.StatusBadRequest)
		return
	}

	h.log.Info().Str("isin", isin).Msg("DELETE request - attempting to delete security")

	// Get security by ISIN
	security, err := h.securityRepo.GetByISIN(isin)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to fetch security")
		http.Error(w, "Failed to fetch security", http.StatusInternalServerError)
		return
	}
	if security == nil {
		h.log.Warn().Str("isin", isin).Msg("Security not found")
		http.Error(w, "Security not found", http.StatusNotFound)
		return
	}

	symbol := security.Symbol
	h.log.Info().Str("isin", isin).Str("symbol", symbol).Msg("Soft deleting security (setting active=0)")

	// Soft delete (set active=0)
	err = h.securityRepo.Delete(symbol)
	if err != nil {
		h.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to delete security")
		http.Error(w, "Failed to delete security", http.StatusInternalServerError)
		return
	}

	h.log.Info().Str("isin", isin).Str("symbol", symbol).Msg("Security successfully deleted")

	response := map[string]string{
		"message": fmt.Sprintf("Security %s removed from universe", symbol),
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(response) // Ignore encode error - already committed response
}

// Helper methods

// proxyToPython forwards the request to the Python service
// Supports GET, POST, PUT, DELETE methods and forwards request body
func (h *UniverseHandlers) proxyToPython(w http.ResponseWriter, r *http.Request, path string) {
	url := h.pythonURL + path

	// Read request body if present
	var body []byte
	var err error
	if r.Body != nil {
		body, err = io.ReadAll(r.Body)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to read request body")
			http.Error(w, "Failed to read request body", http.StatusInternalServerError)
			return
		}
	}

	// Create new request with same method and body
	req, err := http.NewRequest(r.Method, url, bytes.NewReader(body))
	if err != nil {
		h.log.Error().Err(err).Str("url", url).Msg("Failed to create proxy request")
		http.Error(w, "Failed to create proxy request", http.StatusInternalServerError)
		return
	}

	// Copy headers
	req.Header.Set("Content-Type", "application/json")
	for key, values := range r.Header {
		for _, value := range values {
			req.Header.Add(key, value)
		}
	}

	// Execute request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		h.log.Error().Err(err).Str("url", url).Msg("Failed to contact Python service")
		http.Error(w, "Failed to contact Python service", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	// Read response body
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to read Python response")
		http.Error(w, "Failed to read Python response", http.StatusInternalServerError)
		return
	}

	// Copy response headers
	for key, values := range resp.Header {
		for _, value := range values {
			w.Header().Add(key, value)
		}
	}

	// Write response
	w.WriteHeader(resp.StatusCode)
	_, _ = w.Write(respBody) // Ignore write error - already committed response
}
