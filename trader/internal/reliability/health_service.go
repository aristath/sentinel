package reliability

import (
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

	// Run integrity check now
	var result string
	err := s.db.Conn().QueryRow("PRAGMA integrity_check").Scan(&result)
	if err == nil {
		metrics.IntegrityCheckPassed = result == "ok"
		metrics.LastIntegrityCheck = time.Now()
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
