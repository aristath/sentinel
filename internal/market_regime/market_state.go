package market_regime

import (
	"sort"
	"sync"
	"time"

	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// MarketState represents the current state of trading markets
type MarketState string

const (
	// MarketStatePreMarket - 30 min before dominant markets open
	MarketStatePreMarket MarketState = "pre_market"
	// MarketStateDominantOpen - At least one dominant market is open
	MarketStateDominantOpen MarketState = "dominant_open"
	// MarketStateSecondaryOpen - Only secondary markets are open
	MarketStateSecondaryOpen MarketState = "secondary_open"
	// MarketStateClosed - All markets are closed
	MarketStateClosed MarketState = "all_closed"
)

// ExchangeCount holds exchange name and security count
type ExchangeCount struct {
	Exchange string
	Count    int
}

// MarketStateDetector detects current market state based on securities universe
type MarketStateDetector struct {
	securityRepo       *universe.SecurityRepository
	marketHoursService *market_hours.MarketHoursService
	log                zerolog.Logger

	// Cache (protected by mu)
	mu                 sync.RWMutex
	lastExchangeUpdate time.Time
	dominantExchanges  []string
	secondaryExchanges []string
}

// NewMarketStateDetector creates a new market state detector
func NewMarketStateDetector(
	securityRepo *universe.SecurityRepository,
	marketHoursService *market_hours.MarketHoursService,
	log zerolog.Logger,
) *MarketStateDetector {
	return &MarketStateDetector{
		securityRepo:       securityRepo,
		marketHoursService: marketHoursService,
		log:                log.With().Str("component", "market_state_detector").Logger(),
	}
}

// GetMarketState returns the current market state
func (d *MarketStateDetector) GetMarketState(now time.Time) MarketState {
	// Check if cache needs update (read lock)
	d.mu.RLock()
	needsUpdate := d.lastExchangeUpdate.IsZero() || time.Since(d.lastExchangeUpdate) > time.Hour
	d.mu.RUnlock()

	// Update exchange counts if stale (write lock acquired inside updateExchangeCounts)
	if needsUpdate {
		if err := d.updateExchangeCounts(); err != nil {
			d.log.Error().Err(err).Msg("Failed to update exchange counts, using cached data")
		}
	}

	// Get dominant/secondary exchanges (read lock)
	d.mu.RLock()
	dominantCount := len(d.dominantExchanges)
	dominant := make([]string, len(d.dominantExchanges))
	copy(dominant, d.dominantExchanges)
	secondary := make([]string, len(d.secondaryExchanges))
	copy(secondary, d.secondaryExchanges)
	d.mu.RUnlock()

	// If we don't have any exchanges yet, return safe default
	if dominantCount == 0 {
		d.log.Warn().Msg("No exchanges detected, returning all_closed")
		return MarketStateClosed
	}

	// Check pre-market (30 min before dominant markets open)
	preMarketBuffer := 30 * time.Minute
	for _, exchange := range dominant {
		if d.isPreMarket(exchange, now, preMarketBuffer) {
			d.log.Debug().
				Str("exchange", exchange).
				Str("state", string(MarketStatePreMarket)).
				Msg("Market state detected")
			return MarketStatePreMarket
		}
	}

	// Check if any dominant market is open
	for _, exchange := range dominant {
		if d.marketHoursService.IsMarketOpen(exchange, now) {
			d.log.Debug().
				Str("exchange", exchange).
				Str("state", string(MarketStateDominantOpen)).
				Msg("Market state detected")
			return MarketStateDominantOpen
		}
	}

	// Check if any secondary market is open
	for _, exchange := range secondary {
		if d.marketHoursService.IsMarketOpen(exchange, now) {
			d.log.Debug().
				Str("exchange", exchange).
				Str("state", string(MarketStateSecondaryOpen)).
				Msg("Market state detected")
			return MarketStateSecondaryOpen
		}
	}

	// All markets closed
	d.log.Debug().
		Str("state", string(MarketStateClosed)).
		Msg("Market state detected")
	return MarketStateClosed
}

// GetSyncInterval returns the appropriate sync interval for current market state
func (d *MarketStateDetector) GetSyncInterval(now time.Time) time.Duration {
	state := d.GetMarketState(now)

	switch state {
	case MarketStatePreMarket:
		return 5 * time.Minute // Prepare for market open
	case MarketStateDominantOpen:
		return 5 * time.Minute // Main trading hours - responsive
	case MarketStateSecondaryOpen:
		return 10 * time.Minute // Secondary trading hours - moderate
	case MarketStateClosed:
		return 0 // Skip - don't run when markets are closed
	default:
		return 0 // Safe default
	}
}

// updateExchangeCounts updates the list of dominant and secondary exchanges
func (d *MarketStateDetector) updateExchangeCounts() error {
	// Get all active securities (no lock needed - repo is thread-safe)
	securities, err := d.securityRepo.GetAllActive()
	if err != nil {
		return err
	}

	// Count securities per exchange
	exchangeCounts := make(map[string]int)
	for i := range securities {
		sec := &securities[i]
		// After migration 038: All securities in table are active
		if sec.FullExchangeName == "" {
			continue // Skip securities without exchange
		}
		exchangeCounts[sec.FullExchangeName]++
	}

	// Convert to slice and sort by count (descending)
	counts := make([]ExchangeCount, 0, len(exchangeCounts))
	for exchange, count := range exchangeCounts {
		counts = append(counts, ExchangeCount{
			Exchange: exchange,
			Count:    count,
		})
	}

	sort.Slice(counts, func(i, j int) bool {
		return counts[i].Count > counts[j].Count
	})

	// Extract top 2 as dominant, rest as secondary
	newDominant := make([]string, 0, 2)
	newSecondary := make([]string, 0, max(0, len(counts)-2))

	for i, ec := range counts {
		if i < 2 {
			newDominant = append(newDominant, ec.Exchange)
		} else {
			newSecondary = append(newSecondary, ec.Exchange)
		}
	}

	// Update cache with write lock
	d.mu.Lock()
	d.dominantExchanges = newDominant
	d.secondaryExchanges = newSecondary
	d.lastExchangeUpdate = time.Now()
	d.mu.Unlock()

	d.log.Info().
		Strs("dominant", newDominant).
		Strs("secondary", newSecondary).
		Msg("Exchange counts updated")

	return nil
}

// isPreMarket checks if we're within buffer time before market open
func (d *MarketStateDetector) isPreMarket(exchangeName string, now time.Time, buffer time.Duration) bool {
	// Get market status
	status, err := d.marketHoursService.GetMarketStatus(exchangeName, now)
	if err != nil {
		return false
	}

	// If market is already open, it's not pre-market
	if status.Open {
		return false
	}

	// Check if we have an opening time today or in the future
	if status.OpensAt == "" {
		return false
	}

	// Parse timezone from market status
	loc, err := time.LoadLocation(status.Timezone)
	if err != nil {
		d.log.Warn().
			Err(err).
			Str("exchange", exchangeName).
			Str("timezone", status.Timezone).
			Msg("Failed to load timezone, using UTC")
		loc = time.UTC
	}

	// Parse opening time with correct timezone
	var openTime time.Time
	if status.OpensDate != "" {
		// Opens on a different day
		openTimeStr := status.OpensDate + " " + status.OpensAt
		openTime, err = time.ParseInLocation("2006-01-02 15:04", openTimeStr, loc)
	} else {
		// Opens today - use market time, not system time
		marketNow := now.In(loc)
		openTimeStr := marketNow.Format("2006-01-02") + " " + status.OpensAt
		openTime, err = time.ParseInLocation("2006-01-02 15:04", openTimeStr, loc)
	}

	if err != nil {
		d.log.Debug().
			Err(err).
			Str("exchange", exchangeName).
			Str("opens_at", status.OpensAt).
			Str("timezone", status.Timezone).
			Msg("Failed to parse opening time")
		return false
	}

	// Check if we're within buffer time before open
	timeUntilOpen := openTime.Sub(now)
	isPreMarket := timeUntilOpen > 0 && timeUntilOpen <= buffer

	if isPreMarket {
		d.log.Debug().
			Str("exchange", exchangeName).
			Dur("time_until_open", timeUntilOpen).
			Msg("In pre-market period")
	}

	return isPreMarket
}

// GetDominantExchanges returns the list of dominant exchanges
func (d *MarketStateDetector) GetDominantExchanges() []string {
	d.mu.RLock()
	needsUpdate := d.lastExchangeUpdate.IsZero()
	d.mu.RUnlock()

	if needsUpdate {
		// Force update if never updated
		_ = d.updateExchangeCounts()
	}

	d.mu.RLock()
	result := make([]string, len(d.dominantExchanges))
	copy(result, d.dominantExchanges)
	d.mu.RUnlock()

	return result
}

// GetSecondaryExchanges returns the list of secondary exchanges
func (d *MarketStateDetector) GetSecondaryExchanges() []string {
	d.mu.RLock()
	needsUpdate := d.lastExchangeUpdate.IsZero()
	d.mu.RUnlock()

	if needsUpdate {
		// Force update if never updated
		_ = d.updateExchangeCounts()
	}

	d.mu.RLock()
	result := make([]string, len(d.secondaryExchanges))
	copy(result, d.secondaryExchanges)
	d.mu.RUnlock()

	return result
}
