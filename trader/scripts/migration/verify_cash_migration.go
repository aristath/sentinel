//go:build ignore
// +build ignore

package main

import (
	"database/sql"
	"flag"
	"fmt"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/internal/modules/cash_flows"
	"github.com/aristath/arduino-trader/internal/modules/cash_utils"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/satellites"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/aristath/arduino-trader/pkg/logger"
)

// BucketBalanceRow represents a row from the bucket_balances table (for verification)
type BucketBalanceRow struct {
	BucketID string
	Currency string
	Balance  float64
}

func main() {
	// Parse command-line flags
	dataDir := flag.String("data-dir", "../data", "Path to data directory")
	flag.Parse()

	// Initialize logger
	log := logger.New(logger.Config{
		Level:  "info",
		Pretty: true,
	})

	log.Info().
		Str("data_dir", *dataDir).
		Msg("Starting cash migration verification")

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

	// Initialize cash security manager (for potential future use)
	_ = cash_flows.NewCashSecurityManager(
		securityRepo,
		positionRepo,
		bucketRepo,
		universeDB.Conn(),
		portfolioDB.Conn(),
		log,
	)

	// Check 1: Verify bucket_balances table exists
	log.Info().Msg("Check 1: Verifying bucket_balances table exists")
	bucketBalances, err := readBucketBalances(satellitesDB.Conn())
	if err != nil {
		log.Warn().Err(err).Msg("bucket_balances table may have been dropped (this is OK after migration)")
		bucketBalances = []BucketBalanceRow{}
		_ = bucketBalances // Suppress unused variable warning if table doesn't exist
	} else {
		log.Info().Int("count", len(bucketBalances)).Msg("Found bucket_balances records")
	}

	// Check 2: Count cash securities
	log.Info().Msg("Check 2: Counting cash securities in universe.db")
	cashSecurityCount, err := countCashSecurities(universeDB.Conn())
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to count cash securities")
	}
	log.Info().Int("count", cashSecurityCount).Msg("Found cash securities")

	// Check 3: Count cash positions
	log.Info().Msg("Check 3: Counting cash positions in portfolio.db")
	cashPositionCount, err := countCashPositions(portfolioDB.Conn())
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to count cash positions")
	}
	log.Info().Int("count", cashPositionCount).Msg("Found cash positions")

	// Check 4: Verify each cash position has a corresponding security
	log.Info().Msg("Check 4: Verifying cash positions have corresponding securities")
	cashPositions, err := getCashPositions(portfolioDB.Conn())
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to get cash positions")
	}

	orphanedPositions := 0
	for _, pos := range cashPositions {
		security, err := securityRepo.GetBySymbol(pos.Symbol)
		if err != nil {
			log.Fatal().Err(err).Str("symbol", pos.Symbol).Msg("Failed to check security")
		}
		if security == nil {
			log.Error().Str("symbol", pos.Symbol).Msg("Cash position has no corresponding security")
			orphanedPositions++
		}
	}

	if orphanedPositions > 0 {
		log.Error().Int("count", orphanedPositions).Msg("Found orphaned cash positions")
	} else {
		log.Info().Msg("All cash positions have corresponding securities")
	}

	// Check 5: Verify symbol format
	log.Info().Msg("Check 5: Verifying cash symbol format")
	invalidSymbols := 0
	for _, pos := range cashPositions {
		if !cash_utils.IsCashSymbol(pos.Symbol) {
			log.Error().Str("symbol", pos.Symbol).Msg("Invalid cash symbol format")
			invalidSymbols++
			continue
		}

		currency, bucketID, err := cash_utils.ParseCashSymbol(pos.Symbol)
		if err != nil {
			log.Error().Err(err).Str("symbol", pos.Symbol).Msg("Failed to parse cash symbol")
			invalidSymbols++
			continue
		}

		log.Debug().
			Str("symbol", pos.Symbol).
			Str("currency", currency).
			Str("bucket_id", bucketID).
			Msg("Valid cash symbol")
	}

	if invalidSymbols > 0 {
		log.Error().Int("count", invalidSymbols).Msg("Found invalid cash symbols")
	} else {
		log.Info().Msg("All cash symbols are valid")
	}

	// Check 6: Compare totals (if bucket_balances still exists)
	if len(bucketBalances) > 0 {
		log.Info().Msg("Check 6: Comparing bucket_balances totals with cash positions")

		// Calculate bucket_balances totals by currency
		bucketTotals := make(map[string]float64)
		for _, balance := range bucketBalances {
			bucketTotals[balance.Currency] += balance.Balance
		}

		// Calculate cash position totals by currency
		positionTotals := make(map[string]float64)
		for _, pos := range cashPositions {
			currency, _, err := cash_utils.ParseCashSymbol(pos.Symbol)
			if err != nil {
				continue
			}
			positionTotals[currency] += pos.Quantity
		}

		// Compare
		mismatch := false
		for currency, bucketTotal := range bucketTotals {
			positionTotal := positionTotals[currency]
			diff := positionTotal - bucketTotal
			if diff < -0.01 || diff > 0.01 { // Allow for floating point precision
				log.Error().
					Str("currency", currency).
					Float64("bucket_balances", bucketTotal).
					Float64("cash_positions", positionTotal).
					Float64("diff", diff).
					Msg("Total mismatch")
				mismatch = true
			} else {
				log.Info().
					Str("currency", currency).
					Float64("total", bucketTotal).
					Msg("Totals match")
			}
		}

		// Check for currencies in positions but not in bucket_balances
		for currency, positionTotal := range positionTotals {
			if _, exists := bucketTotals[currency]; !exists {
				log.Warn().
					Str("currency", currency).
					Float64("cash_positions", positionTotal).
					Msg("Currency in positions but not in bucket_balances (may be new)")
			}
		}

		if mismatch {
			log.Error().Msg("VERIFICATION FAILED: Totals do not match")
			return
		}
	} else {
		log.Info().Msg("Check 6: Skipped (bucket_balances table not found)")
	}

	// Summary
	log.Info().Msg("")
	log.Info().Msg("=== VERIFICATION SUMMARY ===")
	log.Info().Int("bucket_balances_count", len(bucketBalances)).Msg("Bucket balances")
	log.Info().Int("cash_securities_count", cashSecurityCount).Msg("Cash securities")
	log.Info().Int("cash_positions_count", cashPositionCount).Msg("Cash positions")
	log.Info().Int("orphaned_positions", orphanedPositions).Msg("Orphaned positions")
	log.Info().Int("invalid_symbols", invalidSymbols).Msg("Invalid symbols")

	if orphanedPositions > 0 || invalidSymbols > 0 {
		log.Error().Msg("VERIFICATION FAILED")
		return
	}

	log.Info().Msg("VERIFICATION PASSED ✓")
}

// readBucketBalances reads all rows from the bucket_balances table
func readBucketBalances(db *sql.DB) ([]BucketBalanceRow, error) {
	query := "SELECT bucket_id, currency, balance FROM bucket_balances ORDER BY bucket_id, currency"

	rows, err := db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query bucket_balances: %w", err)
	}
	defer rows.Close()

	var balances []BucketBalanceRow
	for rows.Next() {
		var balance BucketBalanceRow
		if err := rows.Scan(&balance.BucketID, &balance.Currency, &balance.Balance); err != nil {
			return nil, fmt.Errorf("failed to scan bucket_balance: %w", err)
		}
		balances = append(balances, balance)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating bucket_balances: %w", err)
	}

	return balances, nil
}

// countCashSecurities counts securities with product_type='CASH'
func countCashSecurities(db *sql.DB) (int, error) {
	var count int
	err := db.QueryRow("SELECT COUNT(*) FROM securities WHERE product_type = 'CASH'").Scan(&count)
	return count, err
}

// countCashPositions counts positions with symbol LIKE 'CASH:%'
func countCashPositions(db *sql.DB) (int, error) {
	var count int
	err := db.QueryRow("SELECT COUNT(*) FROM positions WHERE symbol LIKE 'CASH:%'").Scan(&count)
	return count, err
}

// CashPosition represents minimal info from a cash position
type CashPosition struct {
	Symbol   string
	Quantity float64
}

// getCashPositions returns all cash positions
func getCashPositions(db *sql.DB) ([]CashPosition, error) {
	query := "SELECT symbol, quantity FROM positions WHERE symbol LIKE 'CASH:%'"

	rows, err := db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query cash positions: %w", err)
	}
	defer rows.Close()

	var positions []CashPosition
	for rows.Next() {
		var pos CashPosition
		if err := rows.Scan(&pos.Symbol, &pos.Quantity); err != nil {
			return nil, fmt.Errorf("failed to scan cash position: %w", err)
		}
		positions = append(positions, pos)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating cash positions: %w", err)
	}

	return positions, nil
}
