package universe

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"regexp"
	"sort"
	"strings"

	"github.com/aristath/arduino-trader/internal/clients/yahoo"
	"github.com/aristath/arduino-trader/internal/modules/scoring/domain"
	"github.com/aristath/arduino-trader/internal/modules/scoring/scorers"
	"github.com/aristath/arduino-trader/pkg/formulas"
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
	Volatility         *float64
	QualityScore       *float64
	OpportunityScore   *float64
	AllocationFitScore *float64
	Symbol             string
	Name               string
	Country            string
	Industry           string
	StockScore         float64
	Multiplier         float64
}

// PriorityResult represents the result of priority calculation
// Faithful translation from Python: app/modules/universe/domain/priority_calculator.py -> PriorityResult
type PriorityResult struct {
	Volatility         *float64
	QualityScore       *float64
	OpportunityScore   *float64
	AllocationFitScore *float64
	Symbol             string
	Name               string
	Country            string
	Industry           string
	StockScore         float64
	Multiplier         float64
	CombinedPriority   float64
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
	log            zerolog.Logger
	portfolioDB    interface{}
	positionRepo   interface{}
	securityRepo   *SecurityRepository
	scoreRepo      *ScoreRepository
	securityScorer *scorers.SecurityScorer
	yahooClient    *yahoo.Client
	historyDB      *HistoryDB
	setupService   *SecuritySetupService
	syncService    *SyncService
	pythonURL      string
}

// NewUniverseHandlers creates a new universe handlers instance
func NewUniverseHandlers(
	securityRepo *SecurityRepository,
	scoreRepo *ScoreRepository,
	portfolioDB interface{},
	positionRepo interface{},
	securityScorer *scorers.SecurityScorer,
	yahooClient *yahoo.Client,
	historyDB *HistoryDB,
	setupService *SecuritySetupService,
	syncService *SyncService,
	pythonURL string,
	log zerolog.Logger,
) *UniverseHandlers {
	return &UniverseHandlers{
		securityRepo:   securityRepo,
		scoreRepo:      scoreRepo,
		portfolioDB:    portfolioDB,
		positionRepo:   positionRepo,
		securityScorer: securityScorer,
		yahooClient:    yahooClient,
		historyDB:      historyDB,
		setupService:   setupService,
		syncService:    syncService,
		pythonURL:      pythonURL,
		log:            log.With().Str("module", "universe_handlers").Logger(),
	}
}

// HandleGetStocks returns all securities with scores and priority
// Faithful translation from Python: app/modules/universe/api/securities.py -> get_stocks()
// GET /api/securities
func (h *UniverseHandlers) HandleGetStocks(w http.ResponseWriter, r *http.Request) {
	// Fetch securities with scores from repository
	// This method joins data from config.db (securities), state.db (scores and positions)
	// Type assertion for portfolioDB
	portfolioDB, ok := h.portfolioDB.(*sql.DB)
	if !ok {
		h.log.Error().Msg("Invalid portfolioDB type")
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	securitiesData, err := h.securityRepo.GetWithScores(portfolioDB)
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

// SecurityCreateRequest represents the request to create a security
type SecurityCreateRequest struct {
	Symbol      string `json:"symbol"`
	Name        string `json:"name"`
	YahooSymbol string `json:"yahoo_symbol"`
	MinLot      int    `json:"min_lot"`
	AllowBuy    bool   `json:"allow_buy"`
	AllowSell   bool   `json:"allow_sell"`
}

// HandleCreateStock creates a new security in the universe
// POST /api/securities
func (h *UniverseHandlers) HandleCreateStock(w http.ResponseWriter, r *http.Request) {
	var req SecurityCreateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate required fields
	if req.Symbol == "" {
		http.Error(w, "Symbol is required", http.StatusBadRequest)
		return
	}
	if req.Name == "" {
		http.Error(w, "Name is required", http.StatusBadRequest)
		return
	}

	// Set defaults
	if req.MinLot == 0 {
		req.MinLot = 1
	}

	h.log.Info().
		Str("symbol", req.Symbol).
		Str("name", req.Name).
		Int("min_lot", req.MinLot).
		Bool("allow_buy", req.AllowBuy).
		Bool("allow_sell", req.AllowSell).
		Msg("Creating security")

	// Call SecuritySetupService
	security, err := h.setupService.CreateSecurity(
		req.Symbol,
		req.Name,
		req.YahooSymbol,
		req.MinLot,
		req.AllowBuy,
		req.AllowSell,
	)
	if err != nil {
		h.log.Error().Err(err).Str("symbol", req.Symbol).Msg("Failed to create security")
		http.Error(w, fmt.Sprintf("Failed to create security: %v", err), http.StatusInternalServerError)
		return
	}

	// Get the calculated score
	score, err := h.scoreRepo.GetBySymbol(security.Symbol)
	if err != nil {
		h.log.Warn().Err(err).Str("symbol", security.Symbol).Msg("Failed to get score")
	}

	w.Header().Set("Content-Type", "application/json")
	response := map[string]interface{}{
		"message":  fmt.Sprintf("Security %s added successfully", security.Symbol),
		"security": security,
	}
	if score != nil {
		response["score"] = score
	}
	_ = json.NewEncoder(w).Encode(response)
}

// AddByIdentifierRequest represents the request to add a security by identifier
type AddByIdentifierRequest struct {
	Identifier string `json:"identifier"`
	MinLot     int    `json:"min_lot"`
	AllowBuy   bool   `json:"allow_buy"`
	AllowSell  bool   `json:"allow_sell"`
}

// HandleAddStockByIdentifier adds a security to the universe by symbol or ISIN
// POST /api/securities/add-by-identifier
func (h *UniverseHandlers) HandleAddStockByIdentifier(w http.ResponseWriter, r *http.Request) {
	var req AddByIdentifierRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Set defaults
	if req.MinLot == 0 {
		req.MinLot = 1
	}

	h.log.Info().
		Str("identifier", req.Identifier).
		Int("min_lot", req.MinLot).
		Bool("allow_buy", req.AllowBuy).
		Bool("allow_sell", req.AllowSell).
		Msg("Adding security by identifier")

	if h.setupService == nil {
		h.log.Error().Msg("SecuritySetupService not available")
		http.Error(w, "Service not available", http.StatusInternalServerError)
		return
	}

	// Call SecuritySetupService
	security, err := h.setupService.AddSecurityByIdentifier(
		req.Identifier,
		req.MinLot,
		req.AllowBuy,
		req.AllowSell,
	)
	if err != nil {
		h.log.Error().Err(err).Str("identifier", req.Identifier).Msg("Failed to add security")
		http.Error(w, fmt.Sprintf("Failed to add security: %v", err), http.StatusInternalServerError)
		return
	}

	h.log.Info().
		Str("symbol", security.Symbol).
		Str("identifier", req.Identifier).
		Msg("Security added successfully")

	w.Header().Set("Content-Type", "application/json")
	response := map[string]interface{}{
		"message":  fmt.Sprintf("Security %s added successfully", security.Symbol),
		"security": security,
	}
	_ = json.NewEncoder(w).Encode(response)
}

// HandleRefreshAllScores recalculates scores for all active securities
// POST /api/securities/refresh-all
func (h *UniverseHandlers) HandleRefreshAllScores(w http.ResponseWriter, r *http.Request) {
	h.log.Info().Msg("Refreshing all security scores")

	// Get all active securities
	securities, err := h.securityRepo.GetAllActive()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get active securities")
		http.Error(w, "Failed to get securities", http.StatusInternalServerError)
		return
	}

	// Score all securities
	var scoredCount int
	var scores []map[string]interface{}

	for _, security := range securities {
		// Update industry if missing
		if security.Industry == "" {
			if industry, err := h.yahooClient.GetSecurityIndustry(security.Symbol, &security.YahooSymbol); err == nil && industry != nil {
				_ = h.securityRepo.Update(security.Symbol, map[string]interface{}{"industry": *industry})
				h.log.Info().Str("symbol", security.Symbol).Str("industry", *industry).Msg("Updated missing industry")
			}
		}

		// Calculate score
		score, err := h.calculateAndSaveScore(security.Symbol, security.YahooSymbol, security.Country, security.Industry)
		if err != nil {
			h.log.Warn().Err(err).Str("symbol", security.Symbol).Msg("Failed to calculate score")
			continue
		}

		if score != nil {
			scoredCount++
			scores = append(scores, map[string]interface{}{
				"symbol":      security.Symbol,
				"total_score": score.TotalScore,
			})
		}
	}

	h.log.Info().Int("scored_count", scoredCount).Int("total_securities", len(securities)).Msg("Score refresh complete")

	response := map[string]interface{}{
		"message": fmt.Sprintf("Refreshed scores for %d stocks", scoredCount),
		"scores":  scores,
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(response)
}

// HandleRefreshSecurityData proxies to Python for full data refresh
// POST /api/securities/{isin}/refresh-data
func (h *UniverseHandlers) HandleRefreshSecurityData(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")

	// Validate ISIN format
	isin = strings.TrimSpace(strings.ToUpper(isin))
	if !isISIN(isin) {
		http.Error(w, "Invalid ISIN format", http.StatusBadRequest)
		return
	}

	h.log.Info().Str("isin", isin).Msg("Refreshing security data")

	// Get security by ISIN
	security, err := h.securityRepo.GetByISIN(isin)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to get security")
		http.Error(w, fmt.Sprintf("Failed to get security: %v", err), http.StatusInternalServerError)
		return
	}
	if security == nil {
		http.Error(w, "Security not found", http.StatusNotFound)
		return
	}

	symbol := security.Symbol

	// Call SecuritySetupService to refresh data
	err = h.setupService.RefreshSecurityData(symbol)
	if err != nil {
		h.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to refresh security data")
		http.Error(w, fmt.Sprintf("Data refresh failed: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	response := map[string]interface{}{
		"status":  "success",
		"symbol":  symbol,
		"message": fmt.Sprintf("Full data refresh completed for %s", symbol),
	}
	_ = json.NewEncoder(w).Encode(response)
}

// HandleRefreshStockScore recalculates score for a single security
// POST /api/securities/{isin}/refresh
func (h *UniverseHandlers) HandleRefreshStockScore(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")
	isin = strings.TrimSpace(strings.ToUpper(isin))

	// Validate ISIN format
	if !isISIN(isin) {
		http.Error(w, "Invalid ISIN format", http.StatusBadRequest)
		return
	}

	h.log.Info().Str("isin", isin).Msg("Refreshing security score")

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

	// Calculate and save score
	score, err := h.calculateAndSaveScore(symbol, security.YahooSymbol, security.Country, security.Industry)
	if err != nil {
		h.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to calculate score")
		http.Error(w, "Failed to calculate score", http.StatusInternalServerError)
		return
	}

	if score == nil {
		http.Error(w, "Failed to calculate score", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"symbol":            symbol,
		"total_score":       score.TotalScore,
		"quality":           score.QualityScore,
		"opportunity":       score.OpportunityScore,
		"analyst":           score.AnalystScore,
		"allocation_fit":    score.AllocationFitScore,
		"volatility":        score.Volatility,
		"cagr_score":        score.CAGRScore,
		"consistency_score": score.ConsistencyScore,
		"history_years":     score.HistoryYears,
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(response)
}

// HandleUpdateStock updates security details and recalculates score
// PUT /api/securities/{isin}
func (h *UniverseHandlers) HandleUpdateStock(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")
	isin = strings.TrimSpace(strings.ToUpper(isin))

	// Validate ISIN format
	if !isISIN(isin) {
		http.Error(w, "Invalid ISIN format", http.StatusBadRequest)
		return
	}

	h.log.Info().Str("isin", isin).Msg("Updating security")

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

	oldSymbol := security.Symbol

	// Parse update request
	var updates map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&updates); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if len(updates) == 0 {
		http.Error(w, "No updates provided", http.StatusBadRequest)
		return
	}

	// Apply updates
	if err := h.securityRepo.Update(oldSymbol, updates); err != nil {
		h.log.Error().Err(err).Str("symbol", oldSymbol).Msg("Failed to update security")
		http.Error(w, "Failed to update security", http.StatusInternalServerError)
		return
	}

	// Get updated security
	finalSymbol := oldSymbol
	if newSymbol, ok := updates["symbol"].(string); ok && newSymbol != oldSymbol {
		finalSymbol = newSymbol
	}

	updatedSecurity, err := h.securityRepo.GetBySymbol(finalSymbol)
	if err != nil || updatedSecurity == nil {
		h.log.Error().Err(err).Str("symbol", finalSymbol).Msg("Failed to fetch updated security")
		http.Error(w, "Security not found after update", http.StatusNotFound)
		return
	}

	// Recalculate score
	score, err := h.calculateAndSaveScore(finalSymbol, updatedSecurity.YahooSymbol, updatedSecurity.Country, updatedSecurity.Industry)
	if err != nil {
		h.log.Warn().Err(err).Str("symbol", finalSymbol).Msg("Failed to recalculate score after update")
		// Continue without score rather than failing the update
	}

	response := map[string]interface{}{
		"symbol":              updatedSecurity.Symbol,
		"isin":                updatedSecurity.ISIN,
		"yahoo_symbol":        updatedSecurity.YahooSymbol,
		"name":                updatedSecurity.Name,
		"industry":            updatedSecurity.Industry,
		"country":             updatedSecurity.Country,
		"fullExchangeName":    updatedSecurity.FullExchangeName,
		"priority_multiplier": updatedSecurity.PriorityMultiplier,
		"min_lot":             updatedSecurity.MinLot,
		"active":              updatedSecurity.Active,
		"allow_buy":           updatedSecurity.AllowBuy,
		"allow_sell":          updatedSecurity.AllowSell,
	}

	if score != nil {
		response["total_score"] = score.TotalScore
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(response)
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

// CalculateAndSaveScore is the public interface implementation for ScoreCalculator
// Wraps the private calculateAndSaveScore method
func (h *UniverseHandlers) CalculateAndSaveScore(symbol string, yahooSymbol string, country string, industry string) error {
	_, err := h.calculateAndSaveScore(symbol, yahooSymbol, country, industry)
	return err
}

// calculateAndSaveScore calculates and saves security score
// Faithful translation from Python: app/modules/scoring/services/scoring_service.py -> calculate_and_save_score
func (h *UniverseHandlers) calculateAndSaveScore(symbol string, yahooSymbol string, country string, industry string) (*SecurityScore, error) {
	// Fetch price data from history database
	dailyPrices, err := h.historyDB.GetDailyPrices(symbol, 400)
	if err != nil {
		return nil, fmt.Errorf("failed to get daily prices: %w", err)
	}

	if len(dailyPrices) < 50 {
		return nil, fmt.Errorf("insufficient daily data: %d days (need at least 50)", len(dailyPrices))
	}

	monthlyPrices, err := h.historyDB.GetMonthlyPrices(symbol, 150)
	if err != nil {
		return nil, fmt.Errorf("failed to get monthly prices: %w", err)
	}

	if len(monthlyPrices) < 12 {
		return nil, fmt.Errorf("insufficient monthly data: %d months (need at least 12)", len(monthlyPrices))
	}

	// Fetch fundamentals from Yahoo Finance
	var yahooSymPtr *string
	if yahooSymbol != "" {
		yahooSymPtr = &yahooSymbol
	}

	fundamentalsData, err := h.yahooClient.GetFundamentalData(symbol, yahooSymPtr)
	if err != nil {
		h.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to get fundamental data, continuing without it")
		// Continue without fundamentals - scoring can work with just price data
	}

	// Convert data formats for scoring service
	// Extract close prices from daily data
	closePrices := make([]float64, len(dailyPrices))
	for i, dp := range dailyPrices {
		closePrices[i] = dp.Close
	}

	// Convert monthly prices to formulas.MonthlyPrice format
	monthlyPricesConverted := make([]formulas.MonthlyPrice, len(monthlyPrices))
	for i, mp := range monthlyPrices {
		monthlyPricesConverted[i] = formulas.MonthlyPrice{
			YearMonth:   mp.YearMonth,
			AvgAdjClose: mp.AvgAdjClose,
		}
	}

	// Build scoring input
	scoringInput := scorers.ScoreSecurityInput{
		Symbol:        symbol,
		DailyPrices:   closePrices,
		MonthlyPrices: monthlyPricesConverted,
	}

	// Add fundamentals if available
	if fundamentalsData != nil {
		scoringInput.PERatio = fundamentalsData.PERatio
		scoringInput.ForwardPE = fundamentalsData.ForwardPE
		scoringInput.DividendYield = fundamentalsData.DividendYield
		scoringInput.FiveYearAvgDivYield = fundamentalsData.FiveYearAvgDividendYield
		scoringInput.ProfitMargin = fundamentalsData.ProfitMargin
		scoringInput.DebtToEquity = fundamentalsData.DebtToEquity
		scoringInput.CurrentRatio = fundamentalsData.CurrentRatio
	}

	// Add country and industry for allocation fit scoring
	if country != "" {
		scoringInput.Country = &country
	}
	if industry != "" {
		scoringInput.Industry = &industry
	}

	// Call scoring service
	calculatedScore := h.securityScorer.ScoreSecurityWithDefaults(scoringInput)

	// Convert calculated score to SecurityScore for database storage
	score := convertToSecurityScore(symbol, calculatedScore)

	// Save score to database
	if err := h.scoreRepo.Upsert(score); err != nil {
		return nil, fmt.Errorf("failed to save score: %w", err)
	}

	h.log.Info().Str("symbol", symbol).Float64("score", score.TotalScore).Msg("Score calculated and saved")
	return &score, nil
}

// convertToSecurityScore converts domain.CalculatedSecurityScore to SecurityScore
func convertToSecurityScore(symbol string, calculated *domain.CalculatedSecurityScore) SecurityScore {
	// Extract group scores
	groupScores := calculated.GroupScores
	if groupScores == nil {
		groupScores = make(map[string]float64)
	}

	// Calculate quality score as average of long_term and fundamentals
	qualityScore := 0.0
	if longTerm, ok := groupScores["long_term"]; ok {
		if fundamentals, ok2 := groupScores["fundamentals"]; ok2 {
			qualityScore = (longTerm + fundamentals) / 2
		} else {
			qualityScore = longTerm
		}
	} else if fundamentals, ok := groupScores["fundamentals"]; ok {
		qualityScore = fundamentals
	}

	// Extract sub-scores
	subScores := calculated.SubScores
	var cagrScore, consistencyScore float64
	if subScores != nil {
		if longTermSubs, ok := subScores["long_term"]; ok {
			if cagr, ok := longTermSubs["cagr"]; ok {
				cagrScore = cagr
			}
		}
		if fundamentalsSubs, ok := subScores["fundamentals"]; ok {
			if consistency, ok := fundamentalsSubs["consistency"]; ok {
				consistencyScore = consistency
			}
		}
	}

	// Approximate history years
	historyYears := 0.0
	if cagrScore > 0 {
		historyYears = 5.0
	}

	volatility := 0.0
	if calculated.Volatility != nil {
		volatility = *calculated.Volatility
	}

	return SecurityScore{
		Symbol:                 symbol,
		QualityScore:           qualityScore,
		OpportunityScore:       groupScores["opportunity"],
		AnalystScore:           groupScores["opinion"],
		AllocationFitScore:     groupScores["diversification"],
		CAGRScore:              cagrScore,
		ConsistencyScore:       consistencyScore,
		HistoryYears:           historyYears,
		TechnicalScore:         groupScores["technicals"],
		FundamentalScore:       groupScores["fundamentals"],
		TotalScore:             calculated.TotalScore,
		Volatility:             volatility,
		FinancialStrengthScore: 0, // Not in current domain model
		SharpeScore:            0, // Not in current domain model
		DrawdownScore:          0, // Not in current domain model
		DividendBonus:          0, // Not in current domain model
		RSI:                    0, // Not in current domain model
		EMA200:                 0, // Not in current domain model
		Below52wHighPct:        0, // Not in current domain model
		SellScore:              0, // Not in current domain model
	}
}

// HandleSyncPrices triggers manual price sync for all active securities
// Endpoint: POST /api/universe/sync/prices
func (h *UniverseHandlers) HandleSyncPrices(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Info().Msg("Manual price sync triggered")

	// Call SyncService
	quotesCount, err := h.syncService.SyncAllPrices()
	if err != nil {
		h.log.Error().Err(err).Msg("Price sync failed")
		http.Error(w, fmt.Sprintf("Price sync failed: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	response := map[string]interface{}{
		"status":  "success",
		"message": "Price sync completed",
		"quotes":  quotesCount,
	}
	_ = json.NewEncoder(w).Encode(response)
}

// HandleSyncHistorical triggers manual historical data sync
// Endpoint: POST /api/universe/sync/historical
func (h *UniverseHandlers) HandleSyncHistorical(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Info().Msg("Manual historical data sync triggered")

	// Call SyncService
	processed, errors, err := h.syncService.SyncAllHistoricalData()
	if err != nil {
		h.log.Error().Err(err).Msg("Historical data sync failed")
		http.Error(w, fmt.Sprintf("Historical data sync failed: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	response := map[string]interface{}{
		"status":    "success",
		"message":   "Historical data sync completed",
		"processed": processed,
		"errors":    errors,
	}
	_ = json.NewEncoder(w).Encode(response)
}

// HandleRebuildUniverse rebuilds universe from portfolio and populates all databases
// Endpoint: POST /api/universe/sync/rebuild-universe
func (h *UniverseHandlers) HandleRebuildUniverse(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Info().Msg("Universe rebuild from portfolio triggered")

	// Call SyncService
	addedCount, err := h.syncService.RebuildUniverseFromPortfolio()
	if err != nil {
		h.log.Error().Err(err).Msg("Universe rebuild failed")
		http.Error(w, fmt.Sprintf("Universe rebuild failed: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	response := map[string]interface{}{
		"status":  "success",
		"message": "Universe rebuild completed",
		"added":   addedCount,
	}
	_ = json.NewEncoder(w).Encode(response)
}

// HandleSyncSecuritiesData triggers securities data sync (historical, industry, metrics, scores)
// Endpoint: POST /api/universe/sync/securities-data
func (h *UniverseHandlers) HandleSyncSecuritiesData(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Info().Msg("Manual securities data sync triggered")

	// Call SyncService
	processed, errors, err := h.syncService.SyncSecuritiesData()
	if err != nil {
		h.log.Error().Err(err).Msg("Securities data sync failed")
		http.Error(w, fmt.Sprintf("Securities data sync failed: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	response := map[string]interface{}{
		"status":    "success",
		"message":   "Securities data sync completed",
		"processed": processed,
		"errors":    errors,
	}
	_ = json.NewEncoder(w).Encode(response)
}
