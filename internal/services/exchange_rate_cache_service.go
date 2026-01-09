package services

import (
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/clients/exchangerate"
	"github.com/aristath/sentinel/internal/clients/yahoo"
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// SettingsServiceInterface defines the contract for settings operations
type SettingsServiceInterface interface {
	Get(key string) (interface{}, error)
	Set(key string, value interface{}) (bool, error)
}

// ExchangeRateCacheService provides cached exchange rates with fallback
type ExchangeRateCacheService struct {
	exchangeRateAPIClient   *exchangerate.Client                    // ExchangeRate API (primary)
	currencyExchangeService domain.CurrencyExchangeServiceInterface // Tradernet
	yahooClient             yahoo.FullClientInterface               // Yahoo fallback
	historyDB               *universe.HistoryDB                     // Cache storage
	settingsService         SettingsServiceInterface                // Staleness config
	log                     zerolog.Logger
}

// NewExchangeRateCacheService creates a new exchange rate cache service
func NewExchangeRateCacheService(
	exchangeRateAPIClient *exchangerate.Client,
	currencyExchangeService domain.CurrencyExchangeServiceInterface,
	yahooClient yahoo.FullClientInterface,
	historyDB *universe.HistoryDB,
	settingsService SettingsServiceInterface,
	log zerolog.Logger,
) *ExchangeRateCacheService {
	return &ExchangeRateCacheService{
		exchangeRateAPIClient:   exchangeRateAPIClient,
		currencyExchangeService: currencyExchangeService,
		yahooClient:             yahooClient,
		historyDB:               historyDB,
		settingsService:         settingsService,
		log:                     log.With().Str("service", "exchange_rate_cache").Logger(),
	}
}

// GetRate returns exchange rate with 5-tier fallback:
// 1. Try exchangerate-api.com (primary - fast, free, no auth)
// 2. Try Tradernet (fallback - uses broker's FX instruments)
// 3. Try Yahoo Finance (fallback)
// 4. Try cached rate from DB
// 5. Use hardcoded fallback rates
func (s *ExchangeRateCacheService) GetRate(fromCurrency, toCurrency string) (float64, error) {
	if fromCurrency == toCurrency {
		return 1.0, nil
	}

	// Tier 1: Try exchangerate-api.com (NEW PRIMARY)
	if s.exchangeRateAPIClient != nil {
		rate, err := s.exchangeRateAPIClient.GetRate(fromCurrency, toCurrency)
		if err == nil && rate > 0 {
			s.log.Debug().
				Str("from", fromCurrency).
				Str("to", toCurrency).
				Float64("rate", rate).
				Str("source", "exchangerate-api").
				Msg("Got rate from ExchangeRate API")
			return rate, nil
		}
		s.log.Warn().Err(err).Msg("ExchangeRateAPI fetch failed, trying Tradernet")
	}

	// Tier 2: Try Tradernet (was Tier 1)
	if s.currencyExchangeService != nil {
		rate, err := s.currencyExchangeService.GetRate(fromCurrency, toCurrency)
		if err == nil && rate > 0 {
			s.log.Debug().
				Str("from", fromCurrency).
				Str("to", toCurrency).
				Float64("rate", rate).
				Str("source", "tradernet").
				Msg("Got rate from Tradernet")
			return rate, nil
		}
		s.log.Warn().Err(err).Msg("Tradernet rate fetch failed, trying Yahoo")
	}

	// Tier 3: Try Yahoo Finance (was Tier 2)
	if s.yahooClient != nil {
		rate, err := s.yahooClient.GetExchangeRate(fromCurrency, toCurrency)
		if err == nil && rate > 0 {
			s.log.Debug().
				Str("from", fromCurrency).
				Str("to", toCurrency).
				Float64("rate", rate).
				Str("source", "yahoo").
				Msg("Got rate from Yahoo Finance")
			return rate, nil
		}
		s.log.Warn().Err(err).Msg("Yahoo rate fetch failed, trying cache")
	}

	// Tier 4: Try cached rate (was Tier 3)
	rate, err := s.GetCachedRate(fromCurrency, toCurrency)
	if err == nil && rate > 0 {
		s.log.Warn().
			Str("from", fromCurrency).
			Str("to", toCurrency).
			Float64("rate", rate).
			Str("source", "cache").
			Msg("Using cached rate (APIs failed)")
		return rate, nil
	}

	// Tier 5: Hardcoded fallback (last resort - was Tier 4)
	rate = s.getHardcodedRate(fromCurrency, toCurrency)
	if rate > 0 {
		s.log.Warn().
			Str("from", fromCurrency).
			Str("to", toCurrency).
			Float64("rate", rate).
			Str("source", "hardcoded").
			Msg("Using hardcoded fallback rate")
		return rate, nil
	}

	return 0, fmt.Errorf("no rate available for %s/%s", fromCurrency, toCurrency)
}

// GetCachedRate fetches rate from database only
// Checks staleness and logs warning if rate is old
func (s *ExchangeRateCacheService) GetCachedRate(fromCurrency, toCurrency string) (float64, error) {
	er, err := s.historyDB.GetLatestExchangeRate(fromCurrency, toCurrency)
	if err != nil {
		return 0, err
	}
	if er == nil {
		return 0, fmt.Errorf("no cached rate found")
	}

	// Check staleness
	maxAgeHours := 48.0
	if s.settingsService != nil {
		if val, err := s.settingsService.Get("max_exchange_rate_age_hours"); err == nil {
			if floatVal, ok := val.(float64); ok {
				maxAgeHours = floatVal
			}
		}
	}

	age := time.Since(er.Date)
	if age > time.Duration(maxAgeHours)*time.Hour {
		s.log.Warn().
			Str("from", fromCurrency).
			Str("to", toCurrency).
			Dur("age", age).
			Msg("Cached rate is stale but using anyway")
	}

	return er.Rate, nil
}

// SyncRates fetches and caches rates for all currency pairs
// Returns error only if ALL rate fetches fail
// Partial success is OK - logged as warnings
func (s *ExchangeRateCacheService) SyncRates() error {
	currencies := []string{"EUR", "USD", "GBP", "HKD"}

	errorCount := 0
	successCount := 0

	for _, from := range currencies {
		for _, to := range currencies {
			if from == to {
				continue
			}

			rate, err := s.GetRate(from, to)
			if err != nil {
				s.log.Error().
					Err(err).
					Str("from", from).
					Str("to", to).
					Msg("Failed to get rate")
				errorCount++
				continue
			}

			// Store in database
			if err := s.historyDB.UpsertExchangeRate(from, to, rate); err != nil {
				s.log.Error().
					Err(err).
					Str("from", from).
					Str("to", to).
					Msg("Failed to cache rate")
				errorCount++
				continue
			}

			s.log.Debug().
				Str("from", from).
				Str("to", to).
				Float64("rate", rate).
				Msg("Cached exchange rate")

			successCount++
		}
	}

	s.log.Info().
		Int("success", successCount).
		Int("errors", errorCount).
		Msg("Exchange rate sync completed")

	if successCount == 0 {
		return fmt.Errorf("all rate fetches failed")
	}

	return nil // Partial success OK
}

// getHardcodedRate returns hardcoded fallback rates
// Based on existing fallback rates in the codebase
func (s *ExchangeRateCacheService) getHardcodedRate(fromCurrency, toCurrency string) float64 {
	// Hardcoded EUR conversion rates (from existing codebase)
	if fromCurrency == "EUR" {
		switch toCurrency {
		case "USD":
			return 1.0 / 0.9 // ~1.11 (EUR→USD)
		case "GBP":
			return 1.0 / 1.2 // ~0.83 (EUR→GBP)
		case "HKD":
			return 1.0 / 0.11 // ~9.09 (EUR→HKD)
		}
	}
	if toCurrency == "EUR" {
		switch fromCurrency {
		case "USD":
			return 0.9 // USD→EUR
		case "GBP":
			return 1.2 // GBP→EUR
		case "HKD":
			return 0.11 // HKD→EUR
		}
	}
	return 0
}
