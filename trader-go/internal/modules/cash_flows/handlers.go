package cash_flows

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// Handler handles cash flow HTTP requests
type Handler struct {
	repo             *Repository
	depositProcessor *DepositProcessor
	tradernetClient  TradernetClient
	log              zerolog.Logger
}

// NewHandler creates a new cash flows handler
func NewHandler(
	repo *Repository,
	depositProcessor *DepositProcessor,
	tradernetClient TradernetClient,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		repo:             repo,
		depositProcessor: depositProcessor,
		tradernetClient:  tradernetClient,
		log:              log.With().Str("handler", "cash_flows").Logger(),
	}
}

// HandleGetCashFlows handles GET / - list cash flows with filters
func (h *Handler) HandleGetCashFlows(w http.ResponseWriter, r *http.Request) {
	// Parse query parameters
	limitStr := r.URL.Query().Get("limit")
	txType := r.URL.Query().Get("transaction_type")
	startDate := r.URL.Query().Get("start_date")
	endDate := r.URL.Query().Get("end_date")

	var cashFlows []CashFlow
	var err error

	// Apply filters
	if startDate != "" && endDate != "" {
		// Validate date format
		if !isValidDate(startDate) || !isValidDate(endDate) {
			http.Error(w, "Invalid date format. Use YYYY-MM-DD", http.StatusBadRequest)
			return
		}

		// Validate date range
		if startDate > endDate {
			http.Error(w, "start_date must be <= end_date", http.StatusBadRequest)
			return
		}

		cashFlows, err = h.repo.GetByDateRange(startDate, endDate)
	} else if txType != "" {
		cashFlows, err = h.repo.GetByType(txType)
	} else {
		var limit *int
		if limitStr != "" {
			l, parseErr := strconv.Atoi(limitStr)
			if parseErr != nil || l < 1 || l > 10000 {
				http.Error(w, "Invalid limit. Must be 1-10000", http.StatusBadRequest)
				return
			}
			limit = &l
		}
		cashFlows, err = h.repo.GetAll(limit)
	}

	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get cash flows")
		http.Error(w, "Failed to retrieve cash flows", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(cashFlows)
}

// HandleSyncCashFlows handles GET /sync - sync from Tradernet API
func (h *Handler) HandleSyncCashFlows(w http.ResponseWriter, r *http.Request) {
	// Check Tradernet connection
	if !h.tradernetClient.IsConnected() {
		h.log.Warn().Msg("Tradernet not connected")
		http.Error(w, "Tradernet service unavailable", http.StatusServiceUnavailable)
		return
	}

	// Fetch transactions from Tradernet
	transactions, err := h.tradernetClient.GetAllCashFlows(1000)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to fetch cash flows from Tradernet")
		http.Error(w, fmt.Sprintf("Failed to fetch from Tradernet: %v", err), http.StatusInternalServerError)
		return
	}

	// Sync to database
	syncedCount, err := h.repo.SyncFromAPI(transactions)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to sync cash flows")
		http.Error(w, "Failed to sync cash flows", http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"message":        fmt.Sprintf("Synced %d new cash flows", syncedCount),
		"synced":         syncedCount,
		"total_from_api": len(transactions),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleGetSummary handles GET /summary - aggregate statistics
func (h *Handler) HandleGetSummary(w http.ResponseWriter, r *http.Request) {
	// Get all cash flows
	cashFlows, err := h.repo.GetAll(nil)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get cash flows for summary")
		http.Error(w, "Failed to retrieve summary", http.StatusInternalServerError)
		return
	}

	// Group by transaction type
	typeSummary := make(map[string]map[string]interface{})
	totalDeposits := 0.0
	totalWithdrawals := 0.0

	for _, cf := range cashFlows {
		if cf.TransactionType == nil {
			continue
		}

		txType := *cf.TransactionType
		if _, exists := typeSummary[txType]; !exists {
			typeSummary[txType] = map[string]interface{}{
				"count": 0,
				"total": 0.0,
			}
		}

		typeSummary[txType]["count"] = typeSummary[txType]["count"].(int) + 1
		typeSummary[txType]["total"] = typeSummary[txType]["total"].(float64) + cf.AmountEUR

		// Track deposits/withdrawals
		txTypeLower := strings.ToLower(txType)
		if strings.Contains(txTypeLower, "deposit") || strings.Contains(txTypeLower, "refill") {
			totalDeposits += cf.AmountEUR
		} else if strings.Contains(txTypeLower, "withdrawal") {
			totalWithdrawals += cf.AmountEUR
		}
	}

	summary := map[string]interface{}{
		"total_transactions": len(cashFlows),
		"by_type":            typeSummary,
		"total_deposits":     totalDeposits,
		"total_withdrawals":  totalWithdrawals,
		"net_cash_flow":      totalDeposits - totalWithdrawals,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(summary)
}

// isValidDate validates YYYY-MM-DD format
func isValidDate(dateStr string) bool {
	_, err := time.Parse("2006-01-02", dateStr)
	return err == nil
}
