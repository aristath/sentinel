package universe

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/rs/zerolog"
)

// MetadataSyncService syncs Tradernet metadata for securities.
// Stores raw Tradernet API response in the data column for field mapping on read.
type MetadataSyncService struct {
	securityRepo *SecurityRepository
	brokerClient domain.BrokerClient
	log          zerolog.Logger
}

// NewMetadataSyncService creates a new metadata sync service.
func NewMetadataSyncService(
	securityRepo *SecurityRepository,
	brokerClient domain.BrokerClient,
	log zerolog.Logger,
) *MetadataSyncService {
	return &MetadataSyncService{
		securityRepo: securityRepo,
		brokerClient: brokerClient,
		log:          log.With().Str("service", "metadata_sync").Logger(),
	}
}

// SyncMetadata syncs Tradernet metadata for a security identified by ISIN.
// Stores raw Tradernet API response (securities[0]) in the data column.
// Field mapping is applied on read via SecurityFromJSON.
// Returns the symbol for progress reporting.
func (s *MetadataSyncService) SyncMetadata(isin string) (string, error) {
	// Get security by ISIN
	security, err := s.securityRepo.GetByISIN(isin)
	if err != nil {
		return "", fmt.Errorf("failed to get security %s: %w", isin, err)
	}
	if security == nil {
		s.log.Debug().Str("isin", isin).Msg("Security not found, skipping")
		return "", nil
	}

	// Call Tradernet API to get raw response
	rawResponse, err := s.brokerClient.GetSecurityMetadataRaw(security.Symbol)
	if err != nil {
		return security.Symbol, fmt.Errorf("failed to fetch metadata for %s: %w", isin, err)
	}
	if rawResponse == nil {
		s.log.Debug().Str("isin", isin).Str("symbol", security.Symbol).Msg("No metadata returned from broker")
		return security.Symbol, nil
	}

	// Extract securities[0] from raw response
	responseMap, ok := rawResponse.(map[string]interface{})
	if !ok {
		return security.Symbol, fmt.Errorf("unexpected response format for %s: expected map", isin)
	}

	securities, ok := responseMap["securities"].([]interface{})
	if !ok || len(securities) == 0 {
		s.log.Debug().Str("isin", isin).Str("symbol", security.Symbol).Msg("No securities in response")
		return security.Symbol, nil
	}

	// Get first security object
	securityData := securities[0]

	// Marshal to JSON
	jsonBytes, err := json.Marshal(securityData)
	if err != nil {
		return security.Symbol, fmt.Errorf("failed to marshal security data for %s: %w", isin, err)
	}

	// Store raw data with last_synced timestamp
	updates := map[string]any{
		"data":        string(jsonBytes),
		"last_synced": time.Now().Unix(),
	}

	if err := s.securityRepo.Update(isin, updates); err != nil {
		return security.Symbol, fmt.Errorf("failed to update security %s: %w", isin, err)
	}

	s.log.Debug().
		Str("isin", isin).
		Str("symbol", security.Symbol).
		Int("data_size", len(jsonBytes)).
		Msg("Synced raw metadata for security")

	return security.Symbol, nil
}

// GetAllActiveISINs returns all active security ISINs for metadata sync.
func (s *MetadataSyncService) GetAllActiveISINs() []string {
	securities, err := s.securityRepo.GetAllActive()
	if err != nil {
		s.log.Error().Err(err).Msg("Failed to get active securities")
		return nil
	}

	isins := make([]string, 0, len(securities))
	for _, sec := range securities {
		if sec.ISIN != "" {
			isins = append(isins, sec.ISIN)
		}
	}

	return isins
}
