package reliability

import (
	"database/sql"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/rs/zerolog"
)

// DatabaseHealthService monitors database health and performs auto-recovery
// Implements comprehensive health monitoring as specified in architecture plan
type DatabaseHealthService struct {
	db   *database.DB
	name string
	path string
	log  zerolog.Logger
}

// NewDatabaseHealthService creates a new database health service
func NewDatabaseHealthService(db *database.DB, name, path string, log zerolog.Logger) *DatabaseHealthService {
	return &DatabaseHealthService{
		db:   db,
		name: name,
		path: path,
		log:  log.With().Str("service", "health").Str("database", name).Logger(),
	}
}

// CheckAndRecover performs health check and auto-recovery if needed
func (s *DatabaseHealthService) CheckAndRecover() error {
	s.log.Debug().Msg("Starting health check")

	// Step 1: Integrity check
	if err := s.checkIntegrity(); err != nil {
		s.log.Error().Err(err).Msg("Integrity check failed")

		// Step 2: Attempt WAL recovery
		if err := s.attemptWALRecovery(); err != nil {
			s.log.Error().Err(err).Msg("WAL recovery failed")

			// Step 3: Restore from backup
			return s.restoreFromBackup()
		}

		// Verify integrity after WAL recovery
		if err := s.checkIntegrity(); err != nil {
			s.log.Error().Err(err).Msg("Integrity check failed after WAL recovery")
			return s.restoreFromBackup()
		}

		s.log.Info().Msg("Database recovered via WAL recovery")
	}

	// Step 4: Check for anomalous growth
	if s.checkAnomalousGrowth() {
		s.log.Warn().Msg("Anomalous database growth detected - investigate")
	}

	// Step 5: Record health metrics
	if err := s.recordHealthMetrics(true); err != nil {
		s.log.Error().Err(err).Msg("Failed to record health metrics")
	}

	s.log.Debug().Msg("Health check complete")
	return nil
}

// checkIntegrity runs PRAGMA integrity_check
func (s *DatabaseHealthService) checkIntegrity() error {
	var result string
	err := s.db.Conn().QueryRow("PRAGMA integrity_check").Scan(&result)
	if err != nil {
		return fmt.Errorf("integrity check query failed: %w", err)
	}

	if result != "ok" {
		return fmt.Errorf("integrity check failed: %s", result)
	}

	return nil
}

// attemptWALRecovery attempts to recover database using WAL checkpoint
func (s *DatabaseHealthService) attemptWALRecovery() error {
	s.log.Warn().Msg("Attempting WAL recovery")

	// Close existing connection
	if err := s.db.Close(); err != nil {
		return fmt.Errorf("failed to close database: %w", err)
	}

	// Run sqlite3 recovery command
	cmd := exec.Command("sqlite3", s.path, "PRAGMA wal_checkpoint(RESTART)")
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("WAL checkpoint failed: %w", err)
	}

	// Reopen database
	newDB, err := database.New(database.Config{
		Path:    s.path,
		Profile: database.ProfileStandard,
		Name:    s.name,
	})
	if err != nil {
		return fmt.Errorf("failed to reopen database: %w", err)
	}

	s.db = newDB

	s.log.Info().Msg("WAL recovery completed")
	return nil
}

// restoreFromBackup attempts to restore database from most recent backup
func (s *DatabaseHealthService) restoreFromBackup() error {
	s.log.Warn().Msg("Attempting restore from backup")

	// Find most recent backup
	backup := s.findMostRecentBackup()
	if backup == "" {
		return fmt.Errorf("CRITICAL: No backup found for %s", s.name)
	}

	s.log.Info().Str("backup", backup).Msg("Found backup")

	// Close existing connection
	if err := s.db.Close(); err != nil {
		return fmt.Errorf("failed to close database: %w", err)
	}

	// Backup corrupted file for investigation
	corruptedPath := s.path + ".corrupted." + time.Now().Format("20060102_150405")
	if err := os.Rename(s.path, corruptedPath); err != nil {
		s.log.Error().Err(err).Msg("Failed to backup corrupted file")
	} else {
		s.log.Info().Str("path", corruptedPath).Msg("Corrupted file backed up")
	}

	// Copy backup to original location
	if err := CopyFile(backup, s.path); err != nil {
		return fmt.Errorf("failed to restore backup: %w", err)
	}

	// Reopen database
	newDB, err := database.New(database.Config{
		Path:    s.path,
		Profile: database.ProfileStandard,
		Name:    s.name,
	})
	if err != nil {
		return fmt.Errorf("failed to reopen database: %w", err)
	}

	s.db = newDB

	// Verify restored database
	var result string
	err = s.db.Conn().QueryRow("PRAGMA integrity_check").Scan(&result)
	if err != nil || result != "ok" {
		return fmt.Errorf("restored backup is also corrupt!")
	}

	s.log.Info().
		Str("backup", backup).
		Msg("Successfully restored from backup")

	return nil
}

// findMostRecentBackup finds the most recent backup for this database
func (s *DatabaseHealthService) findMostRecentBackup() string {
	dataDir := filepath.Dir(s.path)
	backupDir := filepath.Join(dataDir, "backups")

	var mostRecent string
	var mostRecentTime time.Time

	// Search for backups in subdirectories
	if err := filepath.Walk(backupDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}

		if !info.IsDir() && filepath.Base(path) == filepath.Base(s.path) {
			if info.ModTime().After(mostRecentTime) {
				mostRecent = path
				mostRecentTime = info.ModTime()
			}
		}

		return nil
	}); err != nil {
		s.log.Warn().Err(err).Str("backup_dir", backupDir).Msg("Error walking directory for backup search")
	}

	return mostRecent
}

// checkAnomalousGrowth checks if database has grown anomalously
func (s *DatabaseHealthService) checkAnomalousGrowth() bool {
	// Get current size
	info, err := os.Stat(s.path)
	if err != nil {
		return false
	}
	currentSize := info.Size()

	// Get previous size from health metrics
	var previousSize int64
	err = s.db.Conn().QueryRow(`
		SELECT size_bytes FROM _database_health
		ORDER BY checked_at DESC
		LIMIT 1 OFFSET 1
	`).Scan(&previousSize)

	if err != nil || previousSize == 0 {
		return false
	}

	// Check if growth > 50% in one check interval
	growth := float64(currentSize-previousSize) / float64(previousSize)
	return growth > 0.5
}

// recordHealthMetrics records health check results
func (s *DatabaseHealthService) recordHealthMetrics(passed bool) error {
	// Get database size
	info, err := os.Stat(s.path)
	if err != nil {
		return err
	}
	sizeBytes := info.Size()

	// Get WAL size
	var walSize int64
	walPath := s.path + "-wal"
	if walInfo, err := os.Stat(walPath); err == nil {
		walSize = walInfo.Size()
	}

	// Get page count and freelist count
	var pageCount, freelistCount int
	s.db.Conn().QueryRow("PRAGMA page_count").Scan(&pageCount)
	s.db.Conn().QueryRow("PRAGMA freelist_count").Scan(&freelistCount)

	// Insert health record
	_, err = s.db.Conn().Exec(`
		INSERT INTO _database_health (
			checked_at, integrity_check_passed, size_bytes,
			wal_size_bytes, page_count, freelist_count
		) VALUES (?, ?, ?, ?, ?, ?)
	`, time.Now().Unix(), boolToInt(passed), sizeBytes, walSize, pageCount, freelistCount)

	return err
}

// GetMetrics returns current database metrics
func (s *DatabaseHealthService) GetMetrics() (*DatabaseMetrics, error) {
	metrics := &DatabaseMetrics{
		Name: s.name,
	}

	// Get size
	if info, err := os.Stat(s.path); err == nil {
		metrics.SizeMB = float64(info.Size()) / 1024 / 1024
	}

	// Get WAL size
	walPath := s.path + "-wal"
	if info, err := os.Stat(walPath); err == nil {
		metrics.WALSizeMB = float64(info.Size()) / 1024 / 1024
	}

	// Get last vacuum time
	var lastVacuumTime sql.NullInt64
	s.db.Conn().QueryRow(`
		SELECT checked_at FROM _database_health
		WHERE vacuum_performed = 1
		ORDER BY checked_at DESC
		LIMIT 1
	`).Scan(&lastVacuumTime)

	if lastVacuumTime.Valid {
		metrics.LastVacuum = time.Unix(lastVacuumTime.Int64, 0)
	}

	// Get last integrity check
	var lastCheckTime int64
	var lastCheckPassed int
	err := s.db.Conn().QueryRow(`
		SELECT checked_at, integrity_check_passed FROM _database_health
		ORDER BY checked_at DESC
		LIMIT 1
	`).Scan(&lastCheckTime, &lastCheckPassed)

	if err == nil {
		metrics.LastIntegrityCheck = time.Unix(lastCheckTime, 0)
		metrics.IntegrityCheckPassed = lastCheckPassed == 1
	}

	return metrics, nil
}

// DatabaseMetrics holds database health metrics
type DatabaseMetrics struct {
	Name                 string
	SizeMB               float64
	WALSizeMB            float64
	LastVacuum           time.Time
	LastBackup           time.Time
	LastIntegrityCheck   time.Time
	IntegrityCheckPassed bool
	RowCounts            map[string]int64
	GrowthRate24h        float64
}

// Helper functions

func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

// CopyFile copies a file from src to dst (exported for use by other reliability services)
func CopyFile(src, dst string) error {
	input, err := os.ReadFile(src)
	if err != nil {
		return err
	}

	return os.WriteFile(dst, input, 0644)
}
