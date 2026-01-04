package reliability

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/rs/zerolog"
)

// BackupService manages tiered database backups (hourly/daily/weekly/monthly)
// Implements comprehensive backup strategy as specified in architecture plan
type BackupService struct {
	databases map[string]*database.DB
	dataDir   string
	backupDir string
	log       zerolog.Logger
}

// NewBackupService creates a new backup service
func NewBackupService(
	databases map[string]*database.DB,
	dataDir string,
	backupDir string,
	log zerolog.Logger,
) *BackupService {
	return &BackupService{
		databases: databases,
		dataDir:   dataDir,
		backupDir: backupDir,
		log:       log.With().Str("service", "backup").Logger(),
	}
}

// HourlyBackup performs hourly backup (ledger.db only)
// Keeps last 24 hours, rotates older backups
func (s *BackupService) HourlyBackup() error {
	s.log.Info().Msg("Starting hourly backup")
	startTime := time.Now()

	// Create hourly backup directory
	hourlyDir := filepath.Join(s.backupDir, "hourly")
	if err := os.MkdirAll(hourlyDir, 0755); err != nil {
		return fmt.Errorf("failed to create hourly backup directory: %w", err)
	}

	// Backup only ledger.db
	timestamp := time.Now().Format("2006-01-02_15")
	backupName := fmt.Sprintf("ledger_%s.db", timestamp)
	backupPath := filepath.Join(hourlyDir, backupName)

	if err := s.backupDatabase("ledger", backupPath); err != nil {
		return fmt.Errorf("failed to backup ledger.db: %w", err)
	}

	// Verify backup
	if err := s.verifyBackup(backupPath); err != nil {
		// Delete corrupted backup
		os.Remove(backupPath)
		return fmt.Errorf("backup verification failed: %w", err)
	}

	// Rotate old backups (keep last 24 hours)
	if err := s.rotateHourlyBackups(hourlyDir); err != nil {
		s.log.Error().Err(err).Msg("Failed to rotate hourly backups")
		// Don't fail - backup succeeded
	}

	duration := time.Since(startTime)
	s.log.Info().
		Dur("duration_ms", duration).
		Str("backup_path", backupPath).
		Msg("Hourly backup completed successfully")

	return nil
}

// DailyBackup performs daily backup (all databases except cache)
// Keeps last 30 days, rotates older backups
func (s *BackupService) DailyBackup() error {
	s.log.Info().Msg("Starting daily backup")
	startTime := time.Now()

	// Create daily backup directory
	date := time.Now().Format("2006-01-02")
	dailyDir := filepath.Join(s.backupDir, "daily", date)
	if err := os.MkdirAll(dailyDir, 0755); err != nil {
		return fmt.Errorf("failed to create daily backup directory: %w", err)
	}

	// Backup all databases except cache
	dbNames := []string{"universe", "config", "ledger", "portfolio", "satellites", "agents", "history"}
	for _, dbName := range dbNames {
		backupPath := filepath.Join(dailyDir, dbName+".db")

		if err := s.backupDatabase(dbName, backupPath); err != nil {
			s.log.Error().
				Str("database", dbName).
				Err(err).
				Msg("Failed to backup database")
			// Continue with other databases
			continue
		}

		// Verify backup
		if err := s.verifyBackup(backupPath); err != nil {
			s.log.Error().
				Str("database", dbName).
				Err(err).
				Msg("Backup verification failed")
			os.Remove(backupPath)
			// Continue with other databases
		}
	}

	// Rotate old backups (keep last 30 days)
	if err := s.rotateDailyBackups(); err != nil {
		s.log.Error().Err(err).Msg("Failed to rotate daily backups")
		// Don't fail - backup succeeded
	}

	duration := time.Since(startTime)
	s.log.Info().
		Dur("duration_ms", duration).
		Str("backup_dir", dailyDir).
		Msg("Daily backup completed successfully")

	return nil
}

// WeeklyBackup performs weekly backup (all databases including cache)
// Keeps last 12 weeks, rotates older backups
func (s *BackupService) WeeklyBackup() error {
	s.log.Info().Msg("Starting weekly backup")
	startTime := time.Now()

	// Create weekly backup directory (YYYY-WW format)
	year, week := time.Now().ISOWeek()
	weekDir := filepath.Join(s.backupDir, "weekly", fmt.Sprintf("%04d-W%02d", year, week))
	if err := os.MkdirAll(weekDir, 0755); err != nil {
		return fmt.Errorf("failed to create weekly backup directory: %w", err)
	}

	// Backup all databases (including cache)
	dbNames := []string{"universe", "config", "ledger", "portfolio", "satellites", "agents", "history", "cache"}
	for _, dbName := range dbNames {
		backupPath := filepath.Join(weekDir, dbName+".db")

		if err := s.backupDatabase(dbName, backupPath); err != nil {
			s.log.Error().
				Str("database", dbName).
				Err(err).
				Msg("Failed to backup database")
			// Continue with other databases
			continue
		}

		// Verify backup
		if err := s.verifyBackup(backupPath); err != nil {
			s.log.Error().
				Str("database", dbName).
				Err(err).
				Msg("Backup verification failed")
			os.Remove(backupPath)
			// Continue with other databases
		}
	}

	// Rotate old backups (keep last 12 weeks)
	if err := s.rotateWeeklyBackups(); err != nil {
		s.log.Error().Err(err).Msg("Failed to rotate weekly backups")
		// Don't fail - backup succeeded
	}

	duration := time.Since(startTime)
	s.log.Info().
		Dur("duration_ms", duration).
		Str("backup_dir", weekDir).
		Msg("Weekly backup completed successfully")

	return nil
}

// MonthlyBackup performs monthly backup (all databases including cache)
// Keeps last 120 months (10 years), rotates older backups
func (s *BackupService) MonthlyBackup() error {
	s.log.Info().Msg("Starting monthly backup")
	startTime := time.Now()

	// Create monthly backup directory (YYYY-MM format)
	month := time.Now().Format("2006-01")
	monthDir := filepath.Join(s.backupDir, "monthly", month)
	if err := os.MkdirAll(monthDir, 0755); err != nil {
		return fmt.Errorf("failed to create monthly backup directory: %w", err)
	}

	// Backup all databases (including cache)
	dbNames := []string{"universe", "config", "ledger", "portfolio", "satellites", "agents", "history", "cache"}
	for _, dbName := range dbNames {
		backupPath := filepath.Join(monthDir, dbName+".db")

		if err := s.backupDatabase(dbName, backupPath); err != nil {
			s.log.Error().
				Str("database", dbName).
				Err(err).
				Msg("Failed to backup database")
			// Continue with other databases
			continue
		}

		// Verify backup
		if err := s.verifyBackup(backupPath); err != nil {
			s.log.Error().
				Str("database", dbName).
				Err(err).
				Msg("Backup verification failed")
			os.Remove(backupPath)
			// Continue with other databases
		}
	}

	// Rotate old backups (keep last 120 months = 10 years)
	if err := s.rotateMonthlyBackups(); err != nil {
		s.log.Error().Err(err).Msg("Failed to rotate monthly backups")
		// Don't fail - backup succeeded
	}

	duration := time.Since(startTime)
	s.log.Info().
		Dur("duration_ms", duration).
		Str("backup_dir", monthDir).
		Msg("Monthly backup completed successfully")

	return nil
}

// backupDatabase performs backup of a single database using SQLite's VACUUM INTO
func (s *BackupService) backupDatabase(dbName, backupPath string) error {
	db, ok := s.databases[dbName]
	if !ok {
		return fmt.Errorf("database %s not found", dbName)
	}

	s.log.Debug().
		Str("database", dbName).
		Str("backup_path", backupPath).
		Msg("Backing up database")

	// Use VACUUM INTO for atomic backup
	// This creates a fresh copy without WAL files and optimizes the database
	_, err := db.Conn().Exec(fmt.Sprintf("VACUUM INTO '%s'", backupPath))
	if err != nil {
		return fmt.Errorf("VACUUM INTO failed: %w", err)
	}

	// Get backup file size
	info, err := os.Stat(backupPath)
	if err != nil {
		return fmt.Errorf("failed to stat backup: %w", err)
	}

	sizeMB := float64(info.Size()) / 1024 / 1024
	s.log.Debug().
		Str("database", dbName).
		Float64("size_mb", sizeMB).
		Msg("Backup created")

	return nil
}

// verifyBackup verifies backup integrity
func (s *BackupService) verifyBackup(backupPath string) error {
	// Open backup database
	backupDB, err := sql.Open("sqlite", backupPath)
	if err != nil {
		return fmt.Errorf("failed to open backup: %w", err)
	}
	defer backupDB.Close()

	// Run integrity check
	var result string
	err = backupDB.QueryRow("PRAGMA integrity_check").Scan(&result)
	if err != nil {
		return fmt.Errorf("integrity check query failed: %w", err)
	}

	if result != "ok" {
		return fmt.Errorf("integrity check failed: %s", result)
	}

	return nil
}

// rotateHourlyBackups deletes backups older than 24 hours
func (s *BackupService) rotateHourlyBackups(hourlyDir string) error {
	cutoff := time.Now().Add(-24 * time.Hour)

	entries, err := os.ReadDir(hourlyDir)
	if err != nil {
		return fmt.Errorf("failed to read hourly backup directory: %w", err)
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		info, err := entry.Info()
		if err != nil {
			continue
		}

		if info.ModTime().Before(cutoff) {
			path := filepath.Join(hourlyDir, entry.Name())
			if err := os.Remove(path); err != nil {
				s.log.Warn().
					Str("path", path).
					Err(err).
					Msg("Failed to delete old hourly backup")
			} else {
				s.log.Debug().
					Str("path", path).
					Msg("Deleted old hourly backup")
			}
		}
	}

	return nil
}

// rotateDailyBackups deletes backups older than 30 days
func (s *BackupService) rotateDailyBackups() error {
	dailyDir := filepath.Join(s.backupDir, "daily")
	cutoff := time.Now().AddDate(0, 0, -30)

	entries, err := os.ReadDir(dailyDir)
	if err != nil {
		return fmt.Errorf("failed to read daily backup directory: %w", err)
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}

		// Parse date from directory name (YYYY-MM-DD)
		dirDate, err := time.Parse("2006-01-02", entry.Name())
		if err != nil {
			s.log.Warn().
				Str("dir", entry.Name()).
				Msg("Failed to parse date from directory name")
			continue
		}

		if dirDate.Before(cutoff) {
			path := filepath.Join(dailyDir, entry.Name())
			if err := os.RemoveAll(path); err != nil {
				s.log.Warn().
					Str("path", path).
					Err(err).
					Msg("Failed to delete old daily backup")
			} else {
				s.log.Debug().
					Str("path", path).
					Msg("Deleted old daily backup")
			}
		}
	}

	return nil
}

// rotateWeeklyBackups deletes backups older than 12 weeks
func (s *BackupService) rotateWeeklyBackups() error {
	weeklyDir := filepath.Join(s.backupDir, "weekly")
	cutoff := time.Now().AddDate(0, 0, -12*7) // 12 weeks

	entries, err := os.ReadDir(weeklyDir)
	if err != nil {
		return fmt.Errorf("failed to read weekly backup directory: %w", err)
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}

		info, err := entry.Info()
		if err != nil {
			continue
		}

		if info.ModTime().Before(cutoff) {
			path := filepath.Join(weeklyDir, entry.Name())
			if err := os.RemoveAll(path); err != nil {
				s.log.Warn().
					Str("path", path).
					Err(err).
					Msg("Failed to delete old weekly backup")
			} else {
				s.log.Debug().
					Str("path", path).
					Msg("Deleted old weekly backup")
			}
		}
	}

	return nil
}

// rotateMonthlyBackups deletes backups older than 120 months (10 years)
func (s *BackupService) rotateMonthlyBackups() error {
	monthlyDir := filepath.Join(s.backupDir, "monthly")
	cutoff := time.Now().AddDate(-10, 0, 0) // 10 years

	entries, err := os.ReadDir(monthlyDir)
	if err != nil {
		return fmt.Errorf("failed to read monthly backup directory: %w", err)
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}

		// Parse date from directory name (YYYY-MM)
		dirDate, err := time.Parse("2006-01", entry.Name())
		if err != nil {
			s.log.Warn().
				Str("dir", entry.Name()).
				Msg("Failed to parse date from directory name")
			continue
		}

		if dirDate.Before(cutoff) {
			path := filepath.Join(monthlyDir, entry.Name())
			if err := os.RemoveAll(path); err != nil {
				s.log.Warn().
					Str("path", path).
					Err(err).
					Msg("Failed to delete old monthly backup")
			} else {
				s.log.Debug().
					Str("path", path).
					Msg("Deleted old monthly backup")
			}
		}
	}

	return nil
}

// RestoreFromBackup restores a database from the most recent backup
// This is used by the auto-recovery system
func (s *BackupService) RestoreFromBackup(dbName string) (string, error) {
	s.log.Warn().
		Str("database", dbName).
		Msg("Searching for backup to restore")

	// Search in order: hourly (if ledger), daily, weekly, monthly
	var backupPath string

	if dbName == "ledger" {
		// Check hourly backups first for ledger
		backupPath = s.findMostRecentBackup(filepath.Join(s.backupDir, "hourly"), dbName+".db", "ledger_*.db")
		if backupPath != "" {
			s.log.Info().
				Str("backup", backupPath).
				Msg("Found hourly backup")
			return backupPath, nil
		}
	}

	// Check daily backups
	backupPath = s.findMostRecentBackup(filepath.Join(s.backupDir, "daily"), dbName+".db", "")
	if backupPath != "" {
		s.log.Info().
			Str("backup", backupPath).
			Msg("Found daily backup")
		return backupPath, nil
	}

	// Check weekly backups
	backupPath = s.findMostRecentBackup(filepath.Join(s.backupDir, "weekly"), dbName+".db", "")
	if backupPath != "" {
		s.log.Info().
			Str("backup", backupPath).
			Msg("Found weekly backup")
		return backupPath, nil
	}

	// Check monthly backups
	backupPath = s.findMostRecentBackup(filepath.Join(s.backupDir, "monthly"), dbName+".db", "")
	if backupPath != "" {
		s.log.Info().
			Str("backup", backupPath).
			Msg("Found monthly backup")
		return backupPath, nil
	}

	return "", fmt.Errorf("no backup found for %s", dbName)
}

// findMostRecentBackup searches for the most recent backup in a directory tree
func (s *BackupService) findMostRecentBackup(baseDir, filename, pattern string) string {
	var mostRecent string
	var mostRecentTime time.Time

	if err := filepath.Walk(baseDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}

		if info.IsDir() {
			return nil
		}

		// Match either exact filename or pattern
		match := false
		if pattern != "" {
			matched, _ := filepath.Match(pattern, filepath.Base(path))
			match = matched
		} else {
			match = filepath.Base(path) == filename
		}

		if match && info.ModTime().After(mostRecentTime) {
			mostRecent = path
			mostRecentTime = info.ModTime()
		}

		return nil
	}); err != nil {
		s.log.Warn().Err(err).Str("base_dir", baseDir).Msg("Error walking directory for backup search")
	}

	return mostRecent
}

// HourlyBackupJob wraps BackupService.HourlyBackup for scheduler
type HourlyBackupJob struct {
	service *BackupService
}

// NewHourlyBackupJob creates a new hourly backup job
func NewHourlyBackupJob(service *BackupService) *HourlyBackupJob {
	return &HourlyBackupJob{service: service}
}

// Run executes the hourly backup
func (j *HourlyBackupJob) Run() error {
	return j.service.HourlyBackup()
}

// Name returns the job name for scheduler
func (j *HourlyBackupJob) Name() string {
	return "hourly_backup"
}

// DailyBackupJob wraps BackupService.DailyBackup for scheduler
type DailyBackupJob struct {
	service *BackupService
}

// NewDailyBackupJob creates a new daily backup job
func NewDailyBackupJob(service *BackupService) *DailyBackupJob {
	return &DailyBackupJob{service: service}
}

// Run executes the daily backup
func (j *DailyBackupJob) Run() error {
	return j.service.DailyBackup()
}

// Name returns the job name for scheduler
func (j *DailyBackupJob) Name() string {
	return "daily_backup"
}

// WeeklyBackupJob wraps BackupService.WeeklyBackup for scheduler
type WeeklyBackupJob struct {
	service *BackupService
}

// NewWeeklyBackupJob creates a new weekly backup job
func NewWeeklyBackupJob(service *BackupService) *WeeklyBackupJob {
	return &WeeklyBackupJob{service: service}
}

// Run executes the weekly backup
func (j *WeeklyBackupJob) Run() error {
	return j.service.WeeklyBackup()
}

// Name returns the job name for scheduler
func (j *WeeklyBackupJob) Name() string {
	return "weekly_backup"
}

// MonthlyBackupJob wraps BackupService.MonthlyBackup for scheduler
type MonthlyBackupJob struct {
	service *BackupService
}

// NewMonthlyBackupJob creates a new monthly backup job
func NewMonthlyBackupJob(service *BackupService) *MonthlyBackupJob {
	return &MonthlyBackupJob{service: service}
}

// Run executes the monthly backup
func (j *MonthlyBackupJob) Run() error {
	return j.service.MonthlyBackup()
}

// Name returns the job name for scheduler
func (j *MonthlyBackupJob) Name() string {
	return "monthly_backup"
}
