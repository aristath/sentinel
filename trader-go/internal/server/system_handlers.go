package server

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/internal/modules/display"
	"github.com/aristath/arduino-trader/internal/scheduler"
	"github.com/rs/zerolog"
)

// SystemHandlers handles system-wide monitoring and operations endpoints
type SystemHandlers struct {
	log                  zerolog.Logger
	dataDir              string
	stateDB              *database.DB
	settingsDB           *database.DB
	snapshotsDB          *database.DB
	configDB             *database.DB
	marketHours          *scheduler.MarketHoursService
	scheduler            *scheduler.Scheduler
	portfolioDisplayCalc *display.PortfolioDisplayCalculator
	// Jobs (will be set after job registration in main.go)
	syncCycleJob         scheduler.Job
	weeklyMaintenanceJob scheduler.Job
	dividendReinvestJob  scheduler.Job
	plannerBatchJob      scheduler.Job
	dailyMaintenanceJob  scheduler.Job
}

// NewSystemHandlers creates a new system handlers instance
func NewSystemHandlers(
	log zerolog.Logger,
	dataDir string,
	stateDB, settingsDB, snapshotsDB, configDB *database.DB,
	sched *scheduler.Scheduler,
) *SystemHandlers {
	// Create portfolio performance service
	portfolioPerf := display.NewPortfolioPerformanceService(
		snapshotsDB.Conn(),
		settingsDB.Conn(),
		log,
	)

	// Create portfolio display calculator
	portfolioDisplayCalc := display.NewPortfolioDisplayCalculator(
		configDB.Conn(),
		stateDB.Conn(),
		snapshotsDB.Conn(),
		settingsDB.Conn(),
		portfolioPerf,
		log,
	)

	return &SystemHandlers{
		log:                  log.With().Str("component", "system_handlers").Logger(),
		dataDir:              dataDir,
		stateDB:              stateDB,
		settingsDB:           settingsDB,
		snapshotsDB:          snapshotsDB,
		configDB:             configDB,
		marketHours:          scheduler.NewMarketHoursService(log),
		scheduler:            sched,
		portfolioDisplayCalc: portfolioDisplayCalc,
	}
}

// SetJobs registers job references for manual triggering
// Called after jobs are registered in main.go
func (h *SystemHandlers) SetJobs(
	syncCycle scheduler.Job,
	weeklyMaintenance scheduler.Job,
	dividendReinvest scheduler.Job,
	plannerBatch scheduler.Job,
	dailyMaintenance scheduler.Job,
) {
	h.syncCycleJob = syncCycle
	h.weeklyMaintenanceJob = weeklyMaintenance
	h.dividendReinvestJob = dividendReinvest
	h.plannerBatchJob = plannerBatch
	h.dailyMaintenanceJob = dailyMaintenance
}

// SystemStatusResponse represents the system status response
type SystemStatusResponse struct {
	CashBalance    float64 `json:"cash_balance"`
	SecurityCount  int     `json:"security_count"`
	PositionCount  int     `json:"position_count"`
	LastSync       string  `json:"last_sync,omitempty"`
	UniverseActive int     `json:"universe_active"`
}

// LEDDisplayResponse represents the LED display state
type LEDDisplayResponse struct {
	Mode           string                 `json:"mode"`                      // "STATS", "TICKER", or "PORTFOLIO"
	CurrentPanel   int                    `json:"current_panel"`             // For TICKER mode
	SystemStats    map[string]interface{} `json:"system_stats,omitempty"`    // For STATS mode
	PortfolioState interface{}            `json:"portfolio_state,omitempty"` // For PORTFOLIO mode
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
	Markets     []MarketInfo `json:"markets"`
	OpenCount   int          `json:"open_count"`
	ClosedCount int          `json:"closed_count"`
	LastUpdated string       `json:"last_updated"`
}

// MarketInfo represents status of a single market
type MarketInfo struct {
	Exchange string `json:"exchange"` // "NASDAQ", "NYSE", "LSE", etc.
	IsOpen   bool   `json:"is_open"`
	Timezone string `json:"timezone"`
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
	var positionCount int

	err := h.stateDB.Conn().QueryRow(`
		SELECT COUNT(*), MAX(last_updated)
		FROM positions
	`).Scan(&positionCount, &lastSync)

	if err != nil && err != sql.ErrNoRows {
		h.log.Error().Err(err).Msg("Failed to query positions")
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
	err = h.stateDB.Conn().QueryRow(`
		SELECT COUNT(*) FROM securities WHERE is_active = 1
	`).Scan(&securityCount)

	if err != nil && err != sql.ErrNoRows {
		h.log.Error().Err(err).Msg("Failed to query securities")
	}

	// Get cash balance from ledger
	var cashBalance float64
	// TODO: Query actual cash balance from ledger database
	// For now, use placeholder
	cashBalance = 0.0

	response := SystemStatusResponse{
		CashBalance:    cashBalance,
		SecurityCount:  securityCount,
		PositionCount:  positionCount,
		LastSync:       lastSync,
		UniverseActive: securityCount,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleLEDDisplay returns LED display state
func (h *SystemHandlers) HandleLEDDisplay(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting LED display state")

	// Get display mode from settings
	var displayMode string
	err := h.settingsDB.Conn().QueryRow("SELECT value FROM settings WHERE key = 'display_mode'").Scan(&displayMode)
	if err != nil {
		// Default to STATS if setting not found
		displayMode = "STATS"
		h.log.Debug().Err(err).Msg("display_mode setting not found, defaulting to STATS")
	}

	response := LEDDisplayResponse{
		Mode:         displayMode,
		CurrentPanel: 0,
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
		// TODO: Implement ticker mode
		h.log.Debug().Msg("TICKER mode not yet implemented")

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

	// TODO: Integrate with actual Tradernet client
	response := TradernetStatusResponse{
		Connected: false,
		LastCheck: time.Now().Format(time.RFC3339),
		Message:   "Tradernet client not yet implemented in Go",
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

// HandleMarketsStatus returns market open/close status
func (h *SystemHandlers) HandleMarketsStatus(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting markets status")

	// Get real-time market statuses
	statuses := h.marketHours.GetAllMarketStatuses()

	markets := make([]MarketInfo, 0, len(statuses))
	openCount := 0
	closedCount := 0

	for _, status := range statuses {
		markets = append(markets, MarketInfo{
			Exchange: status.Exchange,
			IsOpen:   status.IsOpen,
			Timezone: status.Timezone,
		})

		if status.IsOpen {
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

// HandleTriggerWeeklyMaintenance triggers the weekly maintenance job immediately
// POST /api/jobs/weekly-maintenance
func (h *SystemHandlers) HandleTriggerWeeklyMaintenance(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if h.weeklyMaintenanceJob == nil {
		h.log.Warn().Msg("Weekly maintenance job not registered yet")
		h.writeJSON(w, map[string]string{
			"status":  "error",
			"message": "Weekly maintenance job not registered",
		})
		return
	}

	h.log.Info().Msg("Manual weekly maintenance triggered")

	if err := h.scheduler.RunNow(h.weeklyMaintenanceJob); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger weekly maintenance")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Weekly maintenance triggered successfully",
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

// HandleTriggerPlannerBatch triggers the planner batch generation job immediately
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

	h.log.Info().Msg("Manual planner batch generation triggered")

	if err := h.scheduler.RunNow(h.plannerBatchJob); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger planner batch")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Planner batch generation triggered successfully",
	})
}

// HandleTriggerDailyMaintenance triggers the daily maintenance job immediately
// POST /api/maintenance/daily
func (h *SystemHandlers) HandleTriggerDailyMaintenance(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if h.dailyMaintenanceJob == nil {
		h.log.Warn().Msg("Daily maintenance job not registered yet")
		h.writeJSON(w, map[string]string{
			"status":  "error",
			"message": "Daily maintenance job not registered",
		})
		return
	}

	h.log.Info().Msg("Manual daily maintenance triggered")

	if err := h.scheduler.RunNow(h.dailyMaintenanceJob); err != nil {
		h.log.Error().Err(err).Msg("Failed to trigger daily maintenance")
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, map[string]string{
		"status":  "success",
		"message": "Daily maintenance triggered successfully",
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

// HandleClearLocks clears stuck lock files
// POST /api/system/locks/clear
func (h *SystemHandlers) HandleClearLocks(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Get optional lock_name query parameter
	lockName := r.URL.Query().Get("lock_name")

	h.log.Info().
		Str("lock_name", lockName).
		Msg("Manual lock clearing triggered")

	lockDir := filepath.Join(h.dataDir, "locks")
	cleared := []string{}

	// Check if lock directory exists
	if _, err := os.Stat(lockDir); os.IsNotExist(err) {
		h.writeJSON(w, map[string]interface{}{
			"status":  "ok",
			"message": "No lock directory found",
			"cleared": cleared,
		})
		return
	}

	// If specific lock name provided, clear just that one
	if lockName != "" {
		lockFile := filepath.Join(lockDir, lockName+".lock")
		if err := os.Remove(lockFile); err == nil {
			cleared = append(cleared, lockName)
			h.log.Info().Str("lock", lockName).Msg("Cleared lock file")
		} else if !os.IsNotExist(err) {
			h.log.Error().Err(err).Str("lock", lockName).Msg("Failed to clear lock file")
			http.Error(w, "Failed to clear lock: "+err.Error(), http.StatusInternalServerError)
			return
		}
	} else {
		// Clear all lock files
		files, err := os.ReadDir(lockDir)
		if err != nil {
			h.log.Error().Err(err).Msg("Failed to read lock directory")
			http.Error(w, "Failed to read lock directory", http.StatusInternalServerError)
			return
		}

		for _, file := range files {
			if !file.IsDir() && filepath.Ext(file.Name()) == ".lock" {
				lockFile := filepath.Join(lockDir, file.Name())
				if err := os.Remove(lockFile); err == nil {
					lockName := file.Name()[:len(file.Name())-5] // Remove .lock extension
					cleared = append(cleared, lockName)
					h.log.Info().Str("lock", lockName).Msg("Cleared lock file")
				} else {
					h.log.Error().Err(err).Str("file", file.Name()).Msg("Failed to clear lock file")
				}
			}
		}
	}

	h.writeJSON(w, map[string]interface{}{
		"status":  "ok",
		"message": "Lock files cleared successfully",
		"cleared": cleared,
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
