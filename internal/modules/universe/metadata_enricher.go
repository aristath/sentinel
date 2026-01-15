package universe

import (
	"fmt"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/rs/zerolog"
)

// SectorMapping maps Tradernet sector codes to industry names
var SectorMapping = map[string]string{
	"FIN": "Financial Services",
	"TEC": "Technology",
	"HLT": "Healthcare",
	"CST": "Consumer Staples",
	"CSD": "Consumer Discretionary",
	"IND": "Industrials",
	"MAT": "Materials",
	"ENE": "Energy",
	"UTL": "Utilities",
	"COM": "Communication Services",
	"REI": "Real Estate",
	"OTH": "Other",
}

// MapSectorToIndustry converts a Tradernet sector code to an industry name
func MapSectorToIndustry(sectorCode string) string {
	if industry, ok := SectorMapping[sectorCode]; ok {
		return industry
	}
	return ""
}

// MetadataEnricher enriches security metadata from broker API
type MetadataEnricher struct {
	brokerClient domain.BrokerClient
	log          zerolog.Logger
}

// NewMetadataEnricher creates a new metadata enricher
func NewMetadataEnricher(brokerClient domain.BrokerClient, log zerolog.Logger) *MetadataEnricher {
	return &MetadataEnricher{
		brokerClient: brokerClient,
		log:          log.With().Str("service", "metadata_enricher").Logger(),
	}
}

// Enrich fills in missing metadata from broker API
// Only fills fields that are empty - does not overwrite existing data
func (e *MetadataEnricher) Enrich(security *Security) error {
	if security == nil {
		return fmt.Errorf("security cannot be nil")
	}

	// Skip enrichment if no broker client
	if e.brokerClient == nil {
		e.log.Warn().Str("symbol", security.Symbol).Msg("No broker client, skipping enrichment")
		return nil
	}

	// Use GetSecurityMetadata for full metadata including CountryOfRisk
	// This uses getAllSecurities API which has better country data than FindSymbol
	brokerInfo, err := e.brokerClient.GetSecurityMetadata(security.Symbol)
	if err != nil || brokerInfo == nil {
		if err != nil {
			e.log.Warn().Err(err).Str("symbol", security.Symbol).Msg("GetSecurityMetadata failed, trying FindSymbol fallback")
		}
		// Fallback to FindSymbol
		results, findErr := e.brokerClient.FindSymbol(security.Symbol, nil)
		if findErr != nil {
			return fmt.Errorf("failed to find symbol: %w", findErr)
		}
		if len(results) == 0 {
			e.log.Debug().Str("symbol", security.Symbol).Msg("No broker data found for symbol")
			return nil
		}
		brokerInfo = &results[0]
	}

	// Enrich only missing fields (don't overwrite existing data)
	enriched := false

	if security.Name == "" && brokerInfo.Name != nil && *brokerInfo.Name != "" {
		security.Name = *brokerInfo.Name
		enriched = true
	}

	if security.ISIN == "" && brokerInfo.ISIN != nil && *brokerInfo.ISIN != "" {
		security.ISIN = *brokerInfo.ISIN
		enriched = true
	}

	if security.Currency == "" && brokerInfo.Currency != nil && *brokerInfo.Currency != "" {
		security.Currency = *brokerInfo.Currency
		enriched = true
	}

	// Geography: prefer CountryOfRisk, fallback to Country, reject "0"
	// Always overwrite - Tradernet is source of truth, user customizations go to override table
	{
		country := ""
		if brokerInfo.CountryOfRisk != nil && *brokerInfo.CountryOfRisk != "" {
			country = *brokerInfo.CountryOfRisk
		} else if brokerInfo.Country != nil && *brokerInfo.Country != "" && *brokerInfo.Country != "0" {
			country = *brokerInfo.Country
		}
		// Always write - empty string clears bad data like "0"
		if security.Geography != country {
			security.Geography = country
			enriched = true
		}
	}

	if security.Industry == "" && brokerInfo.Sector != nil && *brokerInfo.Sector != "" {
		industry := MapSectorToIndustry(*brokerInfo.Sector)
		if industry != "" {
			security.Industry = industry
			enriched = true
		}
	}

	if security.FullExchangeName == "" && brokerInfo.ExchangeName != nil && *brokerInfo.ExchangeName != "" {
		security.FullExchangeName = *brokerInfo.ExchangeName
		enriched = true
	}

	if security.MarketCode == "" && brokerInfo.Market != nil && *brokerInfo.Market != "" {
		security.MarketCode = *brokerInfo.Market
		enriched = true
	}

	if enriched {
		e.log.Info().
			Str("symbol", security.Symbol).
			Str("name", security.Name).
			Str("geography", security.Geography).
			Str("industry", security.Industry).
			Str("market_code", security.MarketCode).
			Msg("Enriched security metadata from broker")
	} else {
		e.log.Debug().
			Str("symbol", security.Symbol).
			Msg("No new metadata to enrich (all fields already populated)")
	}

	return nil
}
