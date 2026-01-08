// Package server provides the HTTP server and routing for Sentinel.
package server

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/aristath/sentinel/internal/clients/tradernet"
	"github.com/aristath/sentinel/internal/database"
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/display"
	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/internal/queue"
	"github.com/aristath/sentinel/internal/scheduler"
	"github.com/aristath/sentinel/internal/services"
	"github.com/rs/zerolog"
	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/mem"
)

// SystemHandlers handles system-wide monitoring and operations endpoints - NEW 8-database architecture
type SystemHandlers struct {
	log                     zerolog.Logger
	dataDir                 string
	portfolioDB             *database.DB
	configDB                *database.DB
	universeDB              *database.DB
	historyDB               *database.DB
	queueManager            *queue.Manager
	portfolioDisplayCalc    *display.PortfolioDisplayCalculator
	displayManager          *display.StateManager
	tradernetClient         *tradernet.Client
	currencyExchangeService *services.CurrencyExchangeService
	cashManager             domain.CashManager
	marketHoursService      *market_hours.MarketHoursService
	// Jobs (will be set after job registration in main.go)
	// Original composite jobs
	healthCheckJob       scheduler.Job
	syncCycleJob         scheduler.Job
	dividendReinvestJob  scheduler.Job
	plannerBatchJob      scheduler.Job
	eventBasedTradingJob scheduler.Job
	tagUpdateJob         scheduler.Job

	// Individual sync jobs
	syncTradesJob            scheduler.Job
	syncCashFlowsJob         scheduler.Job
	syncPortfolioJob         scheduler.Job
	syncPricesJob            scheduler.Job
	checkNegativeBalancesJob scheduler.Job
	updateDisplayTickerJob   scheduler.Job

	// Individual planning jobs
	generatePortfolioHashJob   scheduler.Job
	getOptimizerWeightsJob     scheduler.Job
	buildOpportunityContextJob scheduler.Job
	createTradePlanJob         scheduler.Job
	storeRecommendationsJob    scheduler.Job

	// Individual dividend jobs
	getUnreinvestedDividendsJob      scheduler.Job
	groupDividendsBySymbolJob        scheduler.Job
	checkDividendYieldsJob           scheduler.Job
	createDividendRecommendationsJob scheduler.Job
	setPendingBonusesJob             scheduler.Job
	executeDividendTradesJob         scheduler.Job

	// Individual health check jobs
	checkCoreDatabasesJob    scheduler.Job
	checkHistoryDatabasesJob scheduler.Job
	checkWALCheckpointsJob   scheduler.Job
}

// NewSystemHandlers creates a new system handlers instance
func NewSystemHandlers(
	log zerolog.Logger,
	dataDir string,
	portfolioDB, configDB, universeDB, historyDB *database.DB,
	queueManager *queue.Manager,
	displayManager *display.StateManager,
	tradernetClient *tradernet.Client,
	currencyExchangeService *services.CurrencyExchangeService,
	cashManager domain.CashManager,
	marketHoursService *market_hours.MarketHoursService,
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
		historyDB.Conn(),
		portfolioPerf,
		log,
	)

	return &SystemHandlers{
		log:                     log.With().Str("component", "system_handlers").Logger(),
		dataDir:                 dataDir,
		portfolioDB:             portfolioDB,
		configDB:                configDB,
		universeDB:              universeDB,
		historyDB:               historyDB,
		queueManager:            queueManager,
		portfolioDisplayCalc:    portfolioDisplayCalc,
		displayManager:          displayManager,
		marketHoursService:      marketHoursService,
		tradernetClient:         tradernetClient,
		currencyExchangeService: currencyExchangeService,
		cashManager:             cashManager,
	}
}

// SetJobs registers job references for manual triggering
// Called after jobs are registered in main.go
func (h *SystemHandlers) SetJobs(
	healthCheck scheduler.Job,
	syncCycle scheduler.Job,
	dividendReinvest scheduler.Job,
	plannerBatch scheduler.Job,
	eventBasedTrading scheduler.Job,
	tagUpdate scheduler.Job,
	// Individual sync jobs
	syncTrades scheduler.Job,
	syncCashFlows scheduler.Job,
	syncPortfolio scheduler.Job,
	syncPrices scheduler.Job,
	checkNegativeBalances scheduler.Job,
	updateDisplayTicker scheduler.Job,
	// Individual planning jobs
	generatePortfolioHash scheduler.Job,
	getOptimizerWeights scheduler.Job,
	buildOpportunityContext scheduler.Job,
	createTradePlan scheduler.Job,
	storeRecommendations scheduler.Job,
	// Individual dividend jobs
	getUnreinvestedDividends scheduler.Job,
	groupDividendsBySymbol scheduler.Job,
	checkDividendYields scheduler.Job,
	createDividendRecommendations scheduler.Job,
	setPendingBonuses scheduler.Job,
	executeDividendTrades scheduler.Job,
	// Individual health check jobs
	checkCoreDatabases scheduler.Job,
	checkHistoryDatabases scheduler.Job,
	checkWALCheckpoints scheduler.Job,
) {
	h.healthCheckJob = healthCheck
	h.syncCycleJob = syncCycle
	h.dividendReinvestJob = dividendReinvest
	h.plannerBatchJob = plannerBatch
	h.eventBasedTradingJob = eventBasedTrading
	h.tagUpdateJob = tagUpdate

	// Individual sync jobs
	h.syncTradesJob = syncTrades
	h.syncCashFlowsJob = syncCashFlows
	h.syncPortfolioJob = syncPortfolio
	h.syncPricesJob = syncPrices
	h.checkNegativeBalancesJob = checkNegativeBalances
	h.updateDisplayTickerJob = updateDisplayTicker

	// Individual planning jobs
	h.generatePortfolioHashJob = generatePortfolioHash
	h.getOptimizerWeightsJob = getOptimizerWeights
	h.buildOpportunityContextJob = buildOpportunityContext
	h.createTradePlanJob = createTradePlan
	h.storeRecommendationsJob = storeRecommendations

	// Individual dividend jobs
	h.getUnreinvestedDividendsJob = getUnreinvestedDividends
	h.groupDividendsBySymbolJob = groupDividendsBySymbol
	h.checkDividendYieldsJob = checkDividendYields
	h.createDividendRecommendationsJob = createDividendRecommendations
	h.setPendingBonusesJob = setPendingBonuses
	h.executeDividendTradesJob = executeDividendTrades

	// Individual health check jobs
	h.checkCoreDatabasesJob = checkCoreDatabases
	h.checkHistoryDatabasesJob = checkHistoryDatabases
	h.checkWALCheckpointsJob = checkWALCheckpoints
}

// SetTagUpdateJob sets the tag update job (called after job registration)
func (h *SystemHandlers) SetTagUpdateJob(tagUpdate scheduler.Job) {
	h.tagUpdateJob = tagUpdate
}

// enqueueJob is a helper to enqueue a job for manual execution
func (h *SystemHandlers) enqueueJob(jobType queue.JobType, priority queue.Priority) error {
	job := &queue.Job{
		ID:          fmt.Sprintf("manual-%s-%d", jobType, time.Now().UnixNano()),
		Type:        jobType,
		Priority:    priority,
		Payload:     map[string]interface{}{"manual": true},
		CreatedAt:   time.Now(),
		AvailableAt: time.Now(),
		Retries:     0,
		MaxRetries:  3,
	}
	return h.queueManager.Enqueue(job)
}

// SystemStatusResponse represents the system status response
type SystemStatusResponse struct {
	Status           string  `json:"status"`             // "healthy" or "unhealthy"
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
	var lastSync sql.NullString
	var totalPositionCount int

	err := h.portfolioDB.Conn().QueryRow(`
		SELECT COUNT(*), MAX(last_updated)
		FROM positions
	`).Scan(&totalPositionCount, &lastSync)

	if err != nil && err != sql.ErrNoRows {
		h.log.Error().Err(err).Msg("Failed to query positions")
	}

	// Active positions count (all positions are now non-cash)
	activePositionCount := totalPositionCount

	// Format last sync time if available
	var lastSyncFormatted string
	if lastSync.Valid && lastSync.String != "" {
		// Parse and reformat to "YYYY-MM-DD HH:MM"
		if t, err := time.Parse(time.RFC3339, lastSync.String); err == nil {
			lastSyncFormatted = t.Format("2006-01-02 15:04")
		} else {
			lastSyncFormatted = lastSync.String
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

	// Get cash balances from CashManager
	cashBalances, err := h.cashManager.GetAllCashBalances()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get cash balances")
		// Fallback to zero balances on error
		cashBalances = make(map[string]float64)
	}

	// Calculate EUR-only cash balance
	var cashBalanceEUR float64
	if eurBalance, ok := cashBalances["EUR"]; ok {
		cashBalanceEUR = eurBalance
	}

	// Calculate total cash balance in EUR (all currencies converted)
	var totalCashEUR float64
	for currency, balance := range cashBalances {
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

	response := SystemStatusResponse{
		Status:           "healthy",
		CashBalanceEUR:   cashBalanceEUR,
		CashBalanceTotal: totalCashEUR,
		CashBalance:      totalCashEUR, // Backward compatibility
		SecurityCount:    securityCount,
		PositionCount:    totalPositionCount,
		ActivePositions:  activePositionCount,
		LastSync:         lastSyncFormatted,
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
		// Calculate actual CPU and RAM percentages
		cpuPercent, ramPercent := h.getSystemStats()
		response.SystemStats = map[string]interface{}{
			"uptime_hours": 0, // TODO: Calculate actual uptime
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

// RefreshCredentials refreshes tradernet client credentials from settings database
func (h *SystemHandlers) RefreshCredentials() error {
	if h.tradernetClient == nil {
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
		h.tradernetClient.SetCredentials(*apiKey, *apiSecret)
		h.log.Info().Msg("Tradernet client credentials refreshed from settings database")
		return nil
	}

	return fmt.Errorf("credentials not found in settings database")
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

// calculateNextOpenCloseTimes removed - market hours functionality removed

// HandleMarketsStatus returns market open/close status grouped by geography
func (h *SystemHandlers) HandleMarketsStatus(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting markets status")

	if h.marketHoursService == nil {
		h.log.Warn().Msg("Market hours service not available")
		markets := make(map[string]MarketRegionInfo)
		response := MarketsStatusResponse{
			Markets:     markets,
			OpenCount:   0,
			ClosedCount: 0,
			LastUpdated: time.Now().Format(time.RFC3339),
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
		return
	}

	// Get distinct exchanges from universe database
	securityRepo := universe.NewSecurityRepository(h.universeDB.Conn(), h.log)
	exchanges, err := securityRepo.GetDistinctExchanges()
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get exchanges from database")
		exchanges = []string{}
	}

	// If no exchanges found, return empty response
	if len(exchanges) == 0 {
		markets := make(map[string]MarketRegionInfo)
		response := MarketsStatusResponse{
			Markets:     markets,
			OpenCount:   0,
			ClosedCount: 0,
			LastUpdated: time.Now().Format(time.RFC3339),
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
		return
	}

	// Group exchanges by region and get status
	now := time.Now()
	markets := make(map[string]MarketRegionInfo)
	openCount := 0
	closedCount := 0

	// Group exchanges by region
	regionMap := make(map[string][]string)
	for _, exchangeName := range exchanges {
		region := h.getExchangeRegion(exchangeName)
		regionMap[region] = append(regionMap[region], exchangeName)
	}

	// Get status for each region
	for region, exchangeNames := range regionMap {
		regionOpen := false
		var closesAt, opensAt, opensDate string

		// Check if any exchange in region is open
		for _, exchangeName := range exchangeNames {
			status, err := h.marketHoursService.GetMarketStatus(exchangeName, now)
			if err != nil {
				h.log.Debug().Err(err).Str("exchange", exchangeName).Msg("Failed to get market status")
				continue
			}

			if status.Open {
				regionOpen = true
				if closesAt == "" {
					closesAt = status.ClosesAt
				}
				openCount++
			} else {
				closedCount++
				if opensAt == "" {
					opensAt = status.OpensAt
					opensDate = status.OpensDate
				}
			}
		}

		markets[region] = MarketRegionInfo{
			Open:      regionOpen,
			ClosesAt:  closesAt,
			OpensAt:   opensAt,
			OpensDate: opensDate,
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

// getExchangeRegion returns the geographic region for an exchange
func (h *SystemHandlers) getExchangeRegion(exchangeName string) string {
	exchangeCode := market_hours.GetExchangeCode(exchangeName)

	// US exchanges
	if exchangeCode == "XNYS" || exchangeCode == "XNAS" {
		return "US"
	}

	// European exchanges
	if exchangeCode == "XETR" || exchangeCode == "XLON" || exchangeCode == "XPAR" ||
		exchangeCode == "XMIL" || exchangeCode == "XAMS" || exchangeCode == "XCSE" ||
		exchangeCode == "ASEX" {
		return "EU"
	}

	// Asian exchanges
	if exchangeCode == "XHKG" || exchangeCode == "XSHG" || exchangeCode == "XTSE" ||
		exchangeCode == "XASX" {
		return "ASIA"
	}

	// Default to US
	return "US"
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

	// Enqueue sync cycle job
	job := &queue.Job{
		ID:          fmt.Sprintf("manual-sync-cycle-%d", time.Now().UnixNano()),
		Type:        queue.JobTypeSyncCycle,
		Priority:    queue.PriorityHigh,
		Payload:     map[string]interface{}{"manual": true},
		CreatedAt:   time.Now(),
		AvailableAt: time.Now(),
		Retries:     0,
		MaxRetries:  3,
	}
	if err := h.queueManager.Enqueue(job); err != nil {
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

	if err := h.enqueueJob(queue.JobTypeHealthCheck, queue.PriorityMedium); err != nil {
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

	if err := h.enqueueJob(queue.JobTypeDividendReinvest, queue.PriorityHigh); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger dividend reinvestment")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Dividend reinvestment triggered successfully",
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

	if err := h.enqueueJob(queue.JobTypePlannerBatch, queue.PriorityHigh); err != nil {
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

	if err := h.enqueueJob(queue.JobTypeEventBasedTrading, queue.PriorityCritical); err != nil {
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

// HandleTriggerTagUpdate triggers the tag update job immediately
// POST /api/jobs/tag-update
func (h *SystemHandlers) HandleTriggerTagUpdate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if h.tagUpdateJob == nil {
		h.log.Warn().Msg("Tag update job not registered yet")
		h.writeJSON(w, map[string]string{
			"status":  "error",
			"message": "Tag update job not registered",
		})
		return
	}

	h.log.Info().Msg("Manual tag update triggered")

	if err := h.enqueueJob(queue.JobTypeTagUpdate, queue.PriorityMedium); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger tag update")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Tag update triggered successfully",
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
	if h.syncTradesJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Sync trades job not registered"})
		return
	}
	h.log.Info().Msg("Manual sync trades triggered")
	if err := h.enqueueJob(queue.JobTypeSyncTrades, queue.PriorityHigh); err != nil {
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
	if h.syncCashFlowsJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Sync cash flows job not registered"})
		return
	}
	h.log.Info().Msg("Manual sync cash flows triggered")
	if err := h.enqueueJob(queue.JobTypeSyncCashFlows, queue.PriorityHigh); err != nil {
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
	if h.syncPortfolioJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Sync portfolio job not registered"})
		return
	}
	h.log.Info().Msg("Manual sync portfolio triggered")
	if err := h.enqueueJob(queue.JobTypeSyncPortfolio, queue.PriorityHigh); err != nil {
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
	if h.syncPricesJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Sync prices job not registered"})
		return
	}
	h.log.Info().Msg("Manual sync prices triggered")
	if err := h.enqueueJob(queue.JobTypeSyncPrices, queue.PriorityHigh); err != nil {
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
	if h.checkNegativeBalancesJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Check negative balances job not registered"})
		return
	}
	h.log.Info().Msg("Manual check negative balances triggered")
	if err := h.enqueueJob(queue.JobTypeCheckNegativeBalances, queue.PriorityCritical); err != nil {
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
	if h.updateDisplayTickerJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Update display ticker job not registered"})
		return
	}
	h.log.Info().Msg("Manual update display ticker triggered")
	if err := h.enqueueJob(queue.JobTypeUpdateDisplayTicker, queue.PriorityLow); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Update display ticker triggered successfully"})
}

// ==========================================
// INDIVIDUAL PLANNING JOB HANDLERS
// ==========================================

func (h *SystemHandlers) HandleTriggerGeneratePortfolioHash(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if h.generatePortfolioHashJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Generate portfolio hash job not registered"})
		return
	}
	h.log.Info().Msg("Manual generate portfolio hash triggered")
	if err := h.enqueueJob(queue.JobTypeGeneratePortfolioHash, queue.PriorityMedium); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Generate portfolio hash triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerGetOptimizerWeights(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if h.getOptimizerWeightsJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Get optimizer weights job not registered"})
		return
	}
	h.log.Info().Msg("Manual get optimizer weights triggered")
	if err := h.enqueueJob(queue.JobTypeGetOptimizerWeights, queue.PriorityMedium); err != nil {
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
	if h.buildOpportunityContextJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Build opportunity context job not registered"})
		return
	}
	h.log.Info().Msg("Manual build opportunity context triggered")
	if err := h.enqueueJob(queue.JobTypeBuildOpportunityContext, queue.PriorityMedium); err != nil {
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
	if h.createTradePlanJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Create trade plan job not registered"})
		return
	}
	h.log.Info().Msg("Manual create trade plan triggered")
	if err := h.enqueueJob(queue.JobTypeCreateTradePlan, queue.PriorityMedium); err != nil {
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
	if h.storeRecommendationsJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Store recommendations job not registered"})
		return
	}
	h.log.Info().Msg("Manual store recommendations triggered")
	if err := h.enqueueJob(queue.JobTypeStoreRecommendations, queue.PriorityMedium); err != nil {
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
	if h.getUnreinvestedDividendsJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Get unreinvested dividends job not registered"})
		return
	}
	h.log.Info().Msg("Manual get unreinvested dividends triggered")
	if err := h.enqueueJob(queue.JobTypeGetUnreinvestedDividends, queue.PriorityMedium); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Get unreinvested dividends triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerGroupDividendsBySymbol(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if h.groupDividendsBySymbolJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Group dividends by symbol job not registered"})
		return
	}
	h.log.Info().Msg("Manual group dividends by symbol triggered")
	if err := h.enqueueJob(queue.JobTypeGroupDividendsBySymbol, queue.PriorityMedium); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Group dividends by symbol triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerCheckDividendYields(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if h.checkDividendYieldsJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Check dividend yields job not registered"})
		return
	}
	h.log.Info().Msg("Manual check dividend yields triggered")
	if err := h.enqueueJob(queue.JobTypeCheckDividendYields, queue.PriorityMedium); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Check dividend yields triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerCreateDividendRecommendations(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if h.createDividendRecommendationsJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Create dividend recommendations job not registered"})
		return
	}
	h.log.Info().Msg("Manual create dividend recommendations triggered")
	if err := h.enqueueJob(queue.JobTypeCreateDividendRecommendations, queue.PriorityMedium); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Create dividend recommendations triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerSetPendingBonuses(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if h.setPendingBonusesJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Set pending bonuses job not registered"})
		return
	}
	h.log.Info().Msg("Manual set pending bonuses triggered")
	if err := h.enqueueJob(queue.JobTypeSetPendingBonuses, queue.PriorityMedium); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Set pending bonuses triggered successfully"})
}

func (h *SystemHandlers) HandleTriggerExecuteDividendTrades(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if h.executeDividendTradesJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Execute dividend trades job not registered"})
		return
	}
	h.log.Info().Msg("Manual execute dividend trades triggered")
	if err := h.enqueueJob(queue.JobTypeExecuteDividendTrades, queue.PriorityHigh); err != nil {
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
	if h.checkCoreDatabasesJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Check core databases job not registered"})
		return
	}
	h.log.Info().Msg("Manual check core databases triggered")
	if err := h.enqueueJob(queue.JobTypeCheckCoreDatabases, queue.PriorityHigh); err != nil {
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
	if h.checkHistoryDatabasesJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Check history databases job not registered"})
		return
	}
	h.log.Info().Msg("Manual check history databases triggered")
	if err := h.enqueueJob(queue.JobTypeCheckHistoryDatabases, queue.PriorityHigh); err != nil {
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
	if h.checkWALCheckpointsJob == nil {
		h.writeJSON(w, map[string]string{"status": "error", "message": "Check WAL checkpoints job not registered"})
		return
	}
	h.log.Info().Msg("Manual check WAL checkpoints triggered")
	if err := h.enqueueJob(queue.JobTypeCheckWALCheckpoints, queue.PriorityMedium); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, map[string]string{"status": "success", "message": "Check WAL checkpoints triggered successfully"})
}

// writeJSON writes a JSON response
func (h *SystemHandlers) writeJSON(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(data); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode JSON response")
		http.Error(w, "Internal server error", http.StatusInternalServerError)
	}
}
