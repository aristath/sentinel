package reliability

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/rs/zerolog"
)

// AlertLevel defines the severity of an alert
type AlertLevel string

const (
	AlertCritical AlertLevel = "CRITICAL" // Halt system, require manual intervention
	AlertError    AlertLevel = "ERROR"    // Auto-recover if possible, alert admin
	AlertWarning  AlertLevel = "WARNING"  // Log and monitor
	AlertInfo     AlertLevel = "INFO"     // Informational
)

// Alert represents a monitoring alert
type Alert struct {
	Level     AlertLevel
	Component string
	Message   string
	Timestamp time.Time
	Metadata  map[string]interface{}
}

// MonitoringService manages database monitoring and alerting
// Implements comprehensive monitoring as specified in architecture plan
type MonitoringService struct {
	databases      map[string]*database.DB
	healthServices map[string]*DatabaseHealthService
	dataDir        string
	backupDir      string
	alerts         []Alert
	log            zerolog.Logger
}

// NewMonitoringService creates a new monitoring service
func NewMonitoringService(
	databases map[string]*database.DB,
	healthServices map[string]*DatabaseHealthService,
	dataDir string,
	backupDir string,
	log zerolog.Logger,
) *MonitoringService {
	return &MonitoringService{
		databases:      databases,
		healthServices: healthServices,
		dataDir:        dataDir,
		backupDir:      backupDir,
		alerts:         make([]Alert, 0),
		log:            log.With().Str("service", "monitoring").Logger(),
	}
}

// CollectMetrics collects metrics from all databases
func (s *MonitoringService) CollectMetrics() (map[string]*DatabaseMetrics, error) {
	metrics := make(map[string]*DatabaseMetrics)

	for name, healthService := range s.healthServices {
		dbMetrics, err := healthService.GetMetrics()
		if err != nil {
			s.log.Error().
				Str("database", name).
				Err(err).
				Msg("Failed to collect metrics")
			continue
		}

		// Calculate 24h growth rate
		dbMetrics.GrowthRate24h = s.calculate24hGrowth(name, dbMetrics.SizeMB)

		metrics[name] = dbMetrics
	}

	return metrics, nil
}

// calculate24hGrowth calculates database growth rate over last 24 hours
func (s *MonitoringService) calculate24hGrowth(dbName string, currentSizeMB float64) float64 {
	healthService, ok := s.healthServices[dbName]
	if !ok {
		return 0
	}

	// Get size from 24 hours ago
	twentyFourHoursAgo := time.Now().Add(-24 * time.Hour).Unix()
	var oldSize sql.NullInt64

	err := healthService.db.Conn().QueryRow(`
		SELECT size_bytes FROM _database_health
		WHERE checked_at >= ?
		ORDER BY checked_at ASC
		LIMIT 1
	`, twentyFourHoursAgo).Scan(&oldSize)

	if err != nil || !oldSize.Valid || oldSize.Int64 == 0 {
		return 0
	}

	oldSizeMB := float64(oldSize.Int64) / 1024 / 1024
	growthRate := ((currentSizeMB - oldSizeMB) / oldSizeMB) * 100

	return growthRate
}

// CheckAlerts evaluates all alert conditions and generates alerts
func (s *MonitoringService) CheckAlerts() error {
	s.log.Debug().Msg("Checking alert conditions")

	// Clear previous alerts
	s.alerts = make([]Alert, 0)

	// Check disk space
	s.checkDiskSpaceAlerts()

	// Check database metrics
	metrics, err := s.CollectMetrics()
	if err != nil {
		return fmt.Errorf("failed to collect metrics: %w", err)
	}

	for dbName, dbMetrics := range metrics {
		s.checkDatabaseAlerts(dbName, dbMetrics)
	}

	// Check WAL file sizes
	s.checkWALSizeAlerts()

	// Check backup status
	s.checkBackupAlerts()

	// Log and process alerts
	s.processAlerts()

	return nil
}

// checkDiskSpaceAlerts checks disk space and generates alerts
func (s *MonitoringService) checkDiskSpaceAlerts() {
	stat := syscall.Statfs_t{}
	if err := syscall.Statfs(s.dataDir, &stat); err != nil {
		s.addAlert(AlertError, "disk", "Failed to check disk space", map[string]interface{}{
			"error": err.Error(),
		})
		return
	}

	availableBytes := stat.Bavail * uint64(stat.Bsize)
	availableGB := float64(availableBytes) / 1e9

	// CRITICAL: Less than 500MB
	if availableGB < 0.5 {
		s.addAlert(AlertCritical, "disk", "CRITICAL: Insufficient disk space - system should halt", map[string]interface{}{
			"available_gb": availableGB,
			"threshold_gb": 0.5,
		})
	} else if availableGB < 5.0 {
		// ERROR: Less than 5GB
		s.addAlert(AlertError, "disk", "Low disk space - consider cleanup", map[string]interface{}{
			"available_gb": availableGB,
			"threshold_gb": 5.0,
		})
	} else if availableGB < 10.0 {
		// WARNING: Less than 10GB
		s.addAlert(AlertWarning, "disk", "Disk space running low", map[string]interface{}{
			"available_gb": availableGB,
			"threshold_gb": 10.0,
		})
	}
}

// checkDatabaseAlerts checks database-specific alerts
func (s *MonitoringService) checkDatabaseAlerts(dbName string, metrics *DatabaseMetrics) {
	// Check integrity
	if !metrics.IntegrityCheckPassed {
		s.addAlert(AlertError, dbName, "Database integrity check failed", map[string]interface{}{
			"last_check": metrics.LastIntegrityCheck,
		})
	}

	// Check growth rate (24h)
	if metrics.GrowthRate24h > 50.0 {
		s.addAlert(AlertError, dbName, "Anomalous database growth > 50% in 24h", map[string]interface{}{
			"growth_rate_pct": metrics.GrowthRate24h,
			"size_mb":         metrics.SizeMB,
		})
	} else if metrics.GrowthRate24h > 20.0 {
		s.addAlert(AlertWarning, dbName, "High database growth > 20% in 24h", map[string]interface{}{
			"growth_rate_pct": metrics.GrowthRate24h,
			"size_mb":         metrics.SizeMB,
		})
	}

	// Info: Large database (consider archival)
	if metrics.SizeMB > 100.0 {
		s.addAlert(AlertInfo, dbName, "Database size > 100MB - consider archival strategy", map[string]interface{}{
			"size_mb": metrics.SizeMB,
		})
	}

	// Info: Ledger growth (normal, just tracking)
	if dbName == "ledger" && metrics.GrowthRate24h > 0 {
		s.addAlert(AlertInfo, dbName, "Ledger database growth (normal)", map[string]interface{}{
			"growth_rate_pct": metrics.GrowthRate24h,
			"size_mb":         metrics.SizeMB,
		})
	}
}

// checkWALSizeAlerts checks WAL file sizes
func (s *MonitoringService) checkWALSizeAlerts() {
	for dbName, db := range s.databases {
		// Get database file path from connection
		var path string
		err := db.Conn().QueryRow("PRAGMA database_list").Scan(nil, nil, &path)
		if err != nil {
			continue
		}

		// Check WAL file size
		walPath := path + "-wal"
		info, err := os.Stat(walPath)
		if err != nil {
			continue // WAL file doesn't exist or can't be read
		}

		walSizeMB := float64(info.Size()) / 1024 / 1024

		// ERROR: WAL > 100MB (checkpoint stuck?)
		if walSizeMB > 100.0 {
			s.addAlert(AlertError, dbName, "WAL file > 100MB - checkpoint may be stuck", map[string]interface{}{
				"wal_size_mb":  walSizeMB,
				"threshold_mb": 100.0,
			})
		}
	}
}

// checkBackupAlerts checks backup status
func (s *MonitoringService) checkBackupAlerts() {
	// Check if daily backup exists for today
	today := time.Now().Format("2006-01-02")
	dailyBackupDir := filepath.Join(s.backupDir, "daily", today)

	if _, err := os.Stat(dailyBackupDir); os.IsNotExist(err) {
		s.addAlert(AlertWarning, "backup", "Today's daily backup not found", map[string]interface{}{
			"expected_dir": dailyBackupDir,
		})
	}

	// Check if hourly backup exists (should be within last 2 hours)
	hourlyBackupDir := filepath.Join(s.backupDir, "hourly")
	if _, err := os.Stat(hourlyBackupDir); err == nil {
		entries, err := os.ReadDir(hourlyBackupDir)
		if err == nil && len(entries) > 0 {
			// Find most recent backup
			var mostRecentTime time.Time
			for _, entry := range entries {
				if entry.IsDir() {
					continue
				}
				info, err := entry.Info()
				if err == nil && info.ModTime().After(mostRecentTime) {
					mostRecentTime = info.ModTime()
				}
			}

			// Alert if most recent backup is > 2 hours old
			if time.Since(mostRecentTime) > 2*time.Hour {
				s.addAlert(AlertWarning, "backup", "Hourly backup is stale", map[string]interface{}{
					"last_backup": mostRecentTime,
					"age_hours":   time.Since(mostRecentTime).Hours(),
				})
			}
		}
	}
}

// addAlert adds an alert to the list
func (s *MonitoringService) addAlert(level AlertLevel, component, message string, metadata map[string]interface{}) {
	alert := Alert{
		Level:     level,
		Component: component,
		Message:   message,
		Timestamp: time.Now(),
		Metadata:  metadata,
	}
	s.alerts = append(s.alerts, alert)
}

// processAlerts logs and processes all alerts
func (s *MonitoringService) processAlerts() {
	if len(s.alerts) == 0 {
		s.log.Debug().Msg("No alerts to process")
		return
	}

	// Count alerts by level
	counts := make(map[AlertLevel]int)
	for _, alert := range s.alerts {
		counts[alert.Level]++

		// Log alert with appropriate level
		event := s.log.WithLevel(s.alertLevelToZerologLevel(alert.Level)).
			Str("component", alert.Component).
			Str("alert_level", string(alert.Level))

		// Add metadata fields
		for key, value := range alert.Metadata {
			event = event.Interface(key, value)
		}

		event.Msg(alert.Message)
	}

	// Summary log
	s.log.Info().
		Int("critical", counts[AlertCritical]).
		Int("error", counts[AlertError]).
		Int("warning", counts[AlertWarning]).
		Int("info", counts[AlertInfo]).
		Int("total", len(s.alerts)).
		Msg("Alert summary")
}

// alertLevelToZerologLevel converts AlertLevel to zerolog.Level
func (s *MonitoringService) alertLevelToZerologLevel(level AlertLevel) zerolog.Level {
	switch level {
	case AlertCritical:
		return zerolog.FatalLevel
	case AlertError:
		return zerolog.ErrorLevel
	case AlertWarning:
		return zerolog.WarnLevel
	case AlertInfo:
		return zerolog.InfoLevel
	default:
		return zerolog.InfoLevel
	}
}

// GetAlerts returns current alerts
func (s *MonitoringService) GetAlerts() []Alert {
	return s.alerts
}

// GetCriticalAlerts returns only critical alerts
func (s *MonitoringService) GetCriticalAlerts() []Alert {
	critical := make([]Alert, 0)
	for _, alert := range s.alerts {
		if alert.Level == AlertCritical {
			critical = append(critical, alert)
		}
	}
	return critical
}

// HasCriticalAlerts returns true if there are any critical alerts
func (s *MonitoringService) HasCriticalAlerts() bool {
	for _, alert := range s.alerts {
		if alert.Level == AlertCritical {
			return true
		}
	}
	return false
}

// AnalyzeDatabaseGrowth analyzes long-term database growth trends
func (s *MonitoringService) AnalyzeDatabaseGrowth() error {
	s.log.Info().Msg("Analyzing database growth trends")

	for dbName, healthService := range s.healthServices {
		// Get current metrics
		metrics, err := healthService.GetMetrics()
		if err != nil {
			s.log.Error().
				Str("database", dbName).
				Err(err).
				Msg("Failed to get metrics")
			continue
		}

		// Get historical sizes (30 days, 90 days, 1 year)
		growth30d := s.calculateGrowth(healthService, 30)
		growth90d := s.calculateGrowth(healthService, 90)
		growth1y := s.calculateGrowth(healthService, 365)

		// Project 10-year size
		var projected10y float64
		if growth1y > 0 {
			// Use 1-year growth rate to project 10 years
			projected10y = metrics.SizeMB * (1 + growth1y/100) * 10
		}

		s.log.Info().
			Str("database", dbName).
			Float64("current_size_mb", metrics.SizeMB).
			Float64("growth_30d_pct", growth30d).
			Float64("growth_90d_pct", growth90d).
			Float64("growth_1y_pct", growth1y).
			Float64("projected_10y_mb", projected10y).
			Msg("Database growth analysis")

		// Alert if projected 10-year size is concerning
		if projected10y > 1000.0 { // > 1GB
			s.addAlert(AlertWarning, dbName, "Projected 10-year size > 1GB", map[string]interface{}{
				"current_size_mb":  metrics.SizeMB,
				"projected_10y_mb": projected10y,
				"growth_1y_pct":    growth1y,
			})
		}
	}

	return nil
}

// calculateGrowth calculates growth rate over specified number of days
func (s *MonitoringService) calculateGrowth(healthService *DatabaseHealthService, days int) float64 {
	cutoff := time.Now().AddDate(0, 0, -days).Unix()

	var oldSize sql.NullInt64
	err := healthService.db.Conn().QueryRow(`
		SELECT size_bytes FROM _database_health
		WHERE checked_at >= ?
		ORDER BY checked_at ASC
		LIMIT 1
	`, cutoff).Scan(&oldSize)

	if err != nil || !oldSize.Valid || oldSize.Int64 == 0 {
		return 0
	}

	// Get current size
	metrics, err := healthService.GetMetrics()
	if err != nil {
		return 0
	}

	currentSize := metrics.SizeMB * 1024 * 1024
	growthRate := ((currentSize - float64(oldSize.Int64)) / float64(oldSize.Int64)) * 100

	return growthRate
}

// CheckConnectionPoolHealth checks for connection pool exhaustion
func (s *MonitoringService) CheckConnectionPoolHealth() error {
	for dbName, db := range s.databases {
		stats := db.Conn().Stats()

		// Check if pool is exhausted
		if stats.InUse >= stats.MaxOpenConnections {
			s.addAlert(AlertWarning, dbName, "Connection pool exhausted", map[string]interface{}{
				"in_use":     stats.InUse,
				"max_open":   stats.MaxOpenConnections,
				"idle":       stats.Idle,
				"wait_count": stats.WaitCount,
			})
		}

		// Check if wait count is high
		if stats.WaitCount > 100 {
			s.addAlert(AlertWarning, dbName, "High connection wait count", map[string]interface{}{
				"wait_count": stats.WaitCount,
				"in_use":     stats.InUse,
				"max_open":   stats.MaxOpenConnections,
			})
		}

		s.log.Debug().
			Str("database", dbName).
			Int("in_use", stats.InUse).
			Int("idle", stats.Idle).
			Int("max_open", stats.MaxOpenConnections).
			Int64("wait_count", stats.WaitCount).
			Msg("Connection pool stats")
	}

	return nil
}
