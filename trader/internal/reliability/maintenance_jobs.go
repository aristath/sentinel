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

// DailyMaintenanceJob performs daily database maintenance (2 AM)
// Implements comprehensive daily maintenance as specified in architecture plan
type DailyMaintenanceJob struct {
	databases      map[string]*database.DB
	healthServices map[string]*DatabaseHealthService
	backupDir      string
	log            zerolog.Logger
}

// NewDailyMaintenanceJob creates a new daily maintenance job
func NewDailyMaintenanceJob(
	databases map[string]*database.DB,
	healthServices map[string]*DatabaseHealthService,
	backupDir string,
	log zerolog.Logger,
) *DailyMaintenanceJob {
	return &DailyMaintenanceJob{
		databases:      databases,
		healthServices: healthServices,
		backupDir:      backupDir,
		log:            log.With().Str("job", "daily_maintenance").Logger(),
	}
}

// Run executes the daily maintenance job
func (j *DailyMaintenanceJob) Run() error {
	j.log.Info().Msg("Starting daily maintenance")
	startTime := time.Now()

	// Step 1: Integrity check and auto-recovery for all databases
	for name, healthService := range j.healthServices {
		j.log.Debug().Str("database", name).Msg("Running integrity check")

		if err := healthService.CheckAndRecover(); err != nil {
			j.log.Error().
				Str("database", name).
				Err(err).
				Msg("CRITICAL: Failed to recover database")
			return fmt.Errorf("CRITICAL: Failed to recover %s: %w", name, err)
		}
	}

	// Step 2: WAL checkpoint for all databases (prevent bloat)
	for name, db := range j.databases {
		j.log.Debug().Str("database", name).Msg("Running WAL checkpoint")

		_, err := db.Conn().Exec("PRAGMA wal_checkpoint(TRUNCATE)")
		if err != nil {
			j.log.Warn().
				Str("database", name).
				Err(err).
				Msg("WAL checkpoint failed")
			// Don't return error - this is not critical
		}
	}

	// Step 3: Check disk space
	if err := j.checkDiskSpace(); err != nil {
		return err // HALT if critical
	}

	// Step 4: Verify yesterday's backups
	if err := j.verifyBackups(); err != nil {
		j.log.Error().Err(err).Msg("Backup verification failed")
		// Log but don't halt - we have today's backup
	}

	// Step 5: Check database growth rates
	j.analyzeDatabaseGrowth()

	duration := time.Since(startTime)
	j.log.Info().
		Dur("duration_ms", duration).
		Msg("Daily maintenance completed successfully")

	return nil
}

// Name returns the job name for scheduler
func (j *DailyMaintenanceJob) Name() string {
	return "daily_maintenance"
}

// checkDiskSpace verifies sufficient disk space is available
func (j *DailyMaintenanceJob) checkDiskSpace() error {
	stat := syscall.Statfs_t{}
	dataDir := filepath.Dir(filepath.Dir(j.backupDir)) // Go up from backups dir
	if err := syscall.Statfs(dataDir, &stat); err != nil {
		return fmt.Errorf("failed to stat filesystem: %w", err)
	}

	availableBytes := stat.Bavail * uint64(stat.Bsize)
	availableGB := float64(availableBytes) / 1e9

	j.log.Debug().Float64("available_gb", availableGB).Msg("Disk space check")

	// CRITICAL: Less than 500MB
	if availableGB < 0.5 {
		j.log.Error().
			Float64("available_gb", availableGB).
			Msg("CRITICAL: Insufficient disk space - HALTING SYSTEM")
		return fmt.Errorf("CRITICAL: Only %.2f GB free - system halted", availableGB)
	}

	// ERROR: Less than 5GB
	if availableGB < 5.0 {
		j.log.Error().
			Float64("available_gb", availableGB).
			Msg("Low disk space - consider cleanup")
	}

	// WARNING: Less than 10GB
	if availableGB < 10.0 {
		j.log.Warn().
			Float64("available_gb", availableGB).
			Msg("Disk space running low")
	}

	return nil
}

// verifyBackups checks integrity of yesterday's backups
func (j *DailyMaintenanceJob) verifyBackups() error {
	yesterday := time.Now().AddDate(0, 0, -1).Format("2006-01-02")
	dailyBackupDir := filepath.Join(j.backupDir, "daily", yesterday)

	if _, err := os.Stat(dailyBackupDir); os.IsNotExist(err) {
		return fmt.Errorf("yesterday's backup directory not found: %s", dailyBackupDir)
	}

	// Verify each database backup
	dbNames := []string{"universe.db", "config.db", "ledger.db", "portfolio.db", "satellites.db", "agents.db", "history.db"}
	for _, dbName := range dbNames {
		backupPath := filepath.Join(dailyBackupDir, dbName)

		if _, err := os.Stat(backupPath); os.IsNotExist(err) {
			j.log.Error().
				Str("database", dbName).
				Str("path", backupPath).
				Msg("Backup file missing")
			continue
		}

		// Open backup and run integrity check
		backupDB, err := sql.Open("sqlite", backupPath)
		if err != nil {
			j.log.Error().
				Str("database", dbName).
				Err(err).
				Msg("Failed to open backup")
			continue
		}
		defer backupDB.Close()

		var result string
		err = backupDB.QueryRow("PRAGMA integrity_check").Scan(&result)
		if err != nil || result != "ok" {
			j.log.Error().
				Str("database", dbName).
				Str("result", result).
				Msg("Backup integrity check failed")
		} else {
			j.log.Debug().
				Str("database", dbName).
				Msg("Backup verified")
		}
	}

	return nil
}

// analyzeDatabaseGrowth analyzes database growth trends
func (j *DailyMaintenanceJob) analyzeDatabaseGrowth() {
	for name, healthService := range j.healthServices {
		metrics, err := healthService.GetMetrics()
		if err != nil {
			j.log.Error().
				Str("database", name).
				Err(err).
				Msg("Failed to get metrics")
			continue
		}

		j.log.Info().
			Str("database", name).
			Float64("size_mb", metrics.SizeMB).
			Float64("wal_size_mb", metrics.WALSizeMB).
			Float64("growth_rate_24h", metrics.GrowthRate24h).
			Msg("Database metrics")

		// Alert on unusual growth
		if metrics.GrowthRate24h > 50.0 {
			j.log.Error().
				Str("database", name).
				Float64("growth_rate_24h", metrics.GrowthRate24h).
				Msg("ERROR: Anomalous database growth > 50% in 24h")
		} else if metrics.GrowthRate24h > 20.0 {
			j.log.Warn().
				Str("database", name).
				Float64("growth_rate_24h", metrics.GrowthRate24h).
				Msg("WARNING: High database growth > 20% in 24h")
		}
	}
}

// WeeklyMaintenanceJob performs weekly database maintenance (Sunday 3 AM)
type WeeklyMaintenanceJob struct {
	databases map[string]*database.DB
	historyDB *database.DB
	log       zerolog.Logger
}

// NewWeeklyMaintenanceJob creates a new weekly maintenance job
func NewWeeklyMaintenanceJob(
	databases map[string]*database.DB,
	historyDB *database.DB,
	log zerolog.Logger,
) *WeeklyMaintenanceJob {
	return &WeeklyMaintenanceJob{
		databases: databases,
		historyDB: historyDB,
		log:       log.With().Str("job", "weekly_maintenance").Logger(),
	}
}

// Run executes the weekly maintenance job
func (j *WeeklyMaintenanceJob) Run() error {
	j.log.Info().Msg("Starting weekly maintenance")
	startTime := time.Now()

	// Step 1: VACUUM ephemeral databases (cache, history, portfolio)
	ephemeralDBs := []string{"cache", "history", "portfolio"}
	for _, dbName := range ephemeralDBs {
		if db, ok := j.databases[dbName]; ok {
			j.log.Info().Str("database", dbName).Msg("Running VACUUM")

			if err := j.vacuumDatabase(db, dbName); err != nil {
				j.log.Error().
					Str("database", dbName).
					Err(err).
					Msg("VACUUM failed")
				// Continue with other databases
			}
		}
	}

	// Step 2: Archive old cleanup logs (>1 year)
	if err := j.archiveOldCleanupLogs(); err != nil {
		j.log.Error().Err(err).Msg("Failed to archive old cleanup logs")
		// Continue - not critical
	}

	duration := time.Since(startTime)
	j.log.Info().
		Dur("duration_ms", duration).
		Msg("Weekly maintenance completed successfully")

	return nil
}

// Name returns the job name for scheduler
func (j *WeeklyMaintenanceJob) Name() string {
	return "weekly_maintenance"
}

// vacuumDatabase performs VACUUM on a database
func (j *WeeklyMaintenanceJob) vacuumDatabase(db *database.DB, name string) error {
	j.log.Debug().Str("database", name).Msg("Starting VACUUM")

	// Get size before VACUUM
	var pageCount, pageSize int
	db.Conn().QueryRow("PRAGMA page_count").Scan(&pageCount)
	db.Conn().QueryRow("PRAGMA page_size").Scan(&pageSize)
	sizeBefore := float64(pageCount*pageSize) / 1024 / 1024

	// Run VACUUM
	_, err := db.Conn().Exec("VACUUM")
	if err != nil {
		return fmt.Errorf("VACUUM failed: %w", err)
	}

	// Get size after VACUUM
	db.Conn().QueryRow("PRAGMA page_count").Scan(&pageCount)
	sizeAfter := float64(pageCount*pageSize) / 1024 / 1024
	spaceReclaimed := sizeBefore - sizeAfter

	j.log.Info().
		Str("database", name).
		Float64("size_before_mb", sizeBefore).
		Float64("size_after_mb", sizeAfter).
		Float64("space_reclaimed_mb", spaceReclaimed).
		Msg("VACUUM completed")

	return nil
}

// archiveOldCleanupLogs archives cleanup logs older than 1 year
func (j *WeeklyMaintenanceJob) archiveOldCleanupLogs() error {
	oneYearAgo := time.Now().AddDate(-1, 0, 0).Unix()

	// Count rows to be archived
	var count int
	err := j.historyDB.Conn().QueryRow(`
		SELECT COUNT(*) FROM cleanup_log
		WHERE deleted_at < ?
	`, oneYearAgo).Scan(&count)

	if err != nil {
		return fmt.Errorf("failed to count old logs: %w", err)
	}

	if count == 0 {
		j.log.Debug().Msg("No old cleanup logs to archive")
		return nil
	}

	// Delete old logs
	result, err := j.historyDB.Conn().Exec(`
		DELETE FROM cleanup_log
		WHERE deleted_at < ?
	`, oneYearAgo)

	if err != nil {
		return fmt.Errorf("failed to delete old logs: %w", err)
	}

	rowsDeleted, _ := result.RowsAffected()
	j.log.Info().
		Int64("rows_deleted", rowsDeleted).
		Msg("Archived old cleanup logs")

	return nil
}

// MonthlyMaintenanceJob performs monthly database maintenance (1st day, 4 AM)
type MonthlyMaintenanceJob struct {
	databases      map[string]*database.DB
	healthServices map[string]*DatabaseHealthService
	agentsDB       *database.DB
	backupDir      string
	log            zerolog.Logger
}

// NewMonthlyMaintenanceJob creates a new monthly maintenance job
func NewMonthlyMaintenanceJob(
	databases map[string]*database.DB,
	healthServices map[string]*DatabaseHealthService,
	agentsDB *database.DB,
	backupDir string,
	log zerolog.Logger,
) *MonthlyMaintenanceJob {
	return &MonthlyMaintenanceJob{
		databases:      databases,
		healthServices: healthServices,
		agentsDB:       agentsDB,
		backupDir:      backupDir,
		log:            log.With().Str("job", "monthly_maintenance").Logger(),
	}
}

// Run executes the monthly maintenance job
func (j *MonthlyMaintenanceJob) Run() error {
	j.log.Info().Msg("Starting monthly maintenance")
	startTime := time.Now()

	// Step 1: VACUUM all databases (except ledger - it's append-only)
	for name, db := range j.databases {
		if name == "ledger" {
			j.log.Debug().
				Str("database", name).
				Msg("Skipping VACUUM for append-only ledger")
			continue
		}

		j.log.Info().Str("database", name).Msg("Running VACUUM")

		if err := j.vacuumDatabase(db, name); err != nil {
			j.log.Error().
				Str("database", name).
				Err(err).
				Msg("VACUUM failed")
			// Continue with other databases
		}
	}

	// Step 2: Full backup verification (restore to temp, check integrity)
	if err := j.fullBackupVerification(); err != nil {
		j.log.Error().Err(err).Msg("CRITICAL: Backup verification failed")
		return fmt.Errorf("CRITICAL: Backup verification failed: %w", err)
	}

	// Step 3: Archive old sequences from agents.db (>90 days)
	if err := j.archiveOldSequences(); err != nil {
		j.log.Error().Err(err).Msg("Failed to archive old sequences")
		// Continue - not critical
	}

	// Step 4: Database growth analysis
	j.analyzeGrowthTrends()

	duration := time.Since(startTime)
	j.log.Info().
		Dur("duration_ms", duration).
		Msg("Monthly maintenance completed successfully")

	return nil
}

// Name returns the job name for scheduler
func (j *MonthlyMaintenanceJob) Name() string {
	return "monthly_maintenance"
}

// vacuumDatabase performs VACUUM on a database
func (j *MonthlyMaintenanceJob) vacuumDatabase(db *database.DB, name string) error {
	j.log.Debug().Str("database", name).Msg("Starting VACUUM")

	// Get size before VACUUM
	var pageCount, pageSize int
	db.Conn().QueryRow("PRAGMA page_count").Scan(&pageCount)
	db.Conn().QueryRow("PRAGMA page_size").Scan(&pageSize)
	sizeBefore := float64(pageCount*pageSize) / 1024 / 1024

	// Run VACUUM
	_, err := db.Conn().Exec("VACUUM")
	if err != nil {
		return fmt.Errorf("VACUUM failed: %w", err)
	}

	// Get size after VACUUM
	db.Conn().QueryRow("PRAGMA page_count").Scan(&pageCount)
	sizeAfter := float64(pageCount*pageSize) / 1024 / 1024
	spaceReclaimed := sizeBefore - sizeAfter

	j.log.Info().
		Str("database", name).
		Float64("size_before_mb", sizeBefore).
		Float64("size_after_mb", sizeAfter).
		Float64("space_reclaimed_mb", spaceReclaimed).
		Msg("VACUUM completed")

	return nil
}

// fullBackupVerification restores latest backup to temp directory and verifies integrity
func (j *MonthlyMaintenanceJob) fullBackupVerification() error {
	j.log.Info().Msg("Starting full backup verification")

	// Create temp directory for verification
	tempDir, err := os.MkdirTemp("", "backup_verification_*")
	if err != nil {
		return fmt.Errorf("failed to create temp directory: %w", err)
	}
	defer os.RemoveAll(tempDir)

	// Find most recent daily backup
	dailyBackupDir := filepath.Join(j.backupDir, "daily")
	entries, err := os.ReadDir(dailyBackupDir)
	if err != nil {
		return fmt.Errorf("failed to read daily backup directory: %w", err)
	}

	if len(entries) == 0 {
		return fmt.Errorf("no daily backups found")
	}

	// Get most recent backup (entries are sorted by name, which is YYYY-MM-DD)
	var mostRecentBackup string
	for i := len(entries) - 1; i >= 0; i-- {
		if entries[i].IsDir() {
			mostRecentBackup = entries[i].Name()
			break
		}
	}

	if mostRecentBackup == "" {
		return fmt.Errorf("no valid backup directory found")
	}

	backupPath := filepath.Join(dailyBackupDir, mostRecentBackup)
	j.log.Info().Str("backup_date", mostRecentBackup).Msg("Verifying backup")

	// Verify each database backup
	dbNames := []string{"universe.db", "config.db", "ledger.db", "portfolio.db", "satellites.db", "agents.db", "history.db"}
	for _, dbName := range dbNames {
		srcPath := filepath.Join(backupPath, dbName)
		dstPath := filepath.Join(tempDir, dbName)

		// Copy backup to temp
		if err := CopyFile(srcPath, dstPath); err != nil {
			return fmt.Errorf("failed to copy %s: %w", dbName, err)
		}

		// Open and verify integrity
		backupDB, err := sql.Open("sqlite", dstPath)
		if err != nil {
			return fmt.Errorf("failed to open %s: %w", dbName, err)
		}

		var result string
		err = backupDB.QueryRow("PRAGMA integrity_check").Scan(&result)
		backupDB.Close()

		if err != nil || result != "ok" {
			return fmt.Errorf("integrity check failed for %s: %s", dbName, result)
		}

		j.log.Debug().Str("database", dbName).Msg("Backup verified")
	}

	j.log.Info().
		Str("backup_date", mostRecentBackup).
		Msg("Full backup verification completed successfully")

	return nil
}

// archiveOldSequences deletes sequences older than 90 days from agents.db
func (j *MonthlyMaintenanceJob) archiveOldSequences() error {
	ninetyDaysAgo := time.Now().AddDate(0, 0, -90).Unix()

	// Count rows to be archived
	var count int
	err := j.agentsDB.Conn().QueryRow(`
		SELECT COUNT(*) FROM sequences
		WHERE created_at < ?
	`, ninetyDaysAgo).Scan(&count)

	if err != nil {
		return fmt.Errorf("failed to count old sequences: %w", err)
	}

	if count == 0 {
		j.log.Debug().Msg("No old sequences to archive")
		return nil
	}

	// Delete old sequences
	result, err := j.agentsDB.Conn().Exec(`
		DELETE FROM sequences
		WHERE created_at < ?
	`, ninetyDaysAgo)

	if err != nil {
		return fmt.Errorf("failed to delete old sequences: %w", err)
	}

	rowsDeleted, _ := result.RowsAffected()
	j.log.Info().
		Int64("rows_deleted", rowsDeleted).
		Msg("Archived old sequences")

	// Also delete associated evaluations
	result, err = j.agentsDB.Conn().Exec(`
		DELETE FROM evaluations
		WHERE created_at < ?
	`, ninetyDaysAgo)

	if err != nil {
		return fmt.Errorf("failed to delete old evaluations: %w", err)
	}

	rowsDeleted, _ = result.RowsAffected()
	j.log.Info().
		Int64("rows_deleted", rowsDeleted).
		Msg("Archived old evaluations")

	return nil
}

// analyzeGrowthTrends analyzes database growth trends over time
func (j *MonthlyMaintenanceJob) analyzeGrowthTrends() {
	j.log.Info().Msg("Analyzing database growth trends")

	for name, healthService := range j.healthServices {
		metrics, err := healthService.GetMetrics()
		if err != nil {
			j.log.Error().
				Str("database", name).
				Err(err).
				Msg("Failed to get metrics")
			continue
		}

		// Get historical size from 30 days ago
		thirtyDaysAgo := time.Now().AddDate(0, 0, -30).Unix()
		var oldSize sql.NullInt64
		healthService.db.Conn().QueryRow(`
			SELECT size_bytes FROM _database_health
			WHERE checked_at >= ?
			ORDER BY checked_at ASC
			LIMIT 1
		`, thirtyDaysAgo).Scan(&oldSize)

		var growthRate30d float64
		if oldSize.Valid && oldSize.Int64 > 0 {
			currentSize := metrics.SizeMB * 1024 * 1024
			oldSizeMB := float64(oldSize.Int64) / 1024 / 1024
			growthRate30d = ((currentSize - float64(oldSize.Int64)) / float64(oldSize.Int64)) * 100
			j.log.Info().
				Str("database", name).
				Float64("size_mb", metrics.SizeMB).
				Float64("size_30d_ago_mb", oldSizeMB).
				Float64("growth_rate_30d_pct", growthRate30d).
				Msg("Monthly growth analysis")
		} else {
			j.log.Info().
				Str("database", name).
				Float64("size_mb", metrics.SizeMB).
				Msg("Monthly growth analysis (no historical data)")
		}
	}
}
