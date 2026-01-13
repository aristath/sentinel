package scheduler

import (
	"github.com/aristath/sentinel/internal/database"
	"github.com/rs/zerolog"
)

// CheckWALCheckpointsJob monitors WAL checkpoint status
type CheckWALCheckpointsJob struct {
	JobBase
	log          zerolog.Logger
	universeDB   *database.DB
	configDB     *database.DB
	ledgerDB     *database.DB
	portfolioDB  *database.DB
	historyDB    *database.DB
	cacheDB      *database.DB
	clientDataDB *database.DB
}

// NewCheckWALCheckpointsJob creates a new CheckWALCheckpointsJob
func NewCheckWALCheckpointsJob(
	universeDB *database.DB,
	configDB *database.DB,
	ledgerDB *database.DB,
	portfolioDB *database.DB,
	historyDB *database.DB,
	cacheDB *database.DB,
	clientDataDB *database.DB,
) *CheckWALCheckpointsJob {
	return &CheckWALCheckpointsJob{
		log:          zerolog.Nop(),
		universeDB:   universeDB,
		configDB:     configDB,
		ledgerDB:     ledgerDB,
		portfolioDB:  portfolioDB,
		historyDB:    historyDB,
		cacheDB:      cacheDB,
		clientDataDB: clientDataDB,
	}
}

// SetLogger sets the logger for the job
func (j *CheckWALCheckpointsJob) SetLogger(log zerolog.Logger) {
	j.log = log
}

// Name returns the job name
func (j *CheckWALCheckpointsJob) Name() string {
	return "check_wal_checkpoints"
}

// Run executes the check WAL checkpoints job
func (j *CheckWALCheckpointsJob) Run() error {
	databases := map[string]*database.DB{
		"universe":    j.universeDB,
		"config":      j.configDB,
		"ledger":      j.ledgerDB,
		"portfolio":   j.portfolioDB,
		"history":     j.historyDB,
		"cache":       j.cacheDB,
		"client_data": j.clientDataDB,
	}

	checkedCount := 0
	for name, db := range databases {
		if db == nil {
			continue
		}

		// Check WAL checkpoint status
		// PRAGMA wal_checkpoint returns: busy, log, checkpointed
		var busy, log, checkpointed int
		err := db.Conn().QueryRow("PRAGMA wal_checkpoint(PASSIVE)").Scan(&busy, &log, &checkpointed)
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

		checkedCount++
	}

	j.log.Info().
		Int("checked", checkedCount).
		Msg("WAL checkpoint check completed")

	return nil
}
