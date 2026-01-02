package scheduler

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/internal/locking"
	"github.com/rs/zerolog"
)

// HealthCheckJob performs database integrity checks and auto-recovery
// Runs every 6 hours to ensure database health
type HealthCheckJob struct {
	log         zerolog.Logger
	lockManager *locking.Manager
	dataDir     string
	configDB    *database.DB
	stateDB     *database.DB
	snapshotsDB *database.DB
	ledgerDB    *database.DB
	dividendsDB *database.DB
	historyPath string
}

// HealthCheckConfig holds configuration for health check job
type HealthCheckConfig struct {
	Log         zerolog.Logger
	LockManager *locking.Manager
	DataDir     string
	ConfigDB    *database.DB
	StateDB     *database.DB
	SnapshotsDB *database.DB
	LedgerDB    *database.DB
	DividendsDB *database.DB
	HistoryPath string
}

// NewHealthCheckJob creates a new health check job
func NewHealthCheckJob(cfg HealthCheckConfig) *HealthCheckJob {
	return &HealthCheckJob{
		log:         cfg.Log.With().Str("job", "health_check").Logger(),
		lockManager: cfg.LockManager,
		dataDir:     cfg.DataDir,
		configDB:    cfg.ConfigDB,
		stateDB:     cfg.StateDB,
		snapshotsDB: cfg.SnapshotsDB,
		ledgerDB:    cfg.LedgerDB,
		dividendsDB: cfg.DividendsDB,
		historyPath: cfg.HistoryPath,
	}
}

// Name returns the job name
func (j *HealthCheckJob) Name() string {
	return "health_check"
}

// Run executes the health check
func (j *HealthCheckJob) Run() error {
	// Acquire lock to prevent concurrent execution
	if err := j.lockManager.Acquire("health_check"); err != nil {
		j.log.Warn().Err(err).Msg("Health check already running")
		return nil // Don't fail, just skip this run
	}
	defer j.lockManager.Release("health_check")

	j.log.Info().Msg("Starting database health check")
	startTime := time.Now()

	// Step 1: Check core database integrity
	if err := j.checkCoreDatabases(); err != nil {
		j.log.Error().Err(err).Msg("Core database integrity check failed")
		return err
	}

	// Step 2: Check history databases
	j.checkHistoryDatabases()

	// Step 3: Check WAL checkpoints
	j.checkWALCheckpoints()

	// Step 4: Clear stuck locks (older than 1 hour)
	j.clearStuckLocks()

	duration := time.Since(startTime)
	j.log.Info().
		Dur("duration", duration).
		Msg("Health check completed successfully")

	return nil
}

// checkCoreDatabases verifies integrity of core SQLite databases
func (j *HealthCheckJob) checkCoreDatabases() error {
	databases := map[string]*database.DB{
		"config":    j.configDB,
		"state":     j.stateDB,
		"snapshots": j.snapshotsDB,
		"ledger":    j.ledgerDB,
		"dividends": j.dividendsDB,
	}

	for name, db := range databases {
		if db == nil {
			j.log.Warn().Str("database", name).Msg("Database not initialized, skipping")
			continue
		}

		if err := j.checkDatabaseIntegrity(name, db.Conn()); err != nil {
			// Core database corruption is critical - cannot auto-recover
			return fmt.Errorf("database %s is corrupted: %w", name, err)
		}

		j.log.Debug().Str("database", name).Msg("Database integrity OK")
	}

	return nil
}

// checkHistoryDatabases verifies integrity of per-symbol history databases
func (j *HealthCheckJob) checkHistoryDatabases() {
	if j.historyPath == "" {
		j.log.Debug().Msg("History path not configured, skipping history database checks")
		return
	}

	// List all history databases
	entries, err := os.ReadDir(j.historyPath)
	if err != nil {
		if os.IsNotExist(err) {
			j.log.Debug().Msg("History directory does not exist, skipping")
			return
		}
		j.log.Error().Err(err).Msg("Failed to read history directory")
		return
	}

	corruptedCount := 0
	rebuiltCount := 0

	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".db") {
			continue
		}

		dbPath := filepath.Join(j.historyPath, entry.Name())
		symbol := strings.TrimSuffix(entry.Name(), ".db")

		// Open history database
		db, err := sql.Open("sqlite3", dbPath)
		if err != nil {
			j.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to open history database")
			continue
		}
		defer db.Close()

		// Check integrity
		if err := j.checkDatabaseIntegrity(symbol, db); err != nil {
			corruptedCount++
			j.log.Warn().
				Err(err).
				Str("symbol", symbol).
				Str("path", dbPath).
				Msg("History database corrupted, attempting rebuild")

			// Auto-recover: Delete corrupted history database
			// It will be rebuilt by the next historical sync
			if err := os.Remove(dbPath); err != nil {
				j.log.Error().Err(err).Str("symbol", symbol).Msg("Failed to delete corrupted database")
			} else {
				rebuiltCount++
				j.log.Info().Str("symbol", symbol).Msg("Deleted corrupted history database for rebuild")
			}
		}
	}

	if corruptedCount > 0 {
		j.log.Warn().
			Int("corrupted", corruptedCount).
			Int("rebuilt", rebuiltCount).
			Msg("History database corruption detected and recovered")
	}
}

// checkDatabaseIntegrity runs SQLite's PRAGMA integrity_check
func (j *HealthCheckJob) checkDatabaseIntegrity(name string, db *sql.DB) error {
	var result string
	err := db.QueryRow("PRAGMA integrity_check").Scan(&result)
	if err != nil {
		return fmt.Errorf("integrity check failed: %w", err)
	}

	if result != "ok" {
		return fmt.Errorf("integrity check returned: %s", result)
	}

	return nil
}

// checkWALCheckpoints monitors WAL checkpoint status
func (j *HealthCheckJob) checkWALCheckpoints() {
	databases := map[string]*database.DB{
		"config":    j.configDB,
		"state":     j.stateDB,
		"snapshots": j.snapshotsDB,
		"ledger":    j.ledgerDB,
		"dividends": j.dividendsDB,
	}

	for name, db := range databases {
		if db == nil {
			continue
		}

		// Check WAL checkpoint status
		var mode, busy, log, checkpointed int
		err := db.Conn().QueryRow("PRAGMA wal_checkpoint(PASSIVE)").Scan(&mode, &busy, &log, &checkpointed)
		if err != nil {
			j.log.Warn().
				Err(err).
				Str("database", name).
				Msg("Failed to check WAL checkpoint")
			continue
		}

		// Log if WAL is growing large
		if log > 1000 {
			j.log.Warn().
				Str("database", name).
				Int("wal_frames", log).
				Int("checkpointed", checkpointed).
				Msg("WAL file is large, checkpoint may be needed")
		} else {
			j.log.Debug().
				Str("database", name).
				Int("wal_frames", log).
				Msg("WAL checkpoint status OK")
		}
	}
}

// clearStuckLocks removes locks older than 1 hour
func (j *HealthCheckJob) clearStuckLocks() {
	if j.lockManager == nil {
		return
	}

	clearedLocks, err := j.lockManager.ClearStuckLocks(1 * time.Hour)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to clear stuck locks")
		return
	}

	if len(clearedLocks) > 0 {
		j.log.Warn().
			Strs("locks", clearedLocks).
			Msg("Cleared stuck locks")
	} else {
		j.log.Debug().Msg("No stuck locks found")
	}
}
