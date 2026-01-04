package satellites

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// Handlers provides HTTP handlers for satellites API endpoints.
//
// Faithful translation from Python: app/modules/satellites/api/satellites.py
type Handlers struct {
	bucketService         *BucketService
	balanceService        *BalanceService
	reconciliationService *ReconciliationService
	log                   zerolog.Logger
}

// NewHandlers creates a new handlers instance
func NewHandlers(
	bucketService *BucketService,
	balanceService *BalanceService,
	reconciliationService *ReconciliationService,
	log zerolog.Logger,
) *Handlers {
	return &Handlers{
		bucketService:         bucketService,
		balanceService:        balanceService,
		reconciliationService: reconciliationService,
		log:                   log,
	}
}

// ============================================================================
// Helper Functions
// ============================================================================

// respondJSON sends a JSON response
func respondJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(data); err != nil {
		// Log encoding error but don't change response
	}
}

// respondError sends an error response
func respondError(w http.ResponseWriter, status int, message string) {
	respondJSON(w, status, map[string]string{"error": message})
}

// decodeJSON decodes JSON from request body
func decodeJSON(r *http.Request, v interface{}) error {
	return json.NewDecoder(r.Body).Decode(v)
}

// ============================================================================
// Request/Response Models
// ============================================================================

// CreateSatelliteRequest represents request to create a new satellite bucket
type CreateSatelliteRequest struct {
	ID              string  `json:"id"`
	Name            string  `json:"name"`
	Notes           *string `json:"notes"`
	StartInResearch bool    `json:"start_in_research"`
}

// UpdateBucketRequest represents request to update bucket fields
type UpdateBucketRequest struct {
	Name      *string  `json:"name"`
	Notes     *string  `json:"notes"`
	TargetPct *float64 `json:"target_pct"`
	MinPct    *float64 `json:"min_pct"`
	MaxPct    *float64 `json:"max_pct"`
}

// SatelliteSettingsRequest represents request to update satellite settings
type SatelliteSettingsRequest struct {
	Preset              *string `json:"preset"`
	RiskAppetite        float64 `json:"risk_appetite"`
	HoldDuration        float64 `json:"hold_duration"`
	EntryStyle          float64 `json:"entry_style"`
	PositionSpread      float64 `json:"position_spread"`
	ProfitTaking        float64 `json:"profit_taking"`
	TrailingStops       bool    `json:"trailing_stops"`
	FollowRegime        bool    `json:"follow_regime"`
	AutoHarvest         bool    `json:"auto_harvest"`
	PauseHighVolatility bool    `json:"pause_high_volatility"`
	DividendHandling    string  `json:"dividend_handling"`
	// Risk metric parameters
	RiskFreeRate         float64 `json:"risk_free_rate"`
	SortinoMAR           float64 `json:"sortino_mar"`
	EvaluationPeriodDays int     `json:"evaluation_period_days"`
	VolatilityWindow     int     `json:"volatility_window"`
}

// TransferRequest represents request to transfer cash between buckets
type TransferRequest struct {
	FromBucketID string  `json:"from_bucket_id"`
	ToBucketID   string  `json:"to_bucket_id"`
	Amount       float64 `json:"amount"`
	Currency     string  `json:"currency"`
	Description  *string `json:"description"`
}

// DepositRequest represents request to allocate a deposit
type DepositRequest struct {
	Amount      float64 `json:"amount"`
	Currency    string  `json:"currency"`
	Description *string `json:"description"`
}

// ReconcileRequest represents request to reconcile balances
type ReconcileRequest struct {
	Currency             string   `json:"currency"`
	ActualBalance        float64  `json:"actual_balance"`
	AutoCorrectThreshold *float64 `json:"auto_correct_threshold"`
}

// BucketResponse represents response model for a bucket
type BucketResponse struct {
	ID                   string   `json:"id"`
	Name                 string   `json:"name"`
	Type                 string   `json:"type"`
	Status               string   `json:"status"`
	Notes                *string  `json:"notes,omitempty"`
	TargetPct            *float64 `json:"target_pct,omitempty"`
	MinPct               *float64 `json:"min_pct,omitempty"`
	MaxPct               *float64 `json:"max_pct,omitempty"`
	ConsecutiveLosses    int      `json:"consecutive_losses"`
	MaxConsecutiveLosses int      `json:"max_consecutive_losses"`
	HighWaterMark        float64  `json:"high_water_mark"`
	HighWaterMarkDate    *string  `json:"high_water_mark_date,omitempty"`
	LossStreakPausedAt   *string  `json:"loss_streak_paused_at,omitempty"`
	CreatedAt            *string  `json:"created_at,omitempty"`
	UpdatedAt            *string  `json:"updated_at,omitempty"`
}

// BalanceResponse represents response model for a bucket balance
type BalanceResponse struct {
	BucketID    string  `json:"bucket_id"`
	Currency    string  `json:"currency"`
	Balance     float64 `json:"balance"`
	LastUpdated string  `json:"last_updated"`
}

// TransactionResponse represents response model for a transaction
type TransactionResponse struct {
	ID          *int64  `json:"id,omitempty"`
	BucketID    string  `json:"bucket_id"`
	Type        string  `json:"type"`
	Amount      float64 `json:"amount"`
	Currency    string  `json:"currency"`
	Description *string `json:"description,omitempty"`
	CreatedAt   string  `json:"created_at"`
}

// SettingsResponse represents response model for satellite settings
type SettingsResponse struct {
	SatelliteID         string  `json:"satellite_id"`
	Preset              *string `json:"preset,omitempty"`
	RiskAppetite        float64 `json:"risk_appetite"`
	HoldDuration        float64 `json:"hold_duration"`
	EntryStyle          float64 `json:"entry_style"`
	PositionSpread      float64 `json:"position_spread"`
	ProfitTaking        float64 `json:"profit_taking"`
	TrailingStops       bool    `json:"trailing_stops"`
	FollowRegime        bool    `json:"follow_regime"`
	AutoHarvest         bool    `json:"auto_harvest"`
	PauseHighVolatility bool    `json:"pause_high_volatility"`
	DividendHandling    string  `json:"dividend_handling"`
	// Risk metric parameters
	RiskFreeRate         float64 `json:"risk_free_rate"`
	SortinoMAR           float64 `json:"sortino_mar"`
	EvaluationPeriodDays int     `json:"evaluation_period_days"`
	VolatilityWindow     int     `json:"volatility_window"`
}

// ReconciliationResultResponse represents response model for reconciliation result
type ReconciliationResultResponse struct {
	Currency        string             `json:"currency"`
	VirtualTotal    float64            `json:"virtual_total"`
	ActualTotal     float64            `json:"actual_total"`
	Difference      float64            `json:"difference"`
	IsReconciled    bool               `json:"is_reconciled"`
	AdjustmentsMade map[string]float64 `json:"adjustments_made"`
	Timestamp       string             `json:"timestamp"`
}

// Helper to convert bucket to response
func bucketToResponse(b *Bucket) *BucketResponse {
	return &BucketResponse{
		ID:                   b.ID,
		Name:                 b.Name,
		Type:                 string(b.Type),
		Status:               string(b.Status),
		Notes:                b.Notes,
		TargetPct:            b.TargetPct,
		MinPct:               b.MinPct,
		MaxPct:               b.MaxPct,
		ConsecutiveLosses:    b.ConsecutiveLosses,
		MaxConsecutiveLosses: b.MaxConsecutiveLosses,
		HighWaterMark:        b.HighWaterMark,
		HighWaterMarkDate:    b.HighWaterMarkDate,
		LossStreakPausedAt:   b.LossStreakPausedAt,
		CreatedAt:            &b.CreatedAt,
		UpdatedAt:            &b.UpdatedAt,
	}
}

// ============================================================================
// Bucket CRUD Endpoints
// ============================================================================

// ListBuckets handles GET /buckets
func (h *Handlers) ListBuckets(w http.ResponseWriter, r *http.Request) {
	buckets, err := h.bucketService.GetAllBuckets()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to list buckets")
		respondJSON(w, http.StatusInternalServerError, map[string]interface{}{
			"error":  "Failed to list buckets",
			"detail": err.Error(),
		})
		return
	}

	responses := make([]*BucketResponse, len(buckets))
	for i, bucket := range buckets {
		responses[i] = bucketToResponse(bucket)
	}

	respondJSON(w, http.StatusOK, responses)
}

// GetBucket handles GET /buckets/:bucket_id
func (h *Handlers) GetBucket(w http.ResponseWriter, r *http.Request) {
	bucketID := chi.URLParam(r, "bucket_id")

	bucket, err := h.bucketService.GetBucket(bucketID)
	if err != nil {
		h.log.Error().Err(err).Str("bucket_id", bucketID).Msg("Failed to get bucket")
		respondError(w, http.StatusInternalServerError, "Failed to get bucket")
		return
	}

	if bucket == nil {
		respondError(w, http.StatusNotFound, "Bucket '"+bucketID+"' not found")
		return
	}

	respondJSON(w, http.StatusOK, bucketToResponse(bucket))
}

// CreateSatellite handles POST /satellites
func (h *Handlers) CreateSatellite(w http.ResponseWriter, r *http.Request) {
	var req CreateSatelliteRequest
	if err := decodeJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	bucket, err := h.bucketService.CreateSatellite(req.ID, req.Name, req.Notes, req.StartInResearch)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to create satellite")
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusCreated, bucketToResponse(bucket))
}

// UpdateBucket handles PATCH /buckets/:bucket_id
func (h *Handlers) UpdateBucket(w http.ResponseWriter, r *http.Request) {
	bucketID := chi.URLParam(r, "bucket_id")

	var req UpdateBucketRequest
	if err := decodeJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	// Build updates map
	updates := make(map[string]interface{})
	if req.Name != nil {
		updates["name"] = *req.Name
	}
	if req.Notes != nil {
		updates["notes"] = *req.Notes
	}
	if req.TargetPct != nil {
		updates["target_pct"] = *req.TargetPct
	}
	if req.MinPct != nil {
		updates["min_pct"] = *req.MinPct
	}
	if req.MaxPct != nil {
		updates["max_pct"] = *req.MaxPct
	}

	if len(updates) == 0 {
		respondError(w, http.StatusBadRequest, "No fields to update")
		return
	}

	bucket, err := h.bucketService.UpdateBucket(bucketID, updates)
	if err != nil {
		h.log.Error().Err(err).Str("bucket_id", bucketID).Msg("Failed to update bucket")
		respondError(w, http.StatusInternalServerError, "Failed to update bucket")
		return
	}

	if bucket == nil {
		respondError(w, http.StatusNotFound, "Bucket '"+bucketID+"' not found")
		return
	}

	respondJSON(w, http.StatusOK, bucketToResponse(bucket))
}

// ============================================================================
// Lifecycle Endpoints
// ============================================================================

// ActivateSatellite handles POST /satellites/:satellite_id/activate
func (h *Handlers) ActivateSatellite(w http.ResponseWriter, r *http.Request) {
	satelliteID := chi.URLParam(r, "satellite_id")

	bucket, err := h.bucketService.ActivateSatellite(satelliteID)
	if err != nil {
		h.log.Error().Err(err).Str("satellite_id", satelliteID).Msg("Failed to activate satellite")
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, bucketToResponse(bucket))
}

// PauseBucket handles POST /buckets/:bucket_id/pause
func (h *Handlers) PauseBucket(w http.ResponseWriter, r *http.Request) {
	bucketID := chi.URLParam(r, "bucket_id")

	bucket, err := h.bucketService.PauseBucket(bucketID)
	if err != nil {
		h.log.Error().Err(err).Str("bucket_id", bucketID).Msg("Failed to pause bucket")
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, bucketToResponse(bucket))
}

// ResumeBucket handles POST /buckets/:bucket_id/resume
func (h *Handlers) ResumeBucket(w http.ResponseWriter, r *http.Request) {
	bucketID := chi.URLParam(r, "bucket_id")

	bucket, err := h.bucketService.ResumeBucket(bucketID)
	if err != nil {
		h.log.Error().Err(err).Str("bucket_id", bucketID).Msg("Failed to resume bucket")
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, bucketToResponse(bucket))
}

// RetireSatellite handles POST /satellites/:satellite_id/retire
func (h *Handlers) RetireSatellite(w http.ResponseWriter, r *http.Request) {
	satelliteID := chi.URLParam(r, "satellite_id")

	bucket, err := h.bucketService.RetireSatellite(satelliteID)
	if err != nil {
		h.log.Error().Err(err).Str("satellite_id", satelliteID).Msg("Failed to retire satellite")
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, bucketToResponse(bucket))
}

// ============================================================================
// Settings Endpoints
// ============================================================================

// GetSatelliteSettings handles GET /satellites/:satellite_id/settings
func (h *Handlers) GetSatelliteSettings(w http.ResponseWriter, r *http.Request) {
	satelliteID := chi.URLParam(r, "satellite_id")

	settings, err := h.bucketService.GetSettings(satelliteID)
	if err != nil {
		h.log.Error().Err(err).Str("satellite_id", satelliteID).Msg("Failed to get settings")
		respondError(w, http.StatusInternalServerError, "Failed to get settings")
		return
	}

	if settings == nil {
		respondError(w, http.StatusNotFound, "Settings for satellite '"+satelliteID+"' not found")
		return
	}

	respondJSON(w, http.StatusOK, &SettingsResponse{
		SatelliteID:          settings.SatelliteID,
		Preset:               settings.Preset,
		RiskAppetite:         settings.RiskAppetite,
		HoldDuration:         settings.HoldDuration,
		EntryStyle:           settings.EntryStyle,
		PositionSpread:       settings.PositionSpread,
		ProfitTaking:         settings.ProfitTaking,
		TrailingStops:        settings.TrailingStops,
		FollowRegime:         settings.FollowRegime,
		AutoHarvest:          settings.AutoHarvest,
		PauseHighVolatility:  settings.PauseHighVolatility,
		DividendHandling:     settings.DividendHandling,
		RiskFreeRate:         settings.RiskFreeRate,
		SortinoMAR:           settings.SortinoMAR,
		EvaluationPeriodDays: settings.EvaluationPeriodDays,
		VolatilityWindow:     settings.VolatilityWindow,
	})
}

// UpdateSatelliteSettings handles PUT /satellites/:satellite_id/settings
func (h *Handlers) UpdateSatelliteSettings(w http.ResponseWriter, r *http.Request) {
	satelliteID := chi.URLParam(r, "satellite_id")

	var req SatelliteSettingsRequest
	if err := decodeJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	settings := &SatelliteSettings{
		SatelliteID:          satelliteID,
		Preset:               req.Preset,
		RiskAppetite:         req.RiskAppetite,
		HoldDuration:         req.HoldDuration,
		EntryStyle:           req.EntryStyle,
		PositionSpread:       req.PositionSpread,
		ProfitTaking:         req.ProfitTaking,
		TrailingStops:        req.TrailingStops,
		FollowRegime:         req.FollowRegime,
		AutoHarvest:          req.AutoHarvest,
		PauseHighVolatility:  req.PauseHighVolatility,
		DividendHandling:     req.DividendHandling,
		RiskFreeRate:         req.RiskFreeRate,
		SortinoMAR:           req.SortinoMAR,
		EvaluationPeriodDays: req.EvaluationPeriodDays,
		VolatilityWindow:     req.VolatilityWindow,
	}

	saved, err := h.bucketService.SaveSettings(settings)
	if err != nil {
		h.log.Error().Err(err).Str("satellite_id", satelliteID).Msg("Failed to save settings")
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, &SettingsResponse{
		SatelliteID:         saved.SatelliteID,
		Preset:              saved.Preset,
		RiskAppetite:        saved.RiskAppetite,
		HoldDuration:        saved.HoldDuration,
		EntryStyle:          saved.EntryStyle,
		PositionSpread:      saved.PositionSpread,
		ProfitTaking:        saved.ProfitTaking,
		TrailingStops:       saved.TrailingStops,
		FollowRegime:        saved.FollowRegime,
		AutoHarvest:         saved.AutoHarvest,
		PauseHighVolatility: saved.PauseHighVolatility,
		DividendHandling:    saved.DividendHandling,
	})
}

// ============================================================================
// Balance Endpoints
// ============================================================================

// GetBucketBalances handles GET /buckets/:bucket_id/balances
func (h *Handlers) GetBucketBalances(w http.ResponseWriter, r *http.Request) {
	bucketID := chi.URLParam(r, "bucket_id")

	balances, err := h.balanceService.GetAllBalances(bucketID)
	if err != nil {
		h.log.Error().Err(err).Str("bucket_id", bucketID).Msg("Failed to get balances")
		respondError(w, http.StatusInternalServerError, "Failed to get balances")
		return
	}

	responses := make([]*BalanceResponse, len(balances))
	for i, balance := range balances {
		responses[i] = &BalanceResponse{
			BucketID:    balance.BucketID,
			Currency:    balance.Currency,
			Balance:     balance.Balance,
			LastUpdated: balance.LastUpdated,
		}
	}

	respondJSON(w, http.StatusOK, responses)
}

// GetBalanceSummary handles GET /balances/summary
func (h *Handlers) GetBalanceSummary(w http.ResponseWriter, r *http.Request) {
	summary, err := h.balanceService.GetPortfolioSummary()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get balance summary")
		respondJSON(w, http.StatusInternalServerError, map[string]interface{}{
			"error":  "Failed to get balance summary",
			"detail": err.Error(),
		})
		return
	}

	respondJSON(w, http.StatusOK, summary)
}

// TransferBetweenBuckets handles POST /balances/transfer
func (h *Handlers) TransferBetweenBuckets(w http.ResponseWriter, r *http.Request) {
	var req TransferRequest
	if err := decodeJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	// Default currency if not specified
	currency := req.Currency
	if currency == "" {
		currency = "EUR"
	}

	fromBalance, toBalance, err := h.balanceService.TransferBetweenBuckets(
		req.FromBucketID,
		req.ToBucketID,
		req.Amount,
		currency,
		req.Description,
	)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to transfer between buckets")
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, map[string]interface{}{
		"from_balance": &BalanceResponse{
			BucketID:    fromBalance.BucketID,
			Currency:    fromBalance.Currency,
			Balance:     fromBalance.Balance,
			LastUpdated: fromBalance.LastUpdated,
		},
		"to_balance": &BalanceResponse{
			BucketID:    toBalance.BucketID,
			Currency:    toBalance.Currency,
			Balance:     toBalance.Balance,
			LastUpdated: toBalance.LastUpdated,
		},
	})
}

// AllocateDeposit handles POST /balances/deposit
func (h *Handlers) AllocateDeposit(w http.ResponseWriter, r *http.Request) {
	var req DepositRequest
	if err := decodeJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	// Default currency if not specified
	currency := req.Currency
	if currency == "" {
		currency = "EUR"
	}

	allocations, err := h.balanceService.AllocateDeposit(req.Amount, currency, req.Description)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to allocate deposit")
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, map[string]interface{}{"allocations": allocations})
}

// ============================================================================
// Transaction History Endpoints
// ============================================================================

// GetBucketTransactions handles GET /buckets/:bucket_id/transactions
func (h *Handlers) GetBucketTransactions(w http.ResponseWriter, r *http.Request) {
	bucketID := chi.URLParam(r, "bucket_id")

	// Get query parameters
	limit := 100
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil {
			limit = parsed
		}
	}

	var txType *TransactionType
	if typeStr := r.URL.Query().Get("transaction_type"); typeStr != "" {
		tt := TransactionType(typeStr)
		txType = &tt
	}

	transactions, err := h.balanceService.GetTransactions(bucketID, limit, 0, txType)
	if err != nil {
		h.log.Error().Err(err).Str("bucket_id", bucketID).Msg("Failed to get transactions")
		respondError(w, http.StatusInternalServerError, "Failed to get transactions")
		return
	}

	responses := make([]*TransactionResponse, len(transactions))
	for i, tx := range transactions {
		responses[i] = &TransactionResponse{
			ID:          tx.ID,
			BucketID:    tx.BucketID,
			Type:        string(tx.Type),
			Amount:      tx.Amount,
			Currency:    tx.Currency,
			Description: tx.Description,
			CreatedAt:   tx.CreatedAt,
		}
	}

	respondJSON(w, http.StatusOK, responses)
}

// ============================================================================
// Reconciliation Endpoints
// ============================================================================

// ReconcileBalances handles POST /reconcile
func (h *Handlers) ReconcileBalances(w http.ResponseWriter, r *http.Request) {
	var req ReconcileRequest
	if err := decodeJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	result, err := h.reconciliationService.Reconcile(req.Currency, req.ActualBalance, req.AutoCorrectThreshold)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to reconcile balances")
		respondError(w, http.StatusInternalServerError, "Failed to reconcile balances")
		return
	}

	respondJSON(w, http.StatusOK, &ReconciliationResultResponse{
		Currency:        result.Currency,
		VirtualTotal:    result.VirtualTotal,
		ActualTotal:     result.ActualTotal,
		Difference:      result.Difference,
		IsReconciled:    result.IsReconciled,
		AdjustmentsMade: result.AdjustmentsMade,
		Timestamp:       result.Timestamp,
	})
}

// CheckReconciliation handles GET /reconcile/:currency/check
func (h *Handlers) CheckReconciliation(w http.ResponseWriter, r *http.Request) {
	currency := chi.URLParam(r, "currency")

	actualBalance := 0.0
	if balStr := r.URL.Query().Get("actual_balance"); balStr != "" {
		if parsed, err := strconv.ParseFloat(balStr, 64); err == nil {
			actualBalance = parsed
		}
	}

	result, err := h.reconciliationService.CheckInvariant(currency, actualBalance)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to check reconciliation")
		respondError(w, http.StatusInternalServerError, "Failed to check reconciliation")
		return
	}

	respondJSON(w, http.StatusOK, &ReconciliationResultResponse{
		Currency:        result.Currency,
		VirtualTotal:    result.VirtualTotal,
		ActualTotal:     result.ActualTotal,
		Difference:      result.Difference,
		IsReconciled:    result.IsReconciled,
		AdjustmentsMade: result.AdjustmentsMade,
		Timestamp:       result.Timestamp,
	})
}

// GetBalanceBreakdown handles GET /reconcile/:currency/breakdown
func (h *Handlers) GetBalanceBreakdown(w http.ResponseWriter, r *http.Request) {
	currency := chi.URLParam(r, "currency")

	breakdown, err := h.reconciliationService.GetBalanceBreakdown(currency)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get balance breakdown")
		respondError(w, http.StatusInternalServerError, "Failed to get balance breakdown")
		return
	}

	respondJSON(w, http.StatusOK, breakdown)
}

// ============================================================================
// Allocation Settings Endpoints
// ============================================================================

// GetAllocationSettings handles GET /settings/allocation
func (h *Handlers) GetAllocationSettings(w http.ResponseWriter, r *http.Request) {
	settings, err := h.balanceService.GetAllocationSettings()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get allocation settings")
		respondError(w, http.StatusInternalServerError, "Failed to get allocation settings")
		return
	}

	respondJSON(w, http.StatusOK, settings)
}

// UpdateSatelliteBudget handles PUT /settings/satellite-budget
func (h *Handlers) UpdateSatelliteBudget(w http.ResponseWriter, r *http.Request) {
	budgetPct := 0.0
	if pctStr := r.URL.Query().Get("budget_pct"); pctStr != "" {
		if parsed, err := strconv.ParseFloat(pctStr, 64); err == nil {
			budgetPct = parsed
		}
	}

	err := h.balanceService.UpdateSatelliteBudget(budgetPct)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to update satellite budget")
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, map[string]float64{"satellite_budget_pct": budgetPct})
}

// ============================================================================
// Preset Endpoints
// ============================================================================

// ApplyStrategyPreset handles POST /satellites/:satellite_id/apply-preset
func (h *Handlers) ApplyStrategyPreset(w http.ResponseWriter, r *http.Request) {
	satelliteID := chi.URLParam(r, "satellite_id")
	presetName := r.URL.Query().Get("preset_name")

	if presetName == "" {
		respondError(w, http.StatusBadRequest, "preset_name query parameter required")
		return
	}

	// Create new settings for the satellite
	settings := NewSatelliteSettings(satelliteID)

	// Apply preset to settings
	err := ApplyPresetToSettings(settings, presetName)
	if err != nil {
		respondError(w, http.StatusBadRequest, "Invalid preset: "+presetName)
		return
	}

	// Save settings
	saved, err := h.bucketService.SaveSettings(settings)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to apply preset")
		respondError(w, http.StatusInternalServerError, "Failed to apply preset: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, &SettingsResponse{
		SatelliteID:         saved.SatelliteID,
		Preset:              saved.Preset,
		RiskAppetite:        saved.RiskAppetite,
		HoldDuration:        saved.HoldDuration,
		EntryStyle:          saved.EntryStyle,
		PositionSpread:      saved.PositionSpread,
		ProfitTaking:        saved.ProfitTaking,
		TrailingStops:       saved.TrailingStops,
		FollowRegime:        saved.FollowRegime,
		AutoHarvest:         saved.AutoHarvest,
		PauseHighVolatility: saved.PauseHighVolatility,
		DividendHandling:    saved.DividendHandling,
	})
}

// ListStrategyPresets handles GET /presets
func (h *Handlers) ListStrategyPresets(w http.ResponseWriter, r *http.Request) {
	presets := ListPresets()
	responses := make([]map[string]string, len(presets))

	for i, presetName := range presets {
		description, _ := GetPresetDescription(presetName)
		responses[i] = map[string]string{
			"name":        presetName,
			"description": description,
		}
	}

	respondJSON(w, http.StatusOK, map[string]interface{}{"presets": responses})
}

// RegisterRoutes registers all satellite routes to the router
func (h *Handlers) RegisterRoutes(r chi.Router) {
	r.Route("/satellites", func(r chi.Router) {
		// Bucket CRUD
		r.Get("/buckets", h.ListBuckets)
		r.Get("/buckets/{bucket_id}", h.GetBucket)
		r.Post("/satellites", h.CreateSatellite)
		r.Patch("/buckets/{bucket_id}", h.UpdateBucket)

		// Lifecycle
		r.Post("/satellites/{satellite_id}/activate", h.ActivateSatellite)
		r.Post("/buckets/{bucket_id}/pause", h.PauseBucket)
		r.Post("/buckets/{bucket_id}/resume", h.ResumeBucket)
		r.Post("/satellites/{satellite_id}/retire", h.RetireSatellite)

		// Settings
		r.Get("/satellites/{satellite_id}/settings", h.GetSatelliteSettings)
		r.Put("/satellites/{satellite_id}/settings", h.UpdateSatelliteSettings)

		// Balances
		r.Get("/buckets/{bucket_id}/balances", h.GetBucketBalances)
		r.Get("/balances/summary", h.GetBalanceSummary)
		r.Post("/balances/transfer", h.TransferBetweenBuckets)
		r.Post("/balances/deposit", h.AllocateDeposit)

		// Transactions
		r.Get("/buckets/{bucket_id}/transactions", h.GetBucketTransactions)

		// Reconciliation
		r.Post("/reconcile", h.ReconcileBalances)
		r.Get("/reconcile/{currency}/check", h.CheckReconciliation)
		r.Get("/reconcile/{currency}/breakdown", h.GetBalanceBreakdown)

		// Settings
		r.Get("/settings/allocation", h.GetAllocationSettings)
		r.Put("/settings/satellite-budget", h.UpdateSatelliteBudget)

		// Presets
		r.Post("/satellites/{satellite_id}/apply-preset", h.ApplyStrategyPreset)
		r.Get("/presets", h.ListStrategyPresets)
	})
}
