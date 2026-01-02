package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/aristath/arduino-trader/internal/config"
	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/internal/scheduler"
	"github.com/aristath/arduino-trader/internal/server"
	"github.com/aristath/arduino-trader/pkg/logger"
)

func main() {
	// Initialize logger
	log := logger.New(logger.Config{
		Level:  "info",
		Pretty: true,
	})

	log.Info().Msg("Starting Arduino Trader")

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to load configuration")
	}

	// Initialize databases (Python uses multiple SQLite databases)
	configDB, err := database.New(cfg.DatabasePath) // config.db
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to initialize config database")
	}
	defer configDB.Close()

	// state.db - positions, scores
	stateDB, err := database.New("../data/state.db")
	if err != nil {
		log.Error().Err(err).Msg("Failed to initialize state database")
		os.Exit(1)
	}
	defer stateDB.Close()

	// snapshots.db - portfolio snapshots
	snapshotsDB, err := database.New("../data/snapshots.db")
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to initialize snapshots database")
	}
	defer snapshotsDB.Close()

	// ledger.db - trades (append-only ledger)
	ledgerDB, err := database.New("../data/ledger.db")
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to initialize ledger database")
	}
	defer ledgerDB.Close()

	// dividends.db - dividend records with DRIP tracking
	dividendsDB, err := database.New("../data/dividends.db")
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to initialize dividends database")
	}
	defer dividendsDB.Close()

	// Run migrations
	if err := configDB.Migrate(); err != nil {
		log.Fatal().Err(err).Msg("Failed to run migrations")
	}

	// Initialize scheduler
	sched := scheduler.New(log)
	sched.Start()
	defer sched.Stop()

	// Register background jobs
	if err := registerJobs(sched, configDB, cfg); err != nil {
		log.Fatal().Err(err).Msg("Failed to register jobs")
	}

	// Initialize HTTP server
	srv := server.New(server.Config{
		Port:        cfg.Port,
		Log:         log,
		ConfigDB:    configDB,
		StateDB:     stateDB,
		SnapshotsDB: snapshotsDB,
		LedgerDB:    ledgerDB,
		DividendsDB: dividendsDB,
		Config:      cfg,
		DevMode:     cfg.DevMode,
	})

	// Start server in goroutine
	go func() {
		if err := srv.Start(); err != nil {
			log.Fatal().Err(err).Msg("Failed to start server")
		}
	}()

	log.Info().Int("port", cfg.Port).Msg("Server started successfully")

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info().Msg("Shutting down server...")

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Error().Err(err).Msg("Server forced to shutdown")
	}

	log.Info().Msg("Server stopped")
}

func registerJobs(sched *scheduler.Scheduler, db *database.DB, cfg *config.Config) error {
	// TODO: Register background jobs here
	// Example:
	// sched.AddJob("@hourly", jobs.NewPriceSync(db))
	// sched.AddJob("0 9 * * MON-FRI", jobs.NewDailySync(db))

	return nil
}
