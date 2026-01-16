// Package handlers provides HTTP handlers for universe management.
package handlers

import (
	"github.com/aristath/sentinel/internal/modules/universe"
)

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/scoring/scorers"
	"github.com/aristath/sentinel/pkg/formulas"
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
	Geography          string
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
	Geography          string
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
		Geography:          input.Geography,
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
	log                     zerolog.Logger
	portfolioDB             *sql.DB
	positionRepo            *portfolio.PositionRepository
	securityRepo            *universe.SecurityRepository
	scoreRepo               *universe.ScoreRepository
	overrideRepo            *universe.OverrideRepository
	securityScorer          *scorers.SecurityScorer
	historyDB               universe.HistoryDBInterface
	setupService            *universe.SecuritySetupService
	deletionService         *universe.SecurityDeletionService
	syncService             *universe.SyncService
	currencyExchangeService domain.CurrencyExchangeServiceInterface
	eventManager            *events.Manager
}

// NewUniverseHandlers creates a new universe handlers instance
func NewUniverseHandlers(
	securityRepo *universe.SecurityRepository,
	scoreRepo *universe.ScoreRepository,
	overrideRepo *universe.OverrideRepository,
	portfolioDB *sql.DB,
	positionRepo *portfolio.PositionRepository,
	securityScorer *scorers.SecurityScorer,
	historyDB universe.HistoryDBInterface,
	setupService *universe.SecuritySetupService,
	deletionService *universe.SecurityDeletionService,
	syncService *universe.SyncService,
	currencyExchangeService domain.CurrencyExchangeServiceInterface,
	eventManager *events.Manager,
	log zerolog.Logger,
) *UniverseHandlers {
	return &UniverseHandlers{
		securityRepo:            securityRepo,
		scoreRepo:               scoreRepo,
		overrideRepo:            overrideRepo,
		portfolioDB:             portfolioDB,
		positionRepo:            positionRepo,
		securityScorer:          securityScorer,
		historyDB:               historyDB,
		setupService:            setupService,
		deletionService:         deletionService,
		syncService:             syncService,
		currencyExchangeService: currencyExchangeService,
		eventManager:            eventManager,
		log:                     log.With().Str("module", "universe_handlers").Logger(),
	}
}

// HandleGetStocks returns all securities with scores and priority
// Faithful translation from Python: app/modules/universe/api/securities.py -> get_stocks()
// GET /api/securities
func (h *UniverseHandlers) HandleGetStocks(w http.ResponseWriter, r *http.Request) {
	// Fetch securities with scores from repository
	// This method joins data from config.db (securities), state.db (scores and positions)
	securitiesData, err := h.securityRepo.GetWithScores(h.portfolioDB)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to fetch securities with scores")
		http.Error(w, "Failed to fetch securities", http.StatusInternalServerError)
		return
	}

	// Note: PositionValue is already populated from database's market_value_eur field
	// which is correctly converted to EUR by the portfolio sync service.
	// No additional conversion is needed here.

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
			Geography:          sec.Geography,
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
			"product_type":         sec.ProductType,
			"geography":            sec.Geography,
			"fullExchangeName":     sec.FullExchangeName,
			"industry":             sec.Industry,
			"priority_multiplier":  sec.PriorityMultiplier,
			"min_lot":              sec.MinLot,
			"allow_buy":            sec.AllowBuy,
			"allow_sell":           sec.AllowSell,
			"currency":             sec.Currency,
			"last_synced":          convertUnixToString(sec.LastSynced),
			"min_portfolio_target": sec.MinPortfolioTarget,
			"max_portfolio_target": sec.MaxPortfolioTarget,
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
		if sec.StabilityScore != nil {
			stockDict["stability_score"] = *sec.StabilityScore
		}

		// Add position fields (only if not nil)
		if sec.PositionValue != nil {
			stockDict["position_value"] = *sec.PositionValue
		}
		if sec.PositionQuantity != nil {
			stockDict["position_quantity"] = *sec.PositionQuantity
		}
		if sec.CurrentPrice != nil {
			stockDict["current_price"] = *sec.CurrentPrice
		}

		// Add priority score
		if priority, found := priorityMap[sec.Symbol]; found {
			stockDict["priority_score"] = roundFloat(priority, 3)
		} else {
			stockDict["priority_score"] = 0.0
		}

		// Add tags (read-only, internal only)
		if len(sec.Tags) > 0 {
			stockDict["tags"] = sec.Tags
		} else {
			stockDict["tags"] = []string{}
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
	securityISIN := security.ISIN

	// Get score (using ISIN - primary identifier)
	var score *universe.SecurityScore
	score, err = h.scoreRepo.GetByISIN(securityISIN)
	if err != nil {
		h.log.Error().Err(err).Str("isin", securityISIN).Str("symbol", symbol).Msg("Failed to fetch score")
		// Continue without score rather than failing
		score = nil
	}

	// Build response (client symbols available via /api/securities/{isin}/client-symbols)
	result := map[string]interface{}{
		"symbol":               security.Symbol,
		"isin":                 security.ISIN,
		"name":                 security.Name,
		"product_type":         security.ProductType,
		"industry":             security.Industry,
		"geography":            security.Geography,
		"fullExchangeName":     security.FullExchangeName,
		"priority_multiplier":  security.PriorityMultiplier,
		"min_lot":              security.MinLot,
		"allow_buy":            security.AllowBuy,
		"allow_sell":           security.AllowSell,
		"min_portfolio_target": security.MinPortfolioTarget,
		"max_portfolio_target": security.MaxPortfolioTarget,
		"tags":                 security.Tags, // Read-only, internal only
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
		result["stability_score"] = score.StabilityScore

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
// After migration 030: ISIN is required (PRIMARY KEY)
// Note: User-configurable fields (min_lot, allow_buy, allow_sell, priority_multiplier)
// are set via security_overrides after creation, not during the create operation.
type SecurityCreateRequest struct {
	Symbol string   `json:"symbol"`
	Name   string   `json:"name"`
	ISIN   string   `json:"isin"`           // Required: PRIMARY KEY after migration 030
	Tags   []string `json:"tags,omitempty"` // Ignored - tags are internal only
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
	if req.ISIN == "" {
		// ISIN is required after migration 030 (PRIMARY KEY)
		// Suggest using AddSecurityByIdentifier endpoint which automatically fetches ISIN
		http.Error(w, "ISIN is required (PRIMARY KEY). Use /api/securities/add-by-identifier endpoint to automatically fetch ISIN from Tradernet", http.StatusBadRequest)
		return
	}

	// Ignore tags in create request (tags are internal only, auto-assigned)
	// No need to reject - just ignore them silently
	if len(req.Tags) > 0 {
		h.log.Debug().Str("symbol", req.Symbol).Msg("Tags provided in create request - ignoring (tags are internal only)")
	}

	h.log.Info().
		Str("symbol", req.Symbol).
		Str("name", req.Name).
		Str("isin", req.ISIN).
		Msg("Creating security")

	// Call SecuritySetupService (ISIN is now required)
	// Note: User-configurable fields are set via security_overrides after creation
	security, err := h.setupService.CreateSecurity(
		req.Symbol,
		req.Name,
		req.ISIN,
	)
	if err != nil {
		h.log.Error().Err(err).Str("symbol", req.Symbol).Msg("Failed to create security")
		http.Error(w, fmt.Sprintf("Failed to create security: %v", err), http.StatusInternalServerError)
		return
	}

	// Get the calculated score (using ISIN - primary identifier)
	score, err := h.scoreRepo.GetByISIN(security.ISIN)
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
// Note: User-configurable fields (min_lot, allow_buy, allow_sell) are set via
// security_overrides after creation, not during the add operation.
type AddByIdentifierRequest struct {
	Identifier string `json:"identifier"`
}

// HandleAddStockByIdentifier adds a security to the universe by symbol or ISIN
// POST /api/securities/add-by-identifier
func (h *UniverseHandlers) HandleAddStockByIdentifier(w http.ResponseWriter, r *http.Request) {
	var req AddByIdentifierRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	h.log.Info().
		Str("identifier", req.Identifier).
		Msg("Adding security by identifier")

	if h.setupService == nil {
		h.log.Error().Msg("SecuritySetupService not available")
		http.Error(w, "Service not available", http.StatusInternalServerError)
		return
	}

	// Call SecuritySetupService
	// Note: User-configurable fields are set via security_overrides after creation
	security, err := h.setupService.AddSecurityByIdentifier(req.Identifier)
	if err != nil {
		h.log.Error().Err(err).Str("identifier", req.Identifier).Msg("Failed to add security")

		// Return 503 Service Unavailable if Tradernet is not connected
		// This is more appropriate than 500 Internal Server Error
		errorMsg := strings.ToLower(err.Error())
		if strings.Contains(errorMsg, "tradernet") && strings.Contains(errorMsg, "not connected") {
			// Return a user-friendly error message
			http.Error(w, "Tradernet client is not connected. Please connect to Tradernet first to add securities.", http.StatusServiceUnavailable)
		} else {
			http.Error(w, fmt.Sprintf("Failed to add security: %v", err), http.StatusInternalServerError)
		}
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
		// Note: Industry is now populated from Tradernet metadata during security setup
		// If missing, it will be updated during the next sync cycle

		// Calculate score (client symbols no longer needed for scoring)
		score, err := h.calculateAndSaveScore(security.ISIN, security.Geography, security.Industry)
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

	// Emit SECURITY_SYNCED event
	if h.eventManager != nil {
		h.eventManager.Emit(events.SecuritySynced, "universe", map[string]interface{}{
			"isin":   isin,
			"symbol": symbol,
			"reason": "refresh_data",
		})
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

	// Calculate and save score (client symbols no longer needed for scoring)
	score, err := h.calculateAndSaveScore(security.ISIN, security.Geography, security.Industry)
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
	oldISIN := security.ISIN

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

	// Reject tags in update requests (tags are internal only, auto-assigned)
	if _, hasTags := updates["tags"]; hasTags {
		http.Error(w, "Tags cannot be updated via API - they are internal only and auto-assigned", http.StatusBadRequest)
		return
	}

	// Separate overridable fields from regular fields
	// Overridable fields are stored in security_overrides table
	overridableFields := map[string]bool{
		"allow_buy":           true,
		"allow_sell":          true,
		"min_lot":             true,
		"priority_multiplier": true,
		"geography":           true,
		"industry":            true,
		"name":                true,
		"product_type":        true,
	}

	overrideUpdates := make(map[string]string)
	regularUpdates := make(map[string]interface{})

	for field, value := range updates {
		if overridableFields[field] {
			// Convert to string for override storage
			overrideUpdates[field] = fmt.Sprintf("%v", value)
		} else {
			regularUpdates[field] = value
		}
	}

	// Apply override updates to security_overrides table
	if len(overrideUpdates) > 0 && h.overrideRepo != nil {
		for field, value := range overrideUpdates {
			if err := h.overrideRepo.SetOverride(oldISIN, field, value); err != nil {
				h.log.Error().Err(err).
					Str("isin", oldISIN).
					Str("field", field).
					Msg("Failed to set override")
				http.Error(w, fmt.Sprintf("Failed to set override for %s: %v", field, err), http.StatusInternalServerError)
				return
			}
			h.log.Debug().
				Str("isin", oldISIN).
				Str("field", field).
				Str("value", value).
				Msg("Set security override")
		}
	}

	// Apply regular updates to securities table (only if there are any)
	if len(regularUpdates) > 0 {
		if err := h.securityRepo.Update(oldISIN, regularUpdates); err != nil {
			h.log.Error().Err(err).Str("isin", oldISIN).Str("symbol", oldSymbol).Msg("Failed to update security")

			// Return specific error message for validation errors, generic for others
			errorMsg := "Failed to update security"
			if strings.Contains(err.Error(), "invalid update field") {
				errorMsg = err.Error()
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"message": errorMsg,
				})
				return
			}

			http.Error(w, errorMsg, http.StatusInternalServerError)
			return
		}
	}

	// Get updated security (by ISIN - ISIN doesn't change)
	updatedSecurity, err := h.securityRepo.GetByISIN(oldISIN)
	if err != nil || updatedSecurity == nil {
		h.log.Error().Err(err).Str("isin", oldISIN).Msg("Failed to fetch updated security")
		http.Error(w, "Security not found after update", http.StatusNotFound)
		return
	}

	// Recalculate score (client symbols no longer needed for scoring)
	score, err := h.calculateAndSaveScore(updatedSecurity.ISIN, updatedSecurity.Geography, updatedSecurity.Industry)
	if err != nil {
		h.log.Warn().Err(err).Str("isin", updatedSecurity.ISIN).Str("symbol", updatedSecurity.Symbol).Msg("Failed to recalculate score after update")
		// Continue without score rather than failing the update
	}

	// Client symbols available via /api/securities/{isin}/client-symbols
	response := map[string]interface{}{
		"symbol":              updatedSecurity.Symbol,
		"isin":                updatedSecurity.ISIN,
		"name":                updatedSecurity.Name,
		"product_type":        updatedSecurity.ProductType,
		"industry":            updatedSecurity.Industry,
		"geography":           updatedSecurity.Geography,
		"fullExchangeName":    updatedSecurity.FullExchangeName,
		"priority_multiplier": updatedSecurity.PriorityMultiplier,
		"min_lot":             updatedSecurity.MinLot,
		"allow_buy":           updatedSecurity.AllowBuy,
		"allow_sell":          updatedSecurity.AllowSell,
		"tags":                updatedSecurity.Tags, // Read-only, internal only
	}

	if score != nil {
		response["total_score"] = score.TotalScore
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(response)
}

// HandleDeleteStock hard-deletes a security and all related data
// Returns 409 Conflict if security has open positions
// Returns 404 Not Found if security does not exist
// DELETE /api/securities/{isin}
func (h *UniverseHandlers) HandleDeleteStock(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")
	isin = strings.TrimSpace(strings.ToUpper(isin))

	// Validate ISIN format
	if !isISIN(isin) {
		http.Error(w, "Invalid ISIN format", http.StatusBadRequest)
		return
	}

	h.log.Info().Str("isin", isin).Msg("DELETE request - attempting to hard delete security")

	// Use the deletion service which validates positions and removes all related data
	err := h.deletionService.HardDelete(isin)
	if err != nil {
		errStr := err.Error()
		if strings.Contains(errStr, "open position") || strings.Contains(errStr, "pending order") {
			h.log.Warn().Str("isin", isin).Err(err).Msg("Cannot delete security - active trades")
			http.Error(w, errStr, http.StatusConflict)
			return
		}
		if strings.Contains(errStr, "not found") {
			h.log.Warn().Str("isin", isin).Msg("Security not found")
			http.Error(w, errStr, http.StatusNotFound)
			return
		}
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to delete security")
		http.Error(w, "Failed to delete security", http.StatusInternalServerError)
		return
	}

	h.log.Info().Str("isin", isin).Msg("Security successfully hard deleted")
	w.WriteHeader(http.StatusNoContent)
}

// CalculateAndSaveScore is the public interface implementation for ScoreCalculator
// Wraps the private calculateAndSaveScore method
// After migration: accepts symbol but looks up ISIN internally
// Client symbols are no longer needed for scoring - all data comes from internal sources
func (h *UniverseHandlers) CalculateAndSaveScore(symbol string, geography string, industry string) error {
	// Lookup ISIN from symbol
	security, err := h.securityRepo.GetBySymbol(symbol)
	if err != nil {
		return fmt.Errorf("failed to lookup security: %w", err)
	}
	if security == nil || security.ISIN == "" {
		return fmt.Errorf("security not found or missing ISIN: %s", symbol)
	}
	_, err = h.calculateAndSaveScore(security.ISIN, geography, industry)
	return err
}

// calculateAndSaveScore calculates and saves security score
// All price data comes from internal history.db - no external API calls needed
// After migration: accepts ISIN as primary identifier (first parameter)
func (h *UniverseHandlers) calculateAndSaveScore(isin string, geography string, industry string) (*universe.SecurityScore, error) {
	// Get security by ISIN to extract symbol
	security, err := h.securityRepo.GetByISIN(isin)
	if err != nil {
		return nil, fmt.Errorf("failed to get security: %w", err)
	}
	if security == nil {
		return nil, fmt.Errorf("security not found: %s", isin)
	}
	symbol := security.Symbol

	// Fetch price data from history database using ISIN
	dailyPrices, err := h.historyDB.GetDailyPrices(isin, 400)
	if err != nil {
		return nil, fmt.Errorf("failed to get daily prices: %w", err)
	}

	if len(dailyPrices) < 30 {
		return nil, fmt.Errorf("insufficient daily data: %d days (need at least 30)", len(dailyPrices))
	}

	monthlyPrices, err := h.historyDB.GetMonthlyPrices(isin, 150)
	if err != nil {
		return nil, fmt.Errorf("failed to get monthly prices: %w", err)
	}

	if len(monthlyPrices) < 6 {
		return nil, fmt.Errorf("insufficient monthly data: %d months (need at least 6)", len(monthlyPrices))
	}

	// Note: Stability is now calculated from price data via StabilityScorer
	// No external data fetching required

	// Convert data formats for scoring service
	// Extract close prices from daily data
	closePrices := make([]float64, len(dailyPrices))
	for i, dp := range dailyPrices {
		closePrices[i] = dp.Close
	}

	// Convert monthly prices to formulas.MonthlyPrice format
	// GetMonthlyPrices returns DESC order (newest first), but CalculateCAGR expects ASC (oldest first)
	// Reverse the slice to fix the order
	monthlyPricesConverted := make([]formulas.MonthlyPrice, len(monthlyPrices))
	for i, mp := range monthlyPrices {
		// Reverse index: newest first -> oldest first
		reversedIdx := len(monthlyPrices) - 1 - i
		monthlyPricesConverted[reversedIdx] = formulas.MonthlyPrice{
			YearMonth:   mp.YearMonth,
			AvgAdjClose: mp.AvgAdjClose,
		}
	}

	// Build scoring input
	scoringInput := scorers.ScoreSecurityInput{
		Symbol:        symbol,
		ProductType:   security.ProductType, // Pass product type for product-type-aware scoring
		MarketCode:    security.MarketCode,  // Pass market code for per-region regime scoring
		DailyPrices:   closePrices,
		MonthlyPrices: monthlyPricesConverted,
	}

	// Add geography and industry for allocation fit scoring
	if geography != "" {
		scoringInput.Geography = &geography
	}
	if industry != "" {
		scoringInput.Industry = &industry
	}

	// Call scoring service
	calculatedScore := h.securityScorer.ScoreSecurityWithDefaults(scoringInput)

	// Convert calculated score to SecurityScore for database storage (using ISIN)
	score := universe.ConvertToSecurityScore(isin, symbol, calculatedScore)

	// Save score to database
	if err := h.scoreRepo.Upsert(score); err != nil {
		return nil, fmt.Errorf("failed to save score: %w", err)
	}

	// Emit SCORE_UPDATED event
	if h.eventManager != nil {
		h.eventManager.Emit(events.ScoreUpdated, "universe", map[string]interface{}{
			"isin":        isin,
			"symbol":      symbol,
			"total_score": score.TotalScore,
		})
	}

	h.log.Info().Str("isin", isin).Str("symbol", symbol).Float64("score", score.TotalScore).Msg("Score calculated and saved")
	return &score, nil
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

	// Emit SECURITY_SYNCED event after successful sync
	if h.eventManager != nil {
		h.eventManager.Emit(events.SecuritySynced, "universe", map[string]interface{}{
			"processed": processed,
			"errors":    errors,
			"reason":    "sync_securities_data",
		})
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

// convertUnixToString converts Unix timestamp to RFC3339 string for API
func convertUnixToString(ts *int64) string {
	if ts == nil {
		return ""
	}
	t := time.Unix(*ts, 0).UTC()
	return t.Format(time.RFC3339)
}

// HandleGetSecurityOverrides returns all overrides for a specific security
// GET /api/securities/{isin}/overrides
func (h *UniverseHandlers) HandleGetSecurityOverrides(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")
	isin = strings.TrimSpace(strings.ToUpper(isin))

	// Validate ISIN format
	if !isISIN(isin) {
		http.Error(w, "Invalid ISIN format", http.StatusBadRequest)
		return
	}

	// Check if security exists
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

	// Get overrides for this security
	if h.overrideRepo == nil {
		// No override repo - return empty map (all defaults)
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{})
		return
	}

	overrides, err := h.overrideRepo.GetOverrides(isin)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to fetch overrides")
		http.Error(w, "Failed to fetch overrides", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(overrides)
}

// HandleDeleteSecurityOverride deletes a specific override field for a security,
// reverting it to the default value
// DELETE /api/securities/{isin}/overrides/{field}
func (h *UniverseHandlers) HandleDeleteSecurityOverride(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")
	isin = strings.TrimSpace(strings.ToUpper(isin))

	field := chi.URLParam(r, "field")
	field = strings.TrimSpace(strings.ToLower(field))

	// Validate ISIN format
	if !isISIN(isin) {
		http.Error(w, "Invalid ISIN format", http.StatusBadRequest)
		return
	}

	if field == "" {
		http.Error(w, "Field name is required", http.StatusBadRequest)
		return
	}

	h.log.Info().Str("isin", isin).Str("field", field).Msg("Deleting security override")

	// Check if security exists
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

	// Delete the override
	if h.overrideRepo == nil {
		http.Error(w, "Override repository not configured", http.StatusInternalServerError)
		return
	}

	err = h.overrideRepo.DeleteOverride(isin, field)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Str("field", field).Msg("Failed to delete override")
		http.Error(w, "Failed to delete override", http.StatusInternalServerError)
		return
	}

	h.log.Info().Str("isin", isin).Str("field", field).Msg("Override deleted successfully")

	// Return the updated security (with default applied for deleted field)
	updatedSecurity, err := h.securityRepo.GetByISIN(isin)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to fetch updated security")
		http.Error(w, "Failed to fetch updated security", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	response := map[string]interface{}{
		"message":  fmt.Sprintf("Override for '%s' deleted successfully", field),
		"security": updatedSecurity,
	}
	_ = json.NewEncoder(w).Encode(response)
}

// HandleSetSecurityOverride sets or updates a specific override field for a security
// PUT /api/securities/{isin}/overrides/{field}
func (h *UniverseHandlers) HandleSetSecurityOverride(w http.ResponseWriter, r *http.Request) {
	isin := chi.URLParam(r, "isin")
	isin = strings.TrimSpace(strings.ToUpper(isin))

	field := chi.URLParam(r, "field")
	field = strings.TrimSpace(strings.ToLower(field))

	// Validate ISIN format
	if !isISIN(isin) {
		http.Error(w, "Invalid ISIN format", http.StatusBadRequest)
		return
	}

	if field == "" {
		http.Error(w, "Field name is required", http.StatusBadRequest)
		return
	}

	// Parse request body
	var req struct {
		Value string `json:"value"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	h.log.Info().Str("isin", isin).Str("field", field).Str("value", req.Value).Msg("Setting security override")

	// Check if security exists
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

	// Set the override
	if h.overrideRepo == nil {
		http.Error(w, "Override repository not configured", http.StatusInternalServerError)
		return
	}

	err = h.overrideRepo.SetOverride(isin, field, req.Value)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Str("field", field).Msg("Failed to set override")
		http.Error(w, "Failed to set override", http.StatusInternalServerError)
		return
	}

	h.log.Info().Str("isin", isin).Str("field", field).Str("value", req.Value).Msg("Override set successfully")

	// Return the updated security (with new override applied)
	updatedSecurity, err := h.securityRepo.GetByISIN(isin)
	if err != nil {
		h.log.Error().Err(err).Str("isin", isin).Msg("Failed to fetch updated security")
		http.Error(w, "Failed to fetch updated security", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	response := map[string]interface{}{
		"message":  fmt.Sprintf("Override for '%s' set successfully", field),
		"security": updatedSecurity,
	}
	_ = json.NewEncoder(w).Encode(response)
}
