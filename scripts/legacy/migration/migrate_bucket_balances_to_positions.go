//go:build ignore
// +build ignore

package main

import (
	"database/sql"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/internal/modules/cash_flows"
	"github.com/aristath/arduino-trader/internal/modules/cash_utils"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/satellites"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/aristath/arduino-trader/pkg/logger"
	"github.com/rs/zerolog"
)

// BucketBalance represents a row from the bucket_balances table
type BucketBalance struct {
	BucketID  string
	Currency  string
	Balance   float64
	UpdatedAt string
}

func main() {
	fmt.Fprintf(os.Stderr, "⚠️  WARNING: This migration script is OBSOLETE.\n")
	fmt.Fprintf(os.Stderr, "Satellites/buckets functionality has been removed.\n")
	fmt.Fprintf(os.Stderr, "This script is kept for historical reference only.\n")
	fmt.Fprintf(os.Stderr, "Exiting without making any changes.\n")
	os.Exit(0)

	// Parse command-line flags
	dryRun := flag.Bool("dry-run", false, "Run in dry-run mode (no actual changes)")
	dataDir := flag.String("data-dir", "../data", "Path to data directory")
	flag.Parse()

	// Initialize logger
	log := logger.New(logger.Config{
		Level:  "info",
		Pretty: true,
	})

	log.Info().
		Bool("dry_run", *dryRun).
		Str("data_dir", *dataDir).
		Msg("Starting bucket_balances to cash positions migration")

	// Open databases
	universeDB, err := database.New(database.Config{
		Path:    *dataDir + "/universe.db",
		Profile: database.ProfileStandard,
		Name:    "universe",
	})
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to open universe.db")
	}
	defer universeDB.Close()

	portfolioDB, err := database.New(database.Config{
		Path:    *dataDir + "/portfolio.db",
		Profile: database.ProfileStandard,
		Name:    "portfolio",
	})
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to open portfolio.db")
	}
	defer portfolioDB.Close()

	satellitesDB, err := database.New(database.Config{
		Path:    *dataDir + "/satellites.db",
		Profile: database.ProfileStandard,
		Name:    "satellites",
	})
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to open satellites.db")
	}
	defer satellitesDB.Close()

	// Initialize repositories
	securityRepo := universe.NewSecurityRepository(universeDB.Conn(), log)
	positionRepo := portfolio.NewPositionRepository(portfolioDB.Conn(), universeDB.Conn(), log)
	bucketRepo := satellites.NewBucketRepository(satellitesDB.Conn(), log)

	// Initialize cash security manager
	cashManager := cash_flows.NewCashSecurityManager(
		securityRepo,
		positionRepo,
		universeDB.Conn(),
		portfolioDB.Conn(),
		log,
	)

	// Step 1: Read all bucket_balances
	log.Info().Msg("Reading bucket_balances from satellites.db")
	balances, err := readBucketBalances(satellitesDB.Conn())
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to read bucket_balances")
	}

	log.Info().Int("count", len(balances)).Msg("Found bucket_balances records")

	if len(balances) == 0 {
		log.Info().Msg("No bucket_balances to migrate")
		return
	}

	// Step 2: Calculate total balances by currency (for verification)
	totalsBefore := make(map[string]float64)
	for _, balance := range balances {
		totalsBefore[balance.Currency] += balance.Balance
	}

	log.Info().Interface("totals_before", totalsBefore).Msg("Bucket balance totals by currency")

	// Step 3: Migrate balances to cash positions
	if *dryRun {
		log.Info().Msg("DRY RUN: Simulating migration (no changes will be made)")
		for _, balance := range balances {
			symbol := cash_utils.MakeCashSymbol(balance.Currency, balance.BucketID)
			log.Info().
				Str("bucket_id", balance.BucketID).
				Str("currency", balance.Currency).
				Float64("balance", balance.Balance).
				Str("symbol", symbol).
				Msg("Would create cash position")
		}
		log.Info().Msg("DRY RUN completed successfully")
		return
	}

	// Begin transaction for universe.db (securities creation)
	universeTx, err := universeDB.Conn().Begin()
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to begin universe transaction")
	}
	defer func() { _ = universeTx.Rollback() }()

	// Begin transaction for portfolio.db (positions creation)
	portfolioTx, err := portfolioDB.Conn().Begin()
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to begin portfolio transaction")
	}
	defer func() { _ = portfolioTx.Rollback() }()

	// Migrate each balance
	log.Info().Msg("Migrating balances to cash positions")
	migrated := 0
	for _, balance := range balances {
		// Only create positions for non-zero balances
		if balance.Balance <= 0 {
			log.Warn().
				Str("bucket_id", balance.BucketID).
				Str("currency", balance.Currency).
				Float64("balance", balance.Balance).
				Msg("Skipping zero or negative balance")
			continue
		}

		// Use cashManager to create cash security and position
		err := cashManager.UpdateCashPosition(balance.Currency, balance.Balance)
		if err != nil {
			log.Error().
				Err(err).
				Str("bucket_id", balance.BucketID).
				Str("currency", balance.Currency).
				Float64("balance", balance.Balance).
				Msg("Failed to create cash position")
			log.Fatal().Msg("Migration failed - rolling back transactions")
		}

		migrated++
		log.Info().
			Str("bucket_id", balance.BucketID).
			Str("currency", balance.Currency).
			Float64("balance", balance.Balance).
			Str("symbol", cash_utils.MakeCashSymbol(balance.Currency, balance.BucketID)).
			Msg("Migrated balance to cash position")
	}

	// Step 4: Verify totals match
	log.Info().Msg("Verifying migration - calculating cash position totals")
	totalsAfter := make(map[string]float64)
	for _, balance := range balances {
		if balance.Balance <= 0 {
			continue
		}
		cashBalance, err := cashManager.GetCashBalance(balance.Currency)
		if err != nil {
			log.Error().
				Err(err).
				Str("bucket_id", balance.BucketID).
				Str("currency", balance.Currency).
				Msg("Failed to verify cash position")
			log.Fatal().Msg("Verification failed - rolling back transactions")
		}
		totalsAfter[balance.Currency] += cashBalance
	}

	log.Info().Interface("totals_after", totalsAfter).Msg("Cash position totals by currency")

	// Compare totals
	verified := true
	for currency, beforeTotal := range totalsBefore {
		afterTotal := totalsAfter[currency]
		diff := afterTotal - beforeTotal
		if diff < -0.01 || diff > 0.01 { // Allow for floating point precision
			log.Error().
				Str("currency", currency).
				Float64("before", beforeTotal).
				Float64("after", afterTotal).
				Float64("diff", diff).
				Msg("Total mismatch detected")
			verified = false
		}
	}

	if !verified {
		log.Fatal().Msg("Verification failed - totals do not match - rolling back transactions")
	}

	// Commit transactions
	if err := universeTx.Commit(); err != nil {
		log.Fatal().Err(err).Msg("Failed to commit universe transaction")
	}
	log.Info().Msg("Universe transaction committed")

	if err := portfolioTx.Commit(); err != nil {
		log.Fatal().Err(err).Msg("Failed to commit portfolio transaction")
	}
	log.Info().Msg("Portfolio transaction committed")

	// Success!
	log.Info().
		Int("migrated", migrated).
		Int("total_balances", len(balances)).
		Msg("Migration completed successfully")

	log.Info().Msg("")
	log.Info().Msg("NEXT STEPS:")
	log.Info().Msg("1. Run verification script: go run scripts/migration/verify_cash_migration.go")
	log.Info().Msg("2. Monitor application for 48 hours")
	log.Info().Msg("3. After stable operation, drop bucket_balances table:")
	log.Info().Msg("   sqlite3 ../data/satellites.db < internal/database/migrations/011_remove_bucket_balances.sql")
}

// readBucketBalances reads all rows from the bucket_balances table
func readBucketBalances(db *sql.DB) ([]BucketBalance, error) {
	query := "SELECT bucket_id, currency, balance, updated_at FROM bucket_balances ORDER BY bucket_id, currency"

	rows, err := db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query bucket_balances: %w", err)
	}
	defer rows.Close()

	var balances []BucketBalance
	for rows.Next() {
		var balance BucketBalance
		if err := rows.Scan(&balance.BucketID, &balance.Currency, &balance.Balance, &balance.UpdatedAt); err != nil {
			return nil, fmt.Errorf("failed to scan bucket_balance: %w", err)
		}
		balances = append(balances, balance)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating bucket_balances: %w", err)
	}

	return balances, nil
}
