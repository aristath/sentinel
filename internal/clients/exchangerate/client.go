// Package exchangerate provides currency exchange rate fetching and caching functionality.
package exchangerate

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/aristath/sentinel/internal/clientdata"
	"github.com/rs/zerolog"
)

// Client for exchangerate-api.com
type Client struct {
	baseURL   string
	client    *http.Client
	log       zerolog.Logger
	cacheRepo *clientdata.Repository
}

// NewClient creates a new exchangerate-api.com client
// cacheRepo is optional - if nil, caching is disabled
func NewClient(cacheRepo *clientdata.Repository, log zerolog.Logger) *Client {
	return &Client{
		baseURL:   "https://api.exchangerate-api.com/v4/latest",
		client:    &http.Client{Timeout: 10 * time.Second},
		log:       log.With().Str("client", "exchangerate-api").Logger(),
		cacheRepo: cacheRepo,
	}
}

// cachedExchangeRate is the structure stored in the cache
type cachedExchangeRate struct {
	Rate float64 `json:"rate"`
}

// GetRate fetches exchange rate with cache.
// If the API fails, returns stale cached data if available (stale data > no data).
func (c *Client) GetRate(fromCurrency, toCurrency string) (float64, error) {
	if fromCurrency == toCurrency {
		return 1.0, nil
	}

	cacheKey := fromCurrency + ":" + toCurrency

	// Check persistent cache for fresh data
	if c.cacheRepo != nil {
		data, err := c.cacheRepo.GetIfFresh("exchangerate", cacheKey)
		if err == nil && data != nil {
			var cached cachedExchangeRate
			if err := json.Unmarshal(data, &cached); err == nil {
				c.log.Debug().
					Str("from", fromCurrency).
					Str("to", toCurrency).
					Float64("rate", cached.Rate).
					Msg("Cache hit")
				return cached.Rate, nil
			}
		}
	}

	// Fetch from API
	url := fmt.Sprintf("%s/%s", c.baseURL, fromCurrency)
	c.log.Debug().Str("url", url).Msg("Fetching rates")

	resp, err := c.client.Get(url)
	if err != nil {
		// API failed - try to get stale cached data as fallback
		if staleRate, ok := c.getStaleFromCache(cacheKey); ok {
			c.log.Warn().
				Err(err).
				Str("from", fromCurrency).
				Str("to", toCurrency).
				Float64("rate", staleRate).
				Msg("API failed, using stale cached rate")
			return staleRate, nil
		}
		return 0, fmt.Errorf("API request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		// API returned error - try stale cache
		if staleRate, ok := c.getStaleFromCache(cacheKey); ok {
			c.log.Warn().
				Int("status", resp.StatusCode).
				Str("from", fromCurrency).
				Str("to", toCurrency).
				Float64("rate", staleRate).
				Msg("API error, using stale cached rate")
			return staleRate, nil
		}
		return 0, fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	var result struct {
		Rates map[string]float64 `json:"rates"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		// Parse error - try stale cache
		if staleRate, ok := c.getStaleFromCache(cacheKey); ok {
			c.log.Warn().
				Err(err).
				Str("from", fromCurrency).
				Str("to", toCurrency).
				Float64("rate", staleRate).
				Msg("Failed to parse API response, using stale cached rate")
			return staleRate, nil
		}
		return 0, fmt.Errorf("failed to parse response: %w", err)
	}

	rate, exists := result.Rates[toCurrency]
	if !exists {
		// Rate not in response - try stale cache
		if staleRate, ok := c.getStaleFromCache(cacheKey); ok {
			c.log.Warn().
				Str("from", fromCurrency).
				Str("to", toCurrency).
				Float64("rate", staleRate).
				Msg("Rate not in API response, using stale cached rate")
			return staleRate, nil
		}
		return 0, fmt.Errorf("rate not found for %s->%s", fromCurrency, toCurrency)
	}

	// Cache persistently
	if c.cacheRepo != nil {
		cached := cachedExchangeRate{Rate: rate}
		if err := c.cacheRepo.Store("exchangerate", cacheKey, cached, clientdata.TTLExchangeRate); err != nil {
			c.log.Warn().Err(err).Str("pair", cacheKey).Msg("Failed to cache exchange rate")
		}
	}

	c.log.Info().
		Str("from", fromCurrency).
		Str("to", toCurrency).
		Float64("rate", rate).
		Msg("Fetched rate")

	return rate, nil
}

// getStaleFromCache retrieves cached rate even if expired.
// Use this as a fallback when API calls fail - stale data is better than no data.
func (c *Client) getStaleFromCache(cacheKey string) (float64, bool) {
	if c.cacheRepo == nil {
		return 0, false
	}

	data, err := c.cacheRepo.Get("exchangerate", cacheKey)
	if err != nil || data == nil {
		return 0, false
	}

	var cached cachedExchangeRate
	if err := json.Unmarshal(data, &cached); err != nil {
		return 0, false
	}

	return cached.Rate, true
}
