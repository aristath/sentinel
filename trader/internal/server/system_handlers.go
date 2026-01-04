package server

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/internal/modules/cash_utils"
	"github.com/aristath/arduino-trader/internal/modules/display"
	"github.com/aristath/arduino-trader/internal/modules/settings"
	"github.com/aristath/arduino-trader/internal/scheduler"
	"github.com/aristath/arduino-trader/internal/services"
	"github.com/rs/zerolog"
)

// SystemHandlers handles system-wide monitoring and operations endpoints - NEW 8-database architecture
type SystemHandlers struct {
	log                     zerolog.Logger
	dataDir                 string
	portfolioDB             *database.DB
	configDB                *database.DB
	universeDB              *database.DB
	marketHours             *scheduler.MarketHoursService
	scheduler               *scheduler.Scheduler
	portfolioDisplayCalc    *display.PortfolioDisplayCalculator
	displayManager          *display.StateManager
	tradernetClient         *tradernet.Client
	currencyExchangeService *services.CurrencyExchangeService
	// Jobs (will be set after job registration in main.go)
	healthCheckJob             scheduler.Job
	syncCycleJob               scheduler.Job
	dividendReinvestJob        scheduler.Job
	satelliteMaintenanceJob    scheduler.Job
	satelliteReconciliationJob scheduler.Job
	satelliteEvaluationJob     scheduler.Job
	plannerBatchJob            scheduler.Job
	eventBasedTradingJob       scheduler.Job
}

// NewSystemHandlers creates a new system handlers instance
func NewSystemHandlers(
	log zerolog.Logger,
	dataDir string,
	portfolioDB, configDB, universeDB *database.DB,
	sched *scheduler.Scheduler,
	displayManager *display.StateManager,
	tradernetClient *tradernet.Client,
	currencyExchangeService *services.CurrencyExchangeService,
) *SystemHandlers {
	// Create portfolio performance service
	portfolioPerf := display.NewPortfolioPerformanceService(
		portfolioDB.Conn(),
		configDB.Conn(),
		log,
	)

	// Create portfolio display calculator
	portfolioDisplayCalc := display.NewPortfolioDisplayCalculator(
		universeDB.Conn(),
		portfolioDB.Conn(),
		portfolioPerf,
		dataDir,
		log,
	)

	return &SystemHandlers{
		log:                     log.With().Str("component", "system_handlers").Logger(),
		dataDir:                 dataDir,
		portfolioDB:             portfolioDB,
		configDB:                configDB,
		universeDB:              universeDB,
		marketHours:             scheduler.NewMarketHoursService(log),
		scheduler:               sched,
		portfolioDisplayCalc:    portfolioDisplayCalc,
		displayManager:          displayManager,
		tradernetClient:         tradernetClient,
		currencyExchangeService: currencyExchangeService,
	}
}

// SetJobs registers job references for manual triggering
// Called after jobs are registered in main.go
func (h *SystemHandlers) SetJobs(
	healthCheck scheduler.Job,
	syncCycle scheduler.Job,
	dividendReinvest scheduler.Job,
	satelliteMaintenance scheduler.Job,
	satelliteReconciliation scheduler.Job,
	satelliteEvaluation scheduler.Job,
	plannerBatch scheduler.Job,
	eventBasedTrading scheduler.Job,
) {
	h.healthCheckJob = healthCheck
	h.syncCycleJob = syncCycle
	h.dividendReinvestJob = dividendReinvest
	h.satelliteMaintenanceJob = satelliteMaintenance
	h.satelliteReconciliationJob = satelliteReconciliation
	h.satelliteEvaluationJob = satelliteEvaluation
	h.plannerBatchJob = plannerBatch
	h.eventBasedTradingJob = eventBasedTrading
}

// SystemStatusResponse represents the system status response
type SystemStatusResponse struct {
	CashBalanceEUR   float64 `json:"cash_balance_eur"`   // EUR-only cash balance
	CashBalanceTotal float64 `json:"cash_balance_total"` // Total cash in EUR (all currencies converted)
	CashBalance      float64 `json:"cash_balance"`       // Backward compatibility: alias for cash_balance_total
	SecurityCount    int     `json:"security_count"`
	PositionCount    int     `json:"position_count"`   // All positions (including cash)
	ActivePositions  int     `json:"active_positions"` // Non-cash positions only
	LastSync         string  `json:"last_sync,omitempty"`
	UniverseActive   int     `json:"universe_active"`
}

// LEDDisplayResponse represents the LED display state
type LEDDisplayResponse struct {
	Mode           string                 `json:"mode"`                      // "STATS", "TICKER", or "PORTFOLIO"
	CurrentPanel   int                    `json:"current_panel"`             // For TICKER mode
	SystemStats    map[string]interface{} `json:"system_stats,omitempty"`    // For STATS mode
	PortfolioState interface{}            `json:"portfolio_state,omitempty"` // For PORTFOLIO mode
	DisplayText    string                 `json:"display_text,omitempty"`    // For TICKER mode
	TickerSpeed    int                    `json:"ticker_speed,omitempty"`    // For TICKER mode
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

// JobsStatusResponse represents scheduler job status
type JobsStatusResponse struct {
	TotalJobs int       `json:"total_jobs"`
	Jobs      []JobInfo `json:"jobs"`
	LastRun   string    `json:"last_run,omitempty"`
	NextRun   string    `json:"next_run,omitempty"`
}

// JobInfo represents information about a single job
type JobInfo struct {
	Name     string `json:"name"`
	Schedule string `json:"schedule"`
	LastRun  string `json:"last_run,omitempty"`
	NextRun  string `json:"next_run,omitempty"`
	Status   string `json:"status"` // "active", "idle", "failed"
}

// MarketsStatusResponse represents market status
type MarketsStatusResponse struct {
	Markets     map[string]MarketRegionInfo `json:"markets"` // Key: "EU", "US", "ASIA"
	OpenCount   int                         `json:"open_count"`
	ClosedCount int                         `json:"closed_count"`
	LastUpdated string                      `json:"last_updated"`
}

// MarketInfo represents status of a single market (legacy, kept for backward compatibility)
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

// HandleSystemStatus returns comprehensive system status
func (h *SystemHandlers) HandleSystemStatus(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting system status")

	// Query positions to get last sync time and count
	var lastSync string
	var totalPositionCount int

	err := h.portfolioDB.Conn().QueryRow(`
		SELECT COUNT(*), MAX(last_updated)
		FROM positions
	`).Scan(&totalPositionCount, &lastSync)

	if err != nil && err != sql.ErrNoRows {
		h.log.Error().Err(err).Msg("Failed to query positions")
	}

	// Query non-cash positions count (active positions)
	var activePositionCount int
	err = h.portfolioDB.Conn().QueryRow(`
		SELECT COUNT(*)
		FROM positions
		WHERE symbol NOT LIKE 'CASH:%'
	`).Scan(&activePositionCount)

	if err != nil && err != sql.ErrNoRows {
		h.log.Error().Err(err).Msg("Failed to query active positions")
		// Fallback to total count if query fails
		activePositionCount = totalPositionCount
	}

	// Format last sync time if available
	if lastSync != "" {
		// Parse and reformat to "YYYY-MM-DD HH:MM"
		if t, err := time.Parse(time.RFC3339, lastSync); err == nil {
			lastSync = t.Format("2006-01-02 15:04")
		}
	}

	// Query securities count
	var securityCount int
	err = h.universeDB.Conn().QueryRow(`
		SELECT COUNT(*) FROM securities WHERE active = 1
	`).Scan(&securityCount)

	if err != nil && err != sql.ErrNoRows {
		h.log.Error().Err(err).Msg("Failed to query securities")
	}

	// Get cash balances from positions (CASH is now a normal security)
	// Cash positions have symbols like "CASH:EUR:core", "CASH:USD:core", etc.
	// First, get EUR-only cash balance
	var cashBalanceEUR float64
	err = h.portfolioDB.Conn().QueryRow(`
		SELECT COALESCE(SUM(quantity), 0)
		FROM positions
		WHERE symbol LIKE 'CASH:EUR:%'
	`).Scan(&cashBalanceEUR)

	if err != nil && err != sql.ErrNoRows {
		h.log.Error().Err(err).Msg("Failed to query EUR cash balance from positions")
		cashBalanceEUR = 0.0 // Fallback to 0 on error
	}

	// Get total cash balance in EUR (all currencies converted)
	// Query all cash positions grouped by currency
	var totalCashEUR float64
	rows, err := h.portfolioDB.Conn().Query(`
		SELECT symbol, quantity
		FROM positions
		WHERE symbol LIKE 'CASH:%'
	`)
	if err != nil && err != sql.ErrNoRows {
		h.log.Error().Err(err).Msg("Failed to query cash positions for total balance")
		totalCashEUR = cashBalanceEUR // Fallback to EUR-only if query fails
	} else if err == nil {
		defer rows.Close()

		// Group by currency and sum
		currencyBalances := make(map[string]float64)
		for rows.Next() {
			var symbol string
			var quantity float64
			if err := rows.Scan(&symbol, &quantity); err != nil {
				h.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to scan cash position")
				continue
			}

			// Parse currency from symbol (format: CASH:CURRENCY:BUCKET)
			currency, _, err := cash_utils.ParseCashSymbol(symbol)
			if err != nil {
				h.log.Warn().Err(err).Str("symbol", symbol).Msg("Failed to parse cash symbol")
				continue
			}

			currencyBalances[currency] += quantity
		}

		// Check for errors during iteration
		if err := rows.Err(); err != nil {
			h.log.Warn().Err(err).Msg("Error iterating cash positions, using partial results")
		}

		// Convert all currencies to EUR
		for currency, balance := range currencyBalances {
			if currency == "EUR" {
				totalCashEUR += balance
			} else {
				// Convert to EUR using exchange service
				if h.currencyExchangeService != nil {
					rate, err := h.currencyExchangeService.GetRate(currency, "EUR")
					if err != nil {
						h.log.Warn().
							Err(err).
							Str("currency", currency).
							Float64("balance", balance).
							Msg("Failed to get exchange rate, using fallback")
						// Fallback rates for autonomous operation
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
							totalCashEUR += balance // Assume 1:1 for unknown currencies
						}
					} else {
						totalCashEUR += balance * rate
					}
				} else {
					// No exchange service available, use fallback rates
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
						totalCashEUR += balance // Assume 1:1 for unknown currencies
					}
				}
			}
		}
	} else {
		// No rows found, use EUR-only as total
		totalCashEUR = cashBalanceEUR
	}

	response := SystemStatusResponse{
		CashBalanceEUR:   cashBalanceEUR,
		CashBalanceTotal: totalCashEUR,
		CashBalance:      totalCashEUR, // Backward compatibility
		SecurityCount:    securityCount,
		PositionCount:    totalPositionCount,
		ActivePositions:  activePositionCount,
		LastSync:         lastSync,
		UniverseActive:   securityCount,
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
		// Default to STATS if setting not found
		displayMode = "STATS"
		h.log.Debug().Err(err).Msg("display_mode setting not found, defaulting to STATS")
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
	case "PORTFOLIO":
		// Calculate portfolio display state
		portfolioState, err := h.portfolioDisplayCalc.CalculateDisplayState()
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to calculate portfolio display state")
			// Fallback to STATS mode
			response.Mode = "STATS"
			response.SystemStats = map[string]interface{}{
				"error": "Failed to calculate portfolio state",
			}
		} else {
			response.PortfolioState = portfolioState
		}

	case "TICKER":
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
		response.SystemStats = map[string]interface{}{
			"uptime_hours": 0, // TODO: Calculate actual uptime
			"cpu_percent":  0,
			"ram_percent":  0,
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

	if h.tradernetClient == nil {
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
		h.tradernetClient.SetCredentials(*apiKey, *apiSecret)
		h.log.Debug().Msg("Updated Tradernet client credentials from settings")
	}

	healthResult, err := h.tradernetClient.HealthCheck()
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

// HandleJobsStatus returns scheduler job status
func (h *SystemHandlers) HandleJobsStatus(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting jobs status")

	// TODO: Integrate with actual scheduler
	response := JobsStatusResponse{
		TotalJobs: 0,
		Jobs:      []JobInfo{},
		LastRun:   time.Now().Add(-5 * time.Minute).Format(time.RFC3339),
		NextRun:   time.Now().Add(5 * time.Minute).Format(time.RFC3339),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// getExchangeGeography maps exchange names to geographic regions
func getExchangeGeography(exchange string) string {
	// US markets
	usExchanges := map[string]bool{
		"NYSE":     true,
		"NASDAQ":   true,
		"NasdaqGS": true,
		"NasdaqCM": true,
		"TSX":      true,
	}
	if usExchanges[exchange] {
		return "US"
	}

	// EU markets
	euExchanges := map[string]bool{
		"LSE":        true,
		"XETRA":      true,
		"XETR":       true,
		"Paris":      true,
		"Amsterdam":  true,
		"Milan":      true,
		"SIX":        true,
		"Athens":     true,
		"Copenhagen": true,
	}
	if euExchanges[exchange] {
		return "EU"
	}

	// Asia markets
	asiaExchanges := map[string]bool{
		"HKSE":     true,
		"XHKG":     true,
		"Shenzhen": true,
		"XSHG":     true,
		"TSE":      true,
		"XTSE":     true,
		"SGX":      true,
		"KRX":      true,
		"TWSE":     true,
		"ASX":      true,
		"XASX":     true,
		"NSE":      true,
	}
	if asiaExchanges[exchange] {
		return "ASIA"
	}

	// Default to US if unknown
	return "US"
}

// calculateNextOpenCloseTimes calculates the next open/close times for a region
func (h *SystemHandlers) calculateNextOpenCloseTimes(region string, exchanges []scheduler.MarketStatus) MarketRegionInfo {
	now := time.Now()
	var nextClose time.Time
	var nextOpen time.Time
	var nextOpenDate string
	regionOpen := false

	// Find the earliest next close time (if any exchange is open)
	// and the earliest next open time (if all are closed)
	for _, status := range exchanges {
		cal := h.marketHours.GetCalendar(status.Exchange)
		if cal == nil {
			continue
		}

		nowInTz := now.In(cal.Timezone)

		if status.IsOpen {
			regionOpen = true
			// Calculate when this exchange closes today
			for _, window := range cal.TradingWindows {
				closeTime := time.Date(nowInTz.Year(), nowInTz.Month(), nowInTz.Day(),
					window.CloseHour, window.CloseMinute, 0, 0, cal.Timezone)
				if nowInTz.Before(closeTime) {
					if nextClose.IsZero() || closeTime.Before(nextClose) {
						nextClose = closeTime
					}
				}
			}
		} else {
			// Calculate when this exchange opens next
			// First check if it opens today
			foundToday := false
			for _, window := range cal.TradingWindows {
				openTime := time.Date(nowInTz.Year(), nowInTz.Month(), nowInTz.Day(),
					window.OpenHour, window.OpenMinute, 0, 0, cal.Timezone)
				if nowInTz.Before(openTime) {
					// Opens today
					if nextOpen.IsZero() || openTime.Before(nextOpen) {
						nextOpen = openTime
						nextOpenDate = ""
						foundToday = true
					}
				}
			}

			// If not opening today, find next trading day
			if !foundToday {
				nextDay := nowInTz.AddDate(0, 0, 1)
				// Skip weekends and holidays
				for {
					// Skip weekends
					if nextDay.Weekday() == time.Saturday {
						nextDay = nextDay.AddDate(0, 0, 1)
						continue
					}
					if nextDay.Weekday() == time.Sunday {
						nextDay = nextDay.AddDate(0, 0, 1)
						continue
					}

					// Check if it's a holiday
					today := time.Date(nextDay.Year(), nextDay.Month(), nextDay.Day(), 0, 0, 0, 0, cal.Timezone)
					isHoliday := false
					for _, holiday := range cal.Holidays2026 {
						if holiday.Equal(today) {
							isHoliday = true
							break
						}
					}
					if isHoliday {
						nextDay = nextDay.AddDate(0, 0, 1)
						continue
					}

					// Found next trading day, calculate open time
					for _, window := range cal.TradingWindows {
						openTime := time.Date(nextDay.Year(), nextDay.Month(), nextDay.Day(),
							window.OpenHour, window.OpenMinute, 0, 0, cal.Timezone)
						if nextOpen.IsZero() || openTime.Before(nextOpen) {
							nextOpen = openTime
							nextOpenDate = nextDay.Format("Jan 2")
						}
					}
					break
				}
			}
		}
	}

	info := MarketRegionInfo{
		Open: regionOpen,
	}

	if regionOpen && !nextClose.IsZero() {
		info.ClosesAt = nextClose.Format("15:04")
	}

	if !regionOpen && !nextOpen.IsZero() {
		info.OpensAt = nextOpen.Format("15:04")
		if nextOpenDate != "" {
			info.OpensDate = nextOpenDate
		}
	}

	return info
}

// HandleMarketsStatus returns market open/close status grouped by geography
func (h *SystemHandlers) HandleMarketsStatus(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting markets status")

	// Get real-time market statuses
	statuses := h.marketHours.GetAllMarketStatuses()

	// Group exchanges by geography
	exchangesByRegion := make(map[string][]scheduler.MarketStatus)
	for _, status := range statuses {
		geo := getExchangeGeography(status.Exchange)
		exchangesByRegion[geo] = append(exchangesByRegion[geo], status)
	}

	// Calculate status for each region
	markets := make(map[string]MarketRegionInfo)
	openCount := 0
	closedCount := 0

	for region, exchanges := range exchangesByRegion {
		info := h.calculateNextOpenCloseTimes(region, exchanges)
		markets[region] = info

		if info.Open {
			openCount++
		} else {
			closedCount++
		}
	}

	response := MarketsStatusResponse{
		Markets:     markets,
		OpenCount:   openCount,
		ClosedCount: closedCount,
		LastUpdated: time.Now().Format(time.RFC3339),
	}

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
		{"snapshots.db", filepath.Join(h.dataDir, "snapshots.db")},
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

	// Count history databases
	historyDir := filepath.Join(h.dataDir, "history")
	historyCount := 0
	if entries, err := os.ReadDir(historyDir); err == nil {
		for _, entry := range entries {
			if !entry.IsDir() && filepath.Ext(entry.Name()) == ".db" {
				historyCount++
				if info, err := entry.Info(); err == nil {
					totalSizeMB += float64(info.Size()) / 1024 / 1024
				}
			}
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

// ============================================================================
// Job Trigger Endpoints
// ============================================================================

// HandleTriggerSyncCycle triggers the sync cycle job immediately
// POST /api/jobs/sync-cycle
func (h *SystemHandlers) HandleTriggerSyncCycle(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if h.syncCycleJob == nil {
		h.log.Warn().Msg("Sync cycle job not registered yet")
		h.writeJSON(w, map[string]string{
			"status":  "error",
			"message": "Sync cycle job not registered",
		})
		return
	}

	h.log.Info().Msg("Manual sync cycle triggered")

	if err := h.scheduler.RunNow(h.syncCycleJob); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger sync cycle")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Sync cycle triggered successfully",
	})
}

// HandleTriggerHealthCheck triggers the health check job immediately
// POST /api/jobs/health-check
func (h *SystemHandlers) HandleTriggerHealthCheck(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if h.healthCheckJob == nil {
		h.log.Warn().Msg("Health check job not registered yet")
		h.writeJSON(w, map[string]string{
			"status":  "error",
			"message": "Health check job not registered",
		})
		return
	}

	h.log.Info().Msg("Manual health check triggered")

	if err := h.scheduler.RunNow(h.healthCheckJob); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger health check")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Health check triggered successfully",
	})
}

// HandleTriggerDividendReinvestment triggers the dividend reinvestment job immediately
// POST /api/jobs/dividend-reinvestment
func (h *SystemHandlers) HandleTriggerDividendReinvestment(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if h.dividendReinvestJob == nil {
		h.log.Warn().Msg("Dividend reinvestment job not registered yet")
		h.writeJSON(w, map[string]string{
			"status":  "error",
			"message": "Dividend reinvestment job not registered",
		})
		return
	}

	h.log.Info().Msg("Manual dividend reinvestment triggered")

	if err := h.scheduler.RunNow(h.dividendReinvestJob); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger dividend reinvestment")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Dividend reinvestment triggered successfully",
	})
}

// HandleTriggerSatelliteMaintenance triggers the satellite maintenance job immediately
// POST /api/jobs/satellite-maintenance
func (h *SystemHandlers) HandleTriggerSatelliteMaintenance(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if h.satelliteMaintenanceJob == nil {
		h.log.Warn().Msg("Satellite maintenance job not registered yet")
		h.writeJSON(w, map[string]string{
			"status":  "error",
			"message": "Satellite maintenance job not registered",
		})
		return
	}

	h.log.Info().Msg("Manual satellite maintenance triggered")

	if err := h.scheduler.RunNow(h.satelliteMaintenanceJob); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger satellite maintenance")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Satellite maintenance triggered successfully",
	})
}

// HandleTriggerSatelliteReconciliation triggers the satellite reconciliation job immediately
// POST /api/jobs/satellite-reconciliation
func (h *SystemHandlers) HandleTriggerSatelliteReconciliation(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if h.satelliteReconciliationJob == nil {
		h.log.Warn().Msg("Satellite reconciliation job not registered yet")
		h.writeJSON(w, map[string]string{
			"status":  "error",
			"message": "Satellite reconciliation job not registered",
		})
		return
	}

	h.log.Info().Msg("Manual satellite reconciliation triggered")

	if err := h.scheduler.RunNow(h.satelliteReconciliationJob); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger satellite reconciliation")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Satellite reconciliation triggered successfully",
	})
}

// HandleTriggerSatelliteEvaluation triggers the satellite evaluation job immediately
// POST /api/jobs/satellite-evaluation
func (h *SystemHandlers) HandleTriggerSatelliteEvaluation(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if h.satelliteEvaluationJob == nil {
		h.log.Warn().Msg("Satellite evaluation job not registered yet")
		h.writeJSON(w, map[string]string{
			"status":  "error",
			"message": "Satellite evaluation job not registered",
		})
		return
	}

	h.log.Info().Msg("Manual satellite evaluation triggered")

	if err := h.scheduler.RunNow(h.satelliteEvaluationJob); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger satellite evaluation")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Satellite evaluation triggered successfully",
	})
}

// HandleTriggerPlannerBatch triggers the planner batch job immediately
// POST /api/jobs/planner-batch
func (h *SystemHandlers) HandleTriggerPlannerBatch(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if h.plannerBatchJob == nil {
		h.log.Warn().Msg("Planner batch job not registered yet")
		h.writeJSON(w, map[string]string{
			"status":  "error",
			"message": "Planner batch job not registered",
		})
		return
	}

	h.log.Info().Msg("Manual planner batch triggered")

	if err := h.scheduler.RunNow(h.plannerBatchJob); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger planner batch")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Planner batch triggered successfully",
	})
}

// HandleTriggerEventBasedTrading triggers the event-based trading job immediately
// POST /api/jobs/event-based-trading
func (h *SystemHandlers) HandleTriggerEventBasedTrading(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if h.eventBasedTradingJob == nil {
		h.log.Warn().Msg("Event-based trading job not registered yet")
		h.writeJSON(w, map[string]string{
			"status":  "error",
			"message": "Event-based trading job not registered",
		})
		return
	}

	h.log.Info().Msg("Manual event-based trading triggered")

	if err := h.scheduler.RunNow(h.eventBasedTradingJob); err != nil {
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

	// TODO: Implement portfolio sync in Go
	// For now, this is handled by the sync_cycle job which includes portfolio sync
	// The sync cycle job calls cash_flows sync which includes portfolio sync

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Portfolio sync delegated to sync cycle (handled by cash flows module)",
	})
}

// HandleSyncDailyPipeline triggers daily pipeline (securities data sync)
// POST /api/system/sync/daily-pipeline
// This is an alias for /sync/securities-data for backwards compatibility
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

	// TODO: Implement recommendation generation in Go
	// This requires:
	// 1. Clear recommendation caches
	// 2. Generate fresh recommendations via planning module
	// 3. Update LED display
	//
	// For now, recommendations are generated on-demand via:
	// POST /api/planning/recommendations or POST /api/trades/recommendations

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Recommendations are generated on-demand via planning module",
		"note":    "Use POST /api/planning/recommendations or POST /api/trades/recommendations",
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
