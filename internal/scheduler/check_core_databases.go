package scheduler

import (
	"database/sql"
	"fmt"

	"github.com/aristath/sentinel/internal/database"
	"github.com/rs/zerolog"
)

// CheckCoreDatabasesJob verifies integrity of core SQLite databases
type CheckCoreDatabasesJob struct {
	JobBase
	log         zerolog.Logger
	universeDB  *database.DB
	configDB    *database.DB
	ledgerDB    *database.DB
	portfolioDB *database.DB
}

// NewCheckCoreDatabasesJob creates a new CheckCoreDatabasesJob
func NewCheckCoreDatabasesJob(
	universeDB *database.DB,
	configDB *database.DB,
	ledgerDB *database.DB,
	portfolioDB *database.DB,
) *CheckCoreDatabasesJob {
	return &CheckCoreDatabasesJob{
		log:         zerolog.Nop(),
		universeDB:  universeDB,
		configDB:    configDB,
		ledgerDB:    ledgerDB,
		portfolioDB: portfolioDB,
	}
}

// SetLogger sets the logger for the job
func (j *CheckCoreDatabasesJob) SetLogger(log zerolog.Logger) {
	j.log = log
}

// Name returns the job name
func (j *CheckCoreDatabasesJob) Name() string {
	return "check_core_databases"
}

// Run executes the check core databases job
func (j *CheckCoreDatabasesJob) Run() error {
	databases := map[string]*database.DB{
		"universe":  j.universeDB,
		"config":    j.configDB,
		"ledger":    j.ledgerDB,
		"portfolio": j.portfolioDB,
	}

	for name, db := range databases {
		if db == nil {
			j.log.Warn().Str("database", name).Msg("Database not initialized, skipping")
			continue
		}

		if err := j.checkDatabaseIntegrity(name, db.Conn()); err != nil {
			// Core database corruption is critical - cannot auto-recover
			j.log.Error().
				Err(err).
				Str("database", name).
				Msg("Core database integrity check failed")
			return fmt.Errorf("database %s is corrupted: %w", name, err)
		}

		j.log.Debug().Str("database", name).Msg("Database integrity OK")
	}

	j.log.Info().Msg("All core databases integrity check passed")
	return nil
}

// checkDatabaseIntegrity runs SQLite's PRAGMA integrity_check
func (j *CheckCoreDatabasesJob) checkDatabaseIntegrity(name string, db *sql.DB) error {
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
