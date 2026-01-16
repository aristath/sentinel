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
// Tradernet is the source of truth - stores complete API response as JSON
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

	// Build SecurityData from BrokerSecurityInfo - store complete API response as JSON
	data := universe.SecurityData{
		Name:               stringValue(info.Name),
		Currency:           stringValue(info.Currency),
		Geography:          stringValue(info.CountryOfRisk), // Use CountryOfRisk as primary source
		Industry:           mapSectorToIndustry(stringValue(info.Sector)),
		FullExchangeName:   stringValue(info.ExchangeName),
		MarketCode:         stringValue(info.Market),
		MinLot:             intValue(info.LotSize),
		ProductType:        security.ProductType,        // Preserve existing
		MinPortfolioTarget: security.MinPortfolioTarget, // Preserve existing
		MaxPortfolioTarget: security.MaxPortfolioTarget, // Preserve existing
		TradernetRaw: map[string]interface{}{
			"country":         stringValue(info.Country),
			"country_of_risk": stringValue(info.CountryOfRisk),
			"sector":          stringValue(info.Sector),
			"exchange_code":   stringValue(info.ExchangeCode),
			"lot_size":        intValue(info.LotSize),
		},
	}

	// Serialize to JSON
	jsonData, err := universe.SerializeSecurityJSON(&data)
	if err != nil {
		return false, fmt.Errorf("failed to serialize security data: %w", err)
	}

	// Update security with JSON data and last_synced timestamp
	updates := map[string]any{
		"data":        jsonData,
		"last_synced": time.Now().Unix(),
	}

	err = j.securityRepo.Update(security.ISIN, updates)
	if err != nil {
		return false, fmt.Errorf("failed to update security %s: %w", security.Symbol, err)
	}

	j.log.Info().
		Str("symbol", security.Symbol).
		Str("isin", security.ISIN).
		Str("geography", data.Geography).
		Str("industry", data.Industry).
		Msg("Updated security metadata from Tradernet (JSON)")
	return true, nil
}

// stringValue safely extracts string from nullable pointer
func stringValue(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

// intValue safely extracts int from nullable pointer
func intValue(i *int) int {
	if i == nil {
		return 1 // Default lot size
	}
	return *i
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
