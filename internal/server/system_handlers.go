// Package server provides the HTTP server and routing for Sentinel.
package server

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/aristath/sentinel/internal/clients/tradernet"
	"github.com/aristath/sentinel/internal/database"
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/display"
	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/internal/services"
	"github.com/aristath/sentinel/internal/work"
	"github.com/rs/zerolog"
	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/mem"
)

// SystemHandlers handles system-wide monitoring and operations endpoints - NEW 8-database architecture
type SystemHandlers struct {
	log                     zerolog.Logger
	dataDir                 string
	startupTime             time.Time
	portfolioDB             *database.DB
	configDB                *database.DB
	universeDB              *database.DB
	historyDB               *database.DB
	workProcessor           *work.Processor
	portfolioDisplayCalc    *display.PortfolioDisplayCalculator
	displayManager          *display.StateManager
	brokerClient            domain.BrokerClient
	currencyExchangeService *services.CurrencyExchangeService
	cashManager             domain.CashManager
	marketHoursService      *market_hours.MarketHoursService
	marketStatusWS          *tradernet.MarketStatusWebSocket
}

// NewSystemHandlers creates a new system handlers instance
func NewSystemHandlers(
	log zerolog.Logger,
	dataDir string,
	portfolioDB, configDB, universeDB, historyDB *database.DB,
	historyDBClient universe.HistoryDBInterface,
	workProcessor *work.Processor,
	displayManager *display.StateManager,
	brokerClient domain.BrokerClient,
	currencyExchangeService *services.CurrencyExchangeService,
	cashManager domain.CashManager,
	marketHoursService *market_hours.MarketHoursService,
	marketStatusWS *tradernet.MarketStatusWebSocket,
) *SystemHandlers {
	// Create portfolio performance service
	portfolioPerf := display.NewPortfolioPerformanceService(
		portfolioDB.Conn(),
		configDB.Conn(),
		log,
	)

	// Create portfolio display calculator with filtered price access
	portfolioDisplayCalc := display.NewPortfolioDisplayCalculator(
		universeDB.Conn(),
		portfolioDB.Conn(),
		historyDBClient,
		portfolioPerf,
		log,
	)

	return &SystemHandlers{
		log:                     log.With().Str("component", "system_handlers").Logger(),
		dataDir:                 dataDir,
		startupTime:             time.Now(),
		portfolioDB:             portfolioDB,
		configDB:                configDB,
		universeDB:              universeDB,
		historyDB:               historyDB,
		workProcessor:           workProcessor,
		portfolioDisplayCalc:    portfolioDisplayCalc,
		displayManager:          displayManager,
		marketHoursService:      marketHoursService,
		marketStatusWS:          marketStatusWS,
		brokerClient:            brokerClient,
		currencyExchangeService: currencyExchangeService,
		cashManager:             cashManager,
	}
}

// executeWork is a helper to execute a work type via the Work Processor
func (h *SystemHandlers) executeWork(workType string) error {
	if h.workProcessor == nil {
		return fmt.Errorf("work processor not available")
	}
	return h.workProcessor.ExecuteNow(workType, "")
}

// SystemStatusResponse represents the system status response
type SystemStatusResponse struct {
	Status           string  `json:"status"`             // "healthy" or "unhealthy"
	CashBalanceEUR   float64 `json:"cash_balance_eur"`   // EUR-only cash balance
	CashBalanceTotal float64 `json:"cash_balance_total"` // Total cash in EUR (all currencies converted)
	CashBalance      float64 `json:"cash_balance"`       // Alias for cash_balance_total
	SecurityCount    int     `json:"security_count"`
	PositionCount    int     `json:"position_count"`   // All positions (including cash)
	ActivePositions  int     `json:"active_positions"` // Non-cash positions only
	LastSync         string  `json:"last_sync,omitempty"`
	UniverseActive   int     `json:"universe_active"`
}

// LEDDisplayResponse represents the LED display state
type LEDDisplayResponse struct {
	Mode           string                 `json:"mode"`                      // "TEXT", "HEALTH", or "STATS"
	CurrentPanel   int                    `json:"current_panel"`             // For TEXT mode
	SystemStats    map[string]interface{} `json:"system_stats,omitempty"`    // For STATS mode
	PortfolioState interface{}            `json:"portfolio_state,omitempty"` // For HEALTH mode
	DisplayText    string                 `json:"display_text,omitempty"`    // For TEXT mode
	TickerSpeed    int                    `json:"ticker_speed,omitempty"`    // For TEXT mode
	LED3           [3]int                 `json:"led3"`                      // RGB values for LED3
	LED4           [3]int                 `json:"led4"`                      // RGB values for LED4
	LED3Mode       string                 `json:"led3_mode,omitempty"`       // "solid", "blink", etc.
	LED4Mode       string                 `json:"led4_mode,omitempty"`       // "solid", "blink", "alternating", "coordinated"
	LED3Blink      *LED3BlinkInfo         `json:"led3_blink,omitempty"`      // Blink info for LED3
	LED4Blink      *LED4BlinkInfo         `json:"led4_blink,omitempty"`      // Blink info for LED4
}

// LED3BlinkInfo contains LED3 blink state information
type LED3BlinkInfo struct {
	Color      [3]int `json:"color"`
	IntervalMs int    `json:"interval_ms"`
	IsOn       bool   `json:"is_on"`
}

// LED4BlinkInfo contains LED4 blink state information
type LED4BlinkInfo struct {
	Mode            string `json:"mode"`                 // "blink", "alternating", "coordinated"
	Color           [3]int `json:"color,omitempty"`      // For blink/coordinated
	AltColor1       [3]int `json:"alt_color1,omitempty"` // For alternating
	AltColor2       [3]int `json:"alt_color2,omitempty"` // For alternating
	IntervalMs      int    `json:"interval_ms"`
	CoordinatedWith bool   `json:"coordinated_with,omitempty"` // LED3 state when coordinated
}

// TradernetStatusResponse represents Tradernet connection status
type TradernetStatusResponse struct {
	Connected bool   `json:"connected"`
	LastCheck string `json:"last_check"`
	Message   string `json:"message,omitempty"`
}

// JobsStatusResponse represents work processor job status
type JobsStatusResponse struct {
	WorkTypes []WorkTypeStatus `json:"work_types"`
}

// WorkTypeStatus represents the status of a work type
type WorkTypeStatus struct {
	ID           string   `json:"id"`
	Priority     string   `json:"priority"`
	MarketTiming string   `json:"market_timing"`
	Interval     string   `json:"interval"`           // e.g., "5m", "1h", "24h", "0" for on-demand
	LastRun      *string  `json:"last_run,omitempty"` // RFC3339 or null
	NextRun      *string  `json:"next_run,omitempty"` // RFC3339 or null
	DependsOn    []string `json:"depends_on"`
}

// MarketsStatusResponse represents market status

// IndividualMarketInfo represents status of a single exchange.
type IndividualMarketInfo struct {
	Name      string `json:"name"`
	Code      string `json:"code"`
	Status    string `json:"status"`     // "open", "closed", "pre_open", "post_close"
	OpenTime  string `json:"open_time"`  // "09:30"
	CloseTime string `json:"close_time"` // "16:00"
	Date      string `json:"date"`       // "2024-01-09"
	UpdatedAt string `json:"updated_at"` // ISO 8601 timestamp
}

type MarketsStatusResponse struct {
	Markets     map[string]IndividualMarketInfo `json:"markets"` // Key: exchange code (XNAS, XNYS, etc.)
	OpenCount   int                             `json:"open_count"`
	ClosedCount int                             `json:"closed_count"`
	LastUpdated string                          `json:"last_updated"`
}

// MarketInfo represents status of a single market
type MarketInfo struct {
	Exchange string `json:"exchange"` // "NASDAQ", "NYSE", "LSE", etc.
	IsOpen   bool   `json:"is_open"`
	Timezone string `json:"timezone"`
}

// MarketRegionInfo represents status of a geographic market region
type MarketRegionInfo struct {
	Open      bool   `json:"open"`
	ClosesAt  string `json:"closes_at,omitempty"`  // Time when market closes (if open)
	OpensAt   string `json:"opens_at,omitempty"`   // Time when market opens (if closed)
	OpensDate string `json:"opens_date,omitempty"` // Date when market opens (if closed and opens tomorrow or later)
}

// DatabaseStatsResponse represents database statistics
type DatabaseStatsResponse struct {
	CoreDatabases []DBInfo `json:"core_databases"`
	HistoryDBs    int      `json:"history_dbs"`
	TotalSizeMB   float64  `json:"total_size_mb"`
	LastChecked   string   `json:"last_checked"`
}

// DBInfo represents information about a single database
type DBInfo struct {
	Name       string  `json:"name"`
	Path       string  `json:"path"`
	SizeMB     float64 `json:"size_mb"`
	TableCount int     `json:"table_count,omitempty"`
	RowCount   int     `json:"row_count,omitempty"`
}

// DiskUsageResponse represents disk usage statistics
type DiskUsageResponse struct {
	DataDirMB   float64 `json:"data_dir_mb"`
	LogsDirMB   float64 `json:"logs_dir_mb"`
	BackupsMB   float64 `json:"backups_mb"`
	TotalMB     float64 `json:"total_mb"`
	AvailableMB float64 `json:"available_mb,omitempty"`
}

// GetSystemStatusSnapshot returns a snapshot of the current system status.
func (h *SystemHandlers) GetSystemStatusSnapshot() (SystemStatusResponse, error) {
	if h == nil {
		return SystemStatusResponse{}, fmt.Errorf("system handlers not initialized")
	}

	var firstErr error
	recordErr := func(err error) {
		if err != nil && err != sql.ErrNoRows && firstErr == nil {
			firstErr = err
		}
	}

	// Query positions to get last sync time and count
	var lastSync sql.NullString
	var totalPositionCount int

	err := h.portfolioDB.Conn().QueryRow(`
		SELECT COUNT(*), MAX(last_updated)
		FROM positions
	`).Scan(&totalPositionCount, &lastSync)

	if err != nil && err != sql.ErrNoRows {
		h.log.Error().Err(err).Msg("Failed to query positions")
		recordErr(err)
	}

	activePositionCount := totalPositionCount

	// Format last sync time if available
	var lastSyncFormatted string
	if lastSync.Valid && lastSync.String != "" {
		if t, err := time.Parse(time.RFC3339, lastSync.String); err == nil {
			lastSyncFormatted = t.Format("2006-01-02 15:04")
		} else {
			lastSyncFormatted = lastSync.String
		}
	}

	// Query securities count (excludes indices - they are non-tradable)
	var securityCount int
	err = h.universeDB.Conn().QueryRow(`
		SELECT COUNT(*) FROM securities WHERE active = 1 AND (product_type IS NULL OR product_type != ?)
	`, string(domain.ProductTypeIndex)).Scan(&securityCount)

	if err != nil && err != sql.ErrNoRows {
		h.log.Error().Err(err).Msg("Failed to query securities")
		recordErr(err)
	}

	// Get cash balances from CashManager
	cashBalances, err := h.cashManager.GetAllCashBalances()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get cash balances")
		recordErr(err)
		cashBalances = make(map[string]float64)
	}

	var cashBalanceEUR float64
	if eurBalance, ok := cashBalances["EUR"]; ok {
		cashBalanceEUR = eurBalance
	}

	var totalCashEUR float64
	for currency, balance := range cashBalances {
		if currency == "EUR" {
			totalCashEUR += balance
			continue
		}

		if h.currencyExchangeService != nil {
			rate, rateErr := h.currencyExchangeService.GetRate(currency, "EUR")
			if rateErr != nil {
				h.log.Warn().
					Err(rateErr).
					Str("currency", currency).
					Float64("balance", balance).
					Msg("Failed to get exchange rate, using fallback")
				recordErr(rateErr)
				switch currency {
				case "USD":
					totalCashEUR += balance * 0.9
				case "GBP":
					totalCashEUR += balance * 1.2
				case "HKD":
					totalCashEUR += balance * 0.11
				default:
					h.log.Warn().
						Str("currency", currency).
						Float64("balance", balance).
						Msg("Unknown currency, using 1:1 conversion")
					totalCashEUR += balance
				}
			} else {
				totalCashEUR += balance * rate
			}
			continue
		}

		h.log.Warn().
			Str("currency", currency).
			Float64("balance", balance).
			Msg("Exchange service not available, using fallback rates")

		switch currency {
		case "USD":
			totalCashEUR += balance * 0.9
		case "GBP":
			totalCashEUR += balance * 1.2
		case "HKD":
			totalCashEUR += balance * 0.11
		default:
			totalCashEUR += balance
		}
	}

	response := SystemStatusResponse{
		Status:           "healthy",
		CashBalanceEUR:   cashBalanceEUR,
		CashBalanceTotal: totalCashEUR,
		CashBalance:      totalCashEUR,
		SecurityCount:    securityCount,
		PositionCount:    totalPositionCount,
		ActivePositions:  activePositionCount,
		LastSync:         lastSyncFormatted,
		UniverseActive:   securityCount,
	}

	return response, firstErr
}

// HandleSystemStatus returns comprehensive system status
func (h *SystemHandlers) HandleSystemStatus(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting system status")

	response, err := h.GetSystemStatusSnapshot()
	if err != nil {
		h.log.Warn().Err(err).Msg("System status collected with warnings")
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleLEDDisplay returns LED display state
func (h *SystemHandlers) HandleLEDDisplay(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting LED display state")

	// Get display mode from settings
	var displayMode string
	err := h.configDB.Conn().QueryRow("SELECT value FROM settings WHERE key = 'display_mode'").Scan(&displayMode)
	if err != nil {
		// Default to TEXT if setting not found
		displayMode = "TEXT"
		h.log.Debug().Err(err).Msg("display_mode setting not found, defaulting to TEXT")
	}

	// Get LED states from display manager
	led3State := [3]int{0, 0, 0}
	led4State := [3]int{0, 0, 0}
	var led3Mode string
	var led4Mode string
	var led3Blink *LED3BlinkInfo
	var led4Blink *LED4BlinkInfo

	if h.displayManager != nil {
		state := h.displayManager.GetState()
		led3State = [3]int{state.LED3.R, state.LED3.G, state.LED3.B}
		led4State = [3]int{state.LED4.R, state.LED4.G, state.LED4.B}

		// Get LED3 blink state
		isBlinking3, color3, interval3, isOn3 := h.displayManager.GetLED3BlinkStateInfo()
		if isBlinking3 {
			led3Mode = "blink"
			led3Blink = &LED3BlinkInfo{
				Color:      [3]int{color3.R, color3.G, color3.B},
				IntervalMs: interval3,
				IsOn:       isOn3,
			}
		} else {
			led3Mode = "solid"
		}

		// Get LED4 state
		mode4, color4, altColor1, altColor2, interval4, coordinatedWith := h.displayManager.GetLED4StateInfo()
		switch mode4 {
		case display.LEDModeBlink:
			led4Mode = "blink"
			led4Blink = &LED4BlinkInfo{
				Mode:       "blink",
				Color:      [3]int{color4.R, color4.G, color4.B},
				IntervalMs: interval4,
			}
		case display.LEDModeAlternating:
			led4Mode = "alternating"
			led4Blink = &LED4BlinkInfo{
				Mode:       "alternating",
				AltColor1:  [3]int{altColor1.R, altColor1.G, altColor1.B},
				AltColor2:  [3]int{altColor2.R, altColor2.G, altColor2.B},
				IntervalMs: interval4,
			}
		case display.LEDModeCoordinated:
			led4Mode = "coordinated"
			led4Blink = &LED4BlinkInfo{
				Mode:            "coordinated",
				Color:           [3]int{color4.R, color4.G, color4.B},
				IntervalMs:      interval4,
				CoordinatedWith: coordinatedWith,
			}
		default:
			led4Mode = "solid"
		}
	}

	response := LEDDisplayResponse{
		Mode:         displayMode,
		CurrentPanel: 0,
		LED3:         led3State,
		LED4:         led4State,
		LED3Mode:     led3Mode,
		LED4Mode:     led4Mode,
		LED3Blink:    led3Blink,
		LED4Blink:    led4Blink,
	}

	// Return appropriate data based on mode
	switch displayMode {
	case "HEALTH":
		// Calculate portfolio display state (health visualization)
		portfolioState, err := h.portfolioDisplayCalc.CalculateDisplayState()
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to calculate portfolio display state")
			// Fallback to TEXT mode
			response.Mode = "TEXT"
			response.SystemStats = map[string]interface{}{
				"error": "Failed to calculate portfolio state",
			}
		} else {
			response.PortfolioState = portfolioState
		}

	case "TEXT":
		// Get ticker speed from settings
		var tickerSpeed float64
		err := h.configDB.Conn().QueryRow("SELECT value FROM settings WHERE key = 'ticker_speed'").Scan(&tickerSpeed)
		if err != nil {
			tickerSpeed = 50.0 // Default
			h.log.Debug().Err(err).Msg("Using default ticker speed")
		}

		// Get current ticker text from display manager
		text := ""
		if h.displayManager != nil {
			text = h.displayManager.GetCurrentText()
		}

		// Return ticker state
		response.DisplayText = text
		response.TickerSpeed = int(tickerSpeed)

		h.log.Debug().
			Str("text", text).
			Int("speed", int(tickerSpeed)).
			Msg("Returning ticker display state")

	default: // STATS mode
		// Calculate actual CPU and RAM percentages
		cpuPercent, ramPercent := h.getSystemStats()
		uptimeHours := time.Since(h.startupTime).Hours()
		response.SystemStats = map[string]interface{}{
			"uptime_hours": uptimeHours,
			"cpu_percent":  cpuPercent,
			"ram_percent":  ramPercent,
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleTradernetStatus returns Tradernet connection status
func (h *SystemHandlers) HandleTradernetStatus(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Checking Tradernet status")

	response := TradernetStatusResponse{
		Connected: false,
		LastCheck: time.Now().Format(time.RFC3339),
		Message:   "",
	}

	if h.brokerClient == nil {
		response.Message = "Tradernet client not configured"
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
		return
	}

	// Get credentials from settings database to ensure we use the latest values
	settingsRepo := settings.NewRepository(h.configDB.Conn(), h.log)
	apiKey, err := settingsRepo.Get("tradernet_api_key")
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get tradernet_api_key from settings")
	}
	apiSecret, err := settingsRepo.Get("tradernet_api_secret")
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get tradernet_api_secret from settings")
	}

	// Update client credentials if available
	if apiKey != nil && apiSecret != nil && *apiKey != "" && *apiSecret != "" {
		h.brokerClient.SetCredentials(*apiKey, *apiSecret)
		h.log.Debug().Msg("Updated Tradernet client credentials from settings")
	}

	healthResult, err := h.brokerClient.HealthCheck()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to check Tradernet health")
		response.Message = "Failed to check Tradernet service: " + err.Error()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
		return
	}

	response.Connected = healthResult.Connected
	response.LastCheck = healthResult.Timestamp
	if !healthResult.Connected {
		if apiKey == nil || apiSecret == nil || *apiKey == "" || *apiSecret == "" {
			response.Message = "Tradernet API credentials not configured"
		} else {
			response.Message = "Tradernet service is not connected - check credentials"
		}
	} else {
		response.Message = "Tradernet service is connected"
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// RefreshCredentials refreshes tradernet client credentials from settings database
func (h *SystemHandlers) RefreshCredentials() error {
	if h.brokerClient == nil {
		return fmt.Errorf("tradernet client not configured")
	}

	settingsRepo := settings.NewRepository(h.configDB.Conn(), h.log)
	apiKey, err := settingsRepo.Get("tradernet_api_key")
	if err != nil {
		return fmt.Errorf("failed to get tradernet_api_key from settings: %w", err)
	}
	apiSecret, err := settingsRepo.Get("tradernet_api_secret")
	if err != nil {
		return fmt.Errorf("failed to get tradernet_api_secret from settings: %w", err)
	}

	if apiKey != nil && apiSecret != nil && *apiKey != "" && *apiSecret != "" {
		h.brokerClient.SetCredentials(*apiKey, *apiSecret)
		h.log.Info().Msg("Tradernet client credentials refreshed from settings database")
		return nil
	}

	return fmt.Errorf("credentials not found in settings database")
}

// HandleJobsStatus returns work processor job status
func (h *SystemHandlers) HandleJobsStatus(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting jobs status")

	if h.workProcessor == nil {
		http.Error(w, "Work processor not available", http.StatusServiceUnavailable)
		return
	}

	registry := h.workProcessor.GetRegistry()
	completion := h.workProcessor.GetCompletion()

	workTypes := registry.ByPriority()
	workTypeStatuses := make([]WorkTypeStatus, 0, len(workTypes))

	for _, wt := range workTypes {
		// Get last completion time (for global work, subject is empty)
		lastRun, hasLastRun := completion.GetCompletion(wt.ID, "")

		status := WorkTypeStatus{
			ID:           wt.ID,
			Priority:     wt.Priority.String(),
			MarketTiming: wt.MarketTiming.String(),
			Interval:     formatInterval(wt.Interval),
			DependsOn:    wt.DependsOn,
		}

		// Set last run time if available
		if hasLastRun {
			lastRunStr := lastRun.Format(time.RFC3339)
			status.LastRun = &lastRunStr
		}

		// Calculate next run time
		// For on-demand work (interval = 0), next run is null
		// For interval-based work with no last run, next run is null
		// For interval-based work with last run, next run = last run + interval
		if wt.Interval > 0 && hasLastRun {
			nextRun := lastRun.Add(wt.Interval)
			nextRunStr := nextRun.Format(time.RFC3339)
			status.NextRun = &nextRunStr
		}

		workTypeStatuses = append(workTypeStatuses, status)
	}

	response := JobsStatusResponse{
		WorkTypes: workTypeStatuses,
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(response); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode jobs status response")
		http.Error(w, "Failed to encode response", http.StatusInternalServerError)
		return
	}
}

// formatInterval formats a duration as a human-readable string (e.g., "5m", "1h", "24h", "0" for zero)
func formatInterval(d time.Duration) string {
	if d == 0 {
		return "0"
	}

	hours := int(d.Hours())
	minutes := int(d.Minutes()) % 60
	seconds := int(d.Seconds()) % 60

	if hours > 0 {
		if minutes > 0 {
			return fmt.Sprintf("%dh%dm", hours, minutes)
		}
		return fmt.Sprintf("%dh", hours)
	}

	if minutes > 0 {
		return fmt.Sprintf("%dm", minutes)
	}

	if seconds > 0 {
		return fmt.Sprintf("%ds", seconds)
	}

	return "0"
}

// HandleMarketsStatus returns individual market status from WebSocket cache
func (h *SystemHandlers) HandleMarketsStatus(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting markets status from WebSocket cache")

	// Check if WebSocket client is available - if not, fall back to MarketHoursService
	if h.marketStatusWS == nil {
		h.log.Info().Msg("Market status WebSocket not available, using MarketHoursService fallback")
		// Use fallback logic (same as when cache is empty)
		h.returnMarketStatusFallback(w)
		return
	}

	// Get cached market statuses from WebSocket
	cachedMarkets := h.marketStatusWS.GetAllMarketStatuses()

	// If cache is empty, fall back to MarketHoursService
	if len(cachedMarkets) == 0 {
		h.log.Info().Msg("Market status cache is empty, using MarketHoursService fallback")
		h.returnMarketStatusFallback(w)
		return
	}

	// Convert tradernet.MarketStatusData to IndividualMarketInfo
	markets := make(map[string]IndividualMarketInfo, len(cachedMarkets))
	openCount := 0
	closedCount := 0

	for code, market := range cachedMarkets {
		if market.Status == "open" {
			openCount++
		} else {
			closedCount++
		}

		markets[code] = IndividualMarketInfo{
			Name:      market.Name,
			Code:      market.Code,
			Status:    market.Status,
			OpenTime:  market.OpenTime,
			CloseTime: market.CloseTime,
			Date:      market.Date,
			UpdatedAt: market.UpdatedAt.Format(time.RFC3339),
		}
	}

	response := MarketsStatusResponse{
		Markets:     markets,
		OpenCount:   openCount,
		ClosedCount: closedCount,
		LastUpdated: time.Now().Format(time.RFC3339),
	}

	h.log.Debug().
		Int("market_count", len(markets)).
		Int("open_count", openCount).
		Int("closed_count", closedCount).
		Msg("Returning market statuses from WebSocket cache")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// returnMarketStatusFallback returns market status using MarketHoursService as fallback
func (h *SystemHandlers) returnMarketStatusFallback(w http.ResponseWriter) {
	// List of exchanges to track (matches frontend MarketStatus.jsx)
	trackedExchanges := []struct {
		Code string
		Name string
	}{
		{"XNAS", "NASDAQ"},
		{"XNYS", "NYSE"},
		{"XETR", "Frankfurt"},
		{"XLON", "London"},
		{"XPAR", "Paris"},
		{"XMIL", "Milan"},
		{"XAMS", "Amsterdam"},
		{"XCSE", "Copenhagen"},
		{"XHKG", "Hong Kong"},
		{"XSHG", "Shanghai"},
		{"XTSE", "Tokyo"},
		{"XASX", "Sydney"},
	}

	markets := make(map[string]IndividualMarketInfo)
	openCount := 0
	closedCount := 0
	now := time.Now()

	for _, exchange := range trackedExchanges {
		status, err := h.marketHoursService.GetMarketStatus(exchange.Code, now)
		if err != nil {
			h.log.Warn().Err(err).Str("exchange", exchange.Code).Msg("Failed to get market status")
			continue
		}

		var statusStr string
		if status.Open {
			statusStr = "open"
			openCount++
		} else {
			statusStr = "closed"
			closedCount++
		}

		markets[exchange.Code] = IndividualMarketInfo{
			Name:      exchange.Name,
			Code:      exchange.Code,
			Status:    statusStr,
			OpenTime:  status.OpensAt,
			CloseTime: status.ClosesAt,
			Date:      now.Format("2006-01-02"),
			UpdatedAt: now.Format(time.RFC3339),
		}
	}

	response := MarketsStatusResponse{
		Markets:     markets,
		OpenCount:   openCount,
		ClosedCount: closedCount,
		LastUpdated: now.Format(time.RFC3339),
	}

	h.log.Debug().
		Int("market_count", len(markets)).
		Int("open_count", openCount).
		Int("closed_count", closedCount).
		Msg("Returning market statuses from fallback")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleDatabaseStats returns database statistics
func (h *SystemHandlers) HandleDatabaseStats(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting database stats")

	coreDatabases := []DBInfo{}
	totalSizeMB := 0.0

	// Check core databases
	dbPaths := []struct {
		name string
		path string
	}{
		{"config.db", filepath.Join(h.dataDir, "config.db")},
		{"state.db", filepath.Join(h.dataDir, "state.db")},
		{"ledger.db", filepath.Join(h.dataDir, "ledger.db")},
		{"dividends.db", filepath.Join(h.dataDir, "dividends.db")},
	}

	for _, dbPath := range dbPaths {
		if info, err := os.Stat(dbPath.path); err == nil {
			sizeMB := float64(info.Size()) / 1024 / 1024
			totalSizeMB += sizeMB

			coreDatabases = append(coreDatabases, DBInfo{
				Name:   dbPath.name,
				Path:   dbPath.path,
				SizeMB: sizeMB,
			})
		}
	}

	// Count consolidated history database
	historyCount := 0
	if h.historyDB != nil {
		historyCount = 1
		historyPath := filepath.Join(h.dataDir, "history.db")
		if info, err := os.Stat(historyPath); err == nil {
			totalSizeMB += float64(info.Size()) / 1024 / 1024
		}
	}

	response := DatabaseStatsResponse{
		CoreDatabases: coreDatabases,
		HistoryDBs:    historyCount,
		TotalSizeMB:   totalSizeMB,
		LastChecked:   time.Now().Format(time.RFC3339),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleDiskUsage returns disk usage statistics
func (h *SystemHandlers) HandleDiskUsage(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting disk usage")

	// Calculate directory sizes
	dataDirSize := h.getDirSize(h.dataDir)
	logsDir := filepath.Join(h.dataDir, "logs")
	logsDirSize := h.getDirSize(logsDir)
	backupsDir := filepath.Join(h.dataDir, "backups")
	backupsSize := h.getDirSize(backupsDir)

	response := DiskUsageResponse{
		DataDirMB: dataDirSize,
		LogsDirMB: logsDirSize,
		BackupsMB: backupsSize,
		TotalMB:   dataDirSize + logsDirSize + backupsSize,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// getDirSize calculates total size of a directory in MB
func (h *SystemHandlers) getDirSize(dirPath string) float64 {
	var totalSize int64

	err := filepath.Walk(dirPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil // Skip errors
		}
		if !info.IsDir() {
			totalSize += info.Size()
		}
		return nil
	})

	if err != nil {
		h.log.Warn().Err(err).Str("dir", dirPath).Msg("Failed to calculate directory size")
		return 0
	}

	return float64(totalSize) / 1024 / 1024
}

// getSystemStats calculates CPU and RAM usage percentages
// Uses a shorter interval (100ms) for faster response while still providing accurate readings
func (h *SystemHandlers) getSystemStats() (float64, float64) {
	// Get CPU percentage (average across all CPUs, over 100ms for faster response)
	// Using 100ms instead of 1s to avoid blocking the API call for too long
	// The display app polls every 2s with 2s timeout, so we need fast responses
	cpuPercent, err := cpu.Percent(100*time.Millisecond, false)
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get CPU percentage")
		cpuPercent = []float64{0}
	}

	// Get memory statistics (instant, no blocking)
	memStat, err := mem.VirtualMemory()
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get memory statistics")
		return 0, 0
	}

	// Return average CPU percentage and RAM usage percentage
	cpuAvg := 0.0
	if len(cpuPercent) > 0 {
		cpuAvg = cpuPercent[0]
	}

	return cpuAvg, memStat.UsedPercent
}

// ============================================================================
// Job Trigger Endpoints
// ============================================================================

// HandleTriggerEventBasedTrading triggers the event-based trading job immediately
// POST /api/jobs/event-based-trading
func (h *SystemHandlers) HandleTriggerEventBasedTrading(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Info().Msg("Manual event-based trading triggered")

	if err := h.executeWork("trading:execute"); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger event-based trading")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Event-based trading triggered successfully",
	})
}

// HandleSyncPortfolio triggers manual portfolio sync from Tradernet
// POST /api/system/sync/portfolio
func (h *SystemHandlers) HandleSyncPortfolio(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Info().Msg("Manual portfolio sync triggered")

	if err := h.executeWork("sync:portfolio"); err != nil {
		h.log.Error().Err(err).Msg("Failed to execute sync:portfolio work")
		http.Error(w, "Failed to trigger portfolio sync", http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Portfolio sync executed",
	})
}

// HandleSyncDailyPipeline triggers daily pipeline (securities data sync)
// POST /api/system/sync/daily-pipeline
// This is an alias for /sync/securities-data
func (h *SystemHandlers) HandleSyncDailyPipeline(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Info().Msg("Manual daily pipeline (securities data sync) triggered")

	// This is an alias for /sync/securities-data
	// The actual implementation is in universe handlers (HandleSyncSecuritiesData)
	// which proxies to Python for now

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Daily pipeline redirected to /sync/securities-data",
		"note":    "Use POST /api/system/sync/securities-data instead",
	})
}

// HandleSyncRecommendations triggers recommendation generation and cache update
// POST /api/system/sync/recommendations
func (h *SystemHandlers) HandleSyncRecommendations(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Info().Msg("Manual recommendation sync triggered")

	// Execute the planner chain: weights -> context -> plan -> recommendations
	if err := h.executeWork("planner:weights"); err != nil {
		h.log.Error().Err(err).Msg("Failed to execute planner:weights work")
		http.Error(w, "Failed to trigger recommendation generation", http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Recommendation generation triggered (planner chain started)",
	})
}

// ==========================================
// INDIVIDUAL SYNC JOB HANDLERS
// ==========================================

func (h *SystemHandlers) HandleTriggerSyncTrades(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual sync trades triggered")
	if err := h.executeWork("sync:trades"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Sync trades triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerSyncCashFlows(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual sync cash flows triggered")
	if err := h.executeWork("sync:cashflows"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Sync cash flows triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerSyncPortfolio(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual sync portfolio triggered")
	if err := h.executeWork("sync:portfolio"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Sync portfolio triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerSyncPrices(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual sync prices triggered")
	if err := h.executeWork("sync:prices"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Sync prices triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerCheckNegativeBalances(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual check negative balances triggered")
	if err := h.executeWork("sync:negative-balances"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Check negative balances triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerUpdateDisplayTicker(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual update display ticker triggered")
	if err := h.executeWork("sync:display"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Update display ticker triggered successfully"})
}

// ==========================================
// INDIVIDUAL PLANNING JOB HANDLERS
// ==========================================

func (h *SystemHandlers) HandleTriggerGetOptimizerWeights(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual get optimizer weights triggered")
	if err := h.executeWork("planner:weights"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Get optimizer weights triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerBuildOpportunityContext(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual build opportunity context triggered")
	if err := h.executeWork("planner:context"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Build opportunity context triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerCreateTradePlan(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual create trade plan triggered")
	if err := h.executeWork("planner:plan"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Create trade plan triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerStoreRecommendations(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual store recommendations triggered")
	if err := h.executeWork("planner:recommendations"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Store recommendations triggered successfully"})
}

// ==========================================
// INDIVIDUAL DIVIDEND JOB HANDLERS
// ==========================================

func (h *SystemHandlers) HandleTriggerGetUnreinvestedDividends(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual get unreinvested dividends triggered")
	if err := h.executeWork("dividend:detect"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Get unreinvested dividends triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerCreateDividendRecommendations(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual create dividend recommendations triggered")
	if err := h.executeWork("dividend:recommend"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Create dividend recommendations triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerExecuteDividendTrades(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual execute dividend trades triggered")
	if err := h.executeWork("dividend:execute"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Execute dividend trades triggered successfully"})
}

// ==========================================
// INDIVIDUAL HEALTH CHECK JOB HANDLERS
// ==========================================

func (h *SystemHandlers) HandleTriggerCheckCoreDatabases(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual check core databases triggered")
	if err := h.executeWork("maintenance:health"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Check core databases triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerCheckHistoryDatabases(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual check history databases triggered")
	if err := h.executeWork("maintenance:health"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Check history databases triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerCheckWALCheckpoints(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.log.Info().Msg("Manual check WAL checkpoints triggered")
	if err := h.executeWork("maintenance:cleanup:history"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Check WAL checkpoints triggered successfully"})
}

// HandlePendingOrders handles GET /api/system/pending-orders
// Returns pending orders from the broker with their ISIN mappings
func (h *SystemHandlers) HandlePendingOrders(w http.ResponseWriter, r *http.Request) {
	if h.brokerClient == nil {
		h.writeJSON(w, map[string]interface{}{
			"error":   "Broker client not configured",
			"success": false,
		})
		return
	}

	if !h.brokerClient.IsConnected() {
		h.writeJSON(w, map[string]interface{}{
			"error":   "Broker not connected",
			"success": false,
		})
		return
	}

	// Fetch pending orders from broker
	pendingOrders, err := h.brokerClient.GetPendingOrders()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to fetch pending orders")
		h.writeJSON(w, map[string]interface{}{
			"error":   fmt.Sprintf("Failed to fetch pending orders: %v", err),
			"success": false,
		})
		return
	}

	// Convert to response format
	orders := make([]map[string]interface{}, 0, len(pendingOrders))
	for _, order := range pendingOrders {
		orders = append(orders, map[string]interface{}{
			"order_id": order.OrderID,
			"symbol":   order.Symbol,
			"side":     order.Side,
			"quantity": order.Quantity,
			"price":    order.Price,
			"currency": order.Currency,
		})
	}

	h.writeJSON(w, map[string]interface{}{
		"success":        true,
		"pending_orders": orders,
		"count":          len(orders),
		"timestamp":      time.Now().Format(time.RFC3339),
	})
}

// HandleUploadSketch compiles and uploads the Arduino sketch to the MCU
// POST /api/system/mcu/upload-sketch
func (h *SystemHandlers) HandleUploadSketch(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Info().Msg("Manual MCU sketch upload triggered")

	// Check if sketch directory exists
	sketchDir := "/home/arduino/ArduinoApps/trader-display/sketch"
	if _, err := os.Stat(sketchDir); os.IsNotExist(err) {
		h.log.Warn().Str("sketch_dir", sketchDir).Msg("Sketch directory not found - not running on Arduino hardware")
		h.writeJSON(w, map[string]interface{}{
			"status":  "error",
			"message": "Sketch directory not found - not running on Arduino hardware",
		})
		return
	}

	// Compile the sketch
	h.log.Info().Msg("Compiling Arduino sketch...")
	compileCmd := exec.Command("arduino-cli", "compile", "--fqbn", "arduino:zephyr:unoq", sketchDir)
	compileOutput, err := compileCmd.CombinedOutput()
	if err != nil {
		h.log.Error().Err(err).Str("output", string(compileOutput)).Msg("Failed to compile sketch")
		h.writeJSON(w, map[string]interface{}{
			"status":  "error",
			"message": fmt.Sprintf("Failed to compile sketch: %v", err),
			"output":  string(compileOutput),
		})
		return
	}
	h.log.Info().Str("output", string(compileOutput)).Msg("Sketch compiled successfully")

	// Upload the sketch
	h.log.Info().Msg("Uploading sketch to MCU...")
	uploadCmd := exec.Command("arduino-cli", "upload", "--fqbn", "arduino:zephyr:unoq", sketchDir)
	uploadOutput, err := uploadCmd.CombinedOutput()
	if err != nil {
		h.log.Error().Err(err).Str("output", string(uploadOutput)).Msg("Failed to upload sketch")
		h.writeJSON(w, map[string]interface{}{
			"status":  "error",
			"message": fmt.Sprintf("Failed to upload sketch: %v", err),
			"output":  string(uploadOutput),
		})
		return
	}
	h.log.Info().Str("output", string(uploadOutput)).Msg("Sketch uploaded successfully")

	// Restart arduino-router service to re-establish serial connection with MCU
	// This is required for the MCU to register its RPC methods with the router
	h.log.Info().Msg("Restarting arduino-router service...")
	restartCmd := exec.Command("sudo", "systemctl", "restart", "arduino-router")
	restartOutput, err := restartCmd.CombinedOutput()
	if err != nil {
		h.log.Warn().Err(err).Str("output", string(restartOutput)).Msg("Failed to restart arduino-router (sketch uploaded but may need manual service restart)")
	} else {
		h.log.Info().Msg("arduino-router service restarted successfully")
	}

	h.writeJSON(w, map[string]interface{}{
		"status":  "success",
		"message": "Sketch compiled and uploaded successfully",
	})
}

// writeJSON writes a JSON response
func (h *SystemHandlers) writeJSON(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
		http.Error(w, "Internal server error", http.StatusInternalServerError)
	}
}

// HandleTriggerTradernetMetadataSync triggers the Tradernet metadata sync job
// POST /api/system/jobs/tradernet-metadata-sync
func (h *SystemHandlers) HandleTriggerTradernetMetadataSync(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Info().Msg("Manual Tradernet metadata sync triggered")

	// security:metadata syncs metadata for all active securities
	// The Work Processor will iterate through all active ISINs
	if err := h.executeWork("security:metadata"); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger Tradernet metadata sync")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{"status": "success", "message": "Tradernet metadata sync triggered successfully"})
}
