// Package scheduler provides job scheduling functionality.
package scheduler

import (
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// TradernetMetadataSyncJob populates Tradernet metadata for existing securities
// This job fetches geography (country), industry (sector), exchange name, and market code
// from Tradernet for securities that are missing this information.
type TradernetMetadataSyncJob struct {
	JobBase
	log          zerolog.Logger
	securityRepo *universe.SecurityRepository
	brokerClient domain.BrokerClient
}

// TradernetMetadataSyncJobConfig holds configuration for Tradernet metadata sync job
type TradernetMetadataSyncJobConfig struct {
	Log          zerolog.Logger
	SecurityRepo *universe.SecurityRepository
	BrokerClient domain.BrokerClient
}

// NewTradernetMetadataSyncJob creates a new Tradernet metadata sync job
func NewTradernetMetadataSyncJob(cfg TradernetMetadataSyncJobConfig) *TradernetMetadataSyncJob {
	return &TradernetMetadataSyncJob{
		log:          cfg.Log.With().Str("job", "tradernet_metadata_sync").Logger(),
		securityRepo: cfg.SecurityRepo,
		brokerClient: cfg.BrokerClient,
	}
}

// Name returns the job name
func (j *TradernetMetadataSyncJob) Name() string {
	return "tradernet_metadata_sync"
}

// Run executes the Tradernet metadata sync
func (j *TradernetMetadataSyncJob) Run() error {
	j.log.Info().Msg("Starting Tradernet metadata sync")
	startTime := time.Now()

	// Check if broker client is available
	if j.brokerClient == nil {
		return fmt.Errorf("broker client not available")
	}

	if !j.brokerClient.IsConnected() {
		j.log.Warn().Msg("Tradernet not connected, skipping metadata sync")
		return nil // Not an error, just skip
	}

	// Get all active securities
	securities, err := j.securityRepo.GetAllActive()
	if err != nil {
		return fmt.Errorf("failed to get active securities: %w", err)
	}

	j.log.Info().Int("count", len(securities)).Msg("Found active securities")

	updated := 0
	skipped := 0
	failed := 0

	for _, security := range securities {
		// Fetch metadata from Tradernet and update security
		// Always updates fields - Tradernet is source of truth, overrides are for user customizations
		wasUpdated, err := j.fetchAndUpdateMetadata(&security)
		if err != nil {
			j.log.Warn().
				Err(err).
				Str("symbol", security.Symbol).
				Str("isin", security.ISIN).
				Msg("Failed to fetch metadata for security")
			failed++
			continue
		}

		if wasUpdated {
			updated++
		} else {
			skipped++
		}
	}

	duration := time.Since(startTime)
	j.log.Info().
		Int("updated", updated).
		Int("skipped", skipped).
		Int("failed", failed).
		Dur("duration", duration).
		Msg("Tradernet metadata sync completed")

	return nil
}

// fetchAndUpdateMetadata fetches metadata from Tradernet and updates the security
// Returns true if any fields were updated, false if no data from Tradernet
// Tradernet is the source of truth - always overwrites existing values
// User customizations should be stored in security_overrides table
func (j *TradernetMetadataSyncJob) fetchAndUpdateMetadata(security *universe.Security) (bool, error) {
	// Use GetSecurityMetadata which calls getAllSecurities API
	// This returns issuer_country_code and sector_code, unlike FindSymbol (tickerFinder)
	info, err := j.brokerClient.GetSecurityMetadata(security.Symbol)
	if err != nil {
		return false, fmt.Errorf("failed to get security metadata for %s: %w", security.Symbol, err)
	}

	if info == nil {
		j.log.Debug().
			Str("symbol", security.Symbol).
			Msg("No results from Tradernet GetSecurityMetadata")
		return false, nil // Not an error, just no data
	}

	// Build update map - always update from Tradernet (source of truth)
	updates := make(map[string]any)

	// Geography: from country code
	if info.Country != nil && *info.Country != "" {
		updates["geography"] = *info.Country
		j.log.Debug().
			Str("symbol", security.Symbol).
			Str("geography", *info.Country).
			Msg("Setting geography from Tradernet")
	}

	// Industry: from sector code (map to readable industry name)
	if info.Sector != nil && *info.Sector != "" {
		industry := mapSectorToIndustry(*info.Sector)
		updates["industry"] = industry
		j.log.Debug().
			Str("symbol", security.Symbol).
			Str("sector", *info.Sector).
			Str("industry", industry).
			Msg("Setting industry from Tradernet sector")
	}

	// Full exchange name
	if info.ExchangeName != nil && *info.ExchangeName != "" {
		updates["fullExchangeName"] = *info.ExchangeName
		j.log.Debug().
			Str("symbol", security.Symbol).
			Str("exchangeName", *info.ExchangeName).
			Msg("Setting exchange name from Tradernet")
	}

	// Market code
	if info.Market != nil && *info.Market != "" {
		updates["market_code"] = *info.Market
		j.log.Debug().
			Str("symbol", security.Symbol).
			Str("marketCode", *info.Market).
			Msg("Setting market code from Tradernet")
	}

	// Update security if Tradernet provided any data
	if len(updates) > 0 {
		err := j.securityRepo.Update(security.ISIN, updates)
		if err != nil {
			return false, fmt.Errorf("failed to update security %s: %w", security.Symbol, err)
		}

		j.log.Info().
			Str("symbol", security.Symbol).
			Str("isin", security.ISIN).
			Int("fieldsUpdated", len(updates)).
			Msg("Updated security metadata from Tradernet")
		return true, nil
	}

	return false, nil
}

// mapSectorToIndustry maps Tradernet sector codes to readable industry names
// Based on Tradernet sector code documentation
func mapSectorToIndustry(sectorCode string) string {
	// Common sector code mappings from Tradernet
	sectorMap := map[string]string{
		"Technology":             "Technology",
		"Financial Services":     "Financial Services",
		"Healthcare":             "Healthcare",
		"Consumer Cyclical":      "Consumer Cyclical",
		"Consumer Defensive":     "Consumer Defensive",
		"Communication Services": "Communication Services",
		"Industrials":            "Industrials",
		"Energy":                 "Energy",
		"Utilities":              "Utilities",
		"Real Estate":            "Real Estate",
		"Basic Materials":        "Basic Materials",
	}

	if industry, ok := sectorMap[sectorCode]; ok {
		return industry
	}

	// If not in map, return sector code as-is (it's already readable in most cases)
	return sectorCode
}
