// Package di provides dependency injection for database connections.
package di

import (
	"fmt"

	"github.com/aristath/sentinel/internal/config"
	"github.com/aristath/sentinel/internal/database"
	"github.com/rs/zerolog"
)

// InitializeDatabases initializes all 7 databases and applies schemas
func InitializeDatabases(cfg *config.Config, log zerolog.Logger) (*Container, error) {
	container := &Container{}

	// 1. universe.db - Investment universe (securities, groups)
	universeDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/universe.db",
		Profile: database.ProfileStandard,
		Name:    "universe",
	})
	if err != nil {
		return nil, fmt.Errorf("failed to initialize universe database: %w", err)
	}
	container.UniverseDB = universeDB

	// 2. config.db - Application configuration (settings, allocation targets)
	configDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/config.db",
		Profile: database.ProfileStandard,
		Name:    "config",
	})
	if err != nil {
		universeDB.Close()
		return nil, fmt.Errorf("failed to initialize config database: %w", err)
	}
	container.ConfigDB = configDB

	// 3. ledger.db - Immutable financial audit trail (trades, cash flows, dividends)
	ledgerDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/ledger.db",
		Profile: database.ProfileLedger, // Maximum safety for immutable audit trail
		Name:    "ledger",
	})
	if err != nil {
		universeDB.Close()
		configDB.Close()
		return nil, fmt.Errorf("failed to initialize ledger database: %w", err)
	}
	container.LedgerDB = ledgerDB

	// 4. portfolio.db - Current portfolio state (positions, scores, metrics, snapshots)
	portfolioDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/portfolio.db",
		Profile: database.ProfileStandard,
		Name:    "portfolio",
	})
	if err != nil {
		universeDB.Close()
		configDB.Close()
		ledgerDB.Close()
		return nil, fmt.Errorf("failed to initialize portfolio database: %w", err)
	}
	container.PortfolioDB = portfolioDB

	// 5. history.db - Historical time-series data (prices, rates, cleanup tracking)
	historyDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/history.db",
		Profile: database.ProfileStandard,
		Name:    "history",
	})
	if err != nil {
		universeDB.Close()
		configDB.Close()
		ledgerDB.Close()
		portfolioDB.Close()
		return nil, fmt.Errorf("failed to initialize history database: %w", err)
	}
	container.HistoryDB = historyDB

	// 6. cache.db - Ephemeral operational data (job history)
	cacheDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/cache.db",
		Profile: database.ProfileCache, // Maximum speed for ephemeral data
		Name:    "cache",
	})
	if err != nil {
		universeDB.Close()
		configDB.Close()
		ledgerDB.Close()
		portfolioDB.Close()
		historyDB.Close()
		return nil, fmt.Errorf("failed to initialize cache database: %w", err)
	}
	container.CacheDB = cacheDB

	// 7. client_data.db - External API response cache (Alpha Vantage, Yahoo, OpenFIGI, ExchangeRate)
	clientDataDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/client_data.db",
		Profile: database.ProfileCache, // Maximum speed for cache data
		Name:    "client_data",
	})
	if err != nil {
		universeDB.Close()
		configDB.Close()
		ledgerDB.Close()
		portfolioDB.Close()
		historyDB.Close()
		cacheDB.Close()
		return nil, fmt.Errorf("failed to initialize client_data database: %w", err)
	}
	container.ClientDataDB = clientDataDB

	// Apply schemas to all databases (single source of truth)
	for _, db := range []*database.DB{universeDB, configDB, ledgerDB, portfolioDB, historyDB, cacheDB, clientDataDB} {
		if err := db.Migrate(); err != nil {
			// Cleanup on error
			universeDB.Close()
			configDB.Close()
			ledgerDB.Close()
			portfolioDB.Close()
			historyDB.Close()
			cacheDB.Close()
			clientDataDB.Close()
			return nil, fmt.Errorf("failed to apply schema to %s: %w", db.Name(), err)
		}
	}

	log.Info().Msg("All databases initialized and schemas applied")

	return container, nil
}
