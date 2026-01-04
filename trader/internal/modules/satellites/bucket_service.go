package satellites

import (
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/services"
	"github.com/rs/zerolog"
)

// BucketService handles bucket lifecycle management
// Faithful translation from Python: app/modules/satellites/services/bucket_service.py
//
// Handles creation, updates, status transitions, and retirement
// of both core and satellite buckets.
type BucketService struct {
	bucketRepo      *BucketRepository
	balanceRepo     *BalanceRepository
	exchangeService *services.CurrencyExchangeService
	log             zerolog.Logger
}

// NewBucketService creates a new bucket service
func NewBucketService(
	bucketRepo *BucketRepository,
	balanceRepo *BalanceRepository,
	exchangeService *services.CurrencyExchangeService,
	log zerolog.Logger,
) *BucketService {
	return &BucketService{
		bucketRepo:      bucketRepo,
		balanceRepo:     balanceRepo,
		exchangeService: exchangeService,
		log:             log.With().Str("service", "bucket").Logger(),
	}
}

// --- Query Methods ---

// GetBucket gets a bucket by ID
func (s *BucketService) GetBucket(bucketID string) (*Bucket, error) {
	return s.bucketRepo.GetByID(bucketID)
}

// GetAllBuckets gets all buckets
func (s *BucketService) GetAllBuckets() ([]*Bucket, error) {
	return s.bucketRepo.GetAll()
}

// GetActiveBuckets gets all active buckets (not retired or paused)
func (s *BucketService) GetActiveBuckets() ([]*Bucket, error) {
	return s.bucketRepo.GetActive()
}

// GetSatellites gets all satellite buckets
func (s *BucketService) GetSatellites() ([]*Bucket, error) {
	return s.bucketRepo.GetSatellites()
}

// GetCore gets the core bucket
func (s *BucketService) GetCore() (*Bucket, error) {
	return s.bucketRepo.GetCore()
}

// GetSettings gets settings for a satellite
func (s *BucketService) GetSettings(satelliteID string) (*SatelliteSettings, error) {
	return s.bucketRepo.GetSettings(satelliteID)
}

// --- Lifecycle Methods ---

// CreateSatellite creates a new satellite bucket
//
// New satellites start in research mode by default, allowing
// paper trading until the user is ready to activate.
//
// Args:
//
//	satelliteID: Unique identifier for the satellite
//	name: Human-readable name
//	notes: Optional documentation/description
//	startInResearch: If true, start in research mode (default)
//
// Returns:
//
//	The created bucket
//
// Errors:
//
//	Returns error if satellite_id already exists
func (s *BucketService) CreateSatellite(
	satelliteID string,
	name string,
	notes *string,
	startInResearch bool,
) (*Bucket, error) {
	existing, err := s.bucketRepo.GetByID(satelliteID)
	if err != nil {
		return nil, fmt.Errorf("failed to check existing bucket: %w", err)
	}
	if existing != nil {
		return nil, fmt.Errorf("bucket with id '%s' already exists", satelliteID)
	}

	// Get allocation settings for defaults
	settings, err := s.balanceRepo.GetAllAllocationSettings()
	if err != nil {
		return nil, fmt.Errorf("failed to get allocation settings: %w", err)
	}

	minPct := 0.02
	if val, ok := settings["satellite_min_pct"]; ok {
		minPct = val
	}

	maxPct := 0.15
	if val, ok := settings["satellite_max_pct"]; ok {
		maxPct = val
	}

	var status BucketStatus
	if startInResearch {
		status = BucketStatusResearch
	} else {
		status = BucketStatusAccumulating
	}

	targetPct := 0.0 // Starts with no allocation
	bucket := &Bucket{
		ID:                   satelliteID,
		Name:                 name,
		Type:                 BucketTypeSatellite,
		Status:               status,
		Notes:                notes,
		TargetPct:            &targetPct,
		MinPct:               &minPct,
		MaxPct:               &maxPct,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}

	err = s.bucketRepo.Create(bucket)
	if err != nil {
		return nil, fmt.Errorf("failed to create satellite: %w", err)
	}

	statusStr := "research"
	if !startInResearch {
		statusStr = "accumulating"
	}
	s.log.Info().
		Str("satellite_id", satelliteID).
		Str("status", statusStr).
		Msg("Created satellite")

	return bucket, nil
}

// ActivateSatellite activates a satellite from research or accumulating mode
//
// The satellite must have reached minimum allocation threshold
// to become fully active.
func (s *BucketService) ActivateSatellite(satelliteID string) (*Bucket, error) {
	bucket, err := s.bucketRepo.GetByID(satelliteID)
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket: %w", err)
	}
	if bucket == nil {
		return nil, fmt.Errorf("satellite '%s' not found", satelliteID)
	}

	if bucket.Type != BucketTypeSatellite {
		return nil, fmt.Errorf("cannot activate non-satellite bucket")
	}

	if bucket.Status != BucketStatusResearch && bucket.Status != BucketStatusAccumulating {
		return nil, fmt.Errorf("cannot activate satellite in '%s' status", bucket.Status)
	}

	updated, err := s.bucketRepo.UpdateStatus(satelliteID, BucketStatusActive)
	if err != nil {
		return nil, fmt.Errorf("failed to update status: %w", err)
	}
	if updated == nil {
		return nil, fmt.Errorf("failed to update status for satellite '%s' - bucket disappeared during operation", satelliteID)
	}

	s.log.Info().Str("satellite_id", satelliteID).Msg("Activated satellite")
	return updated, nil
}

// PauseBucket pauses a bucket, stopping all trading
func (s *BucketService) PauseBucket(bucketID string) (*Bucket, error) {
	bucket, err := s.bucketRepo.GetByID(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket: %w", err)
	}
	if bucket == nil {
		return nil, fmt.Errorf("bucket '%s' not found", bucketID)
	}

	if bucket.Status == BucketStatusRetired {
		return nil, fmt.Errorf("cannot pause a retired bucket")
	}

	if bucket.Status == BucketStatusPaused {
		return nil, fmt.Errorf("bucket is already paused")
	}

	updated, err := s.bucketRepo.UpdateStatus(bucketID, BucketStatusPaused)
	if err != nil {
		return nil, fmt.Errorf("failed to pause bucket: %w", err)
	}
	if updated == nil {
		return nil, fmt.Errorf("failed to pause bucket '%s' - bucket disappeared during operation", bucketID)
	}

	s.log.Info().Str("bucket_id", bucketID).Msg("Paused bucket")
	return updated, nil
}

// ResumeBucket resumes a paused bucket
//
// Returns the bucket to its previous active state (active or accumulating
// depending on allocation).
func (s *BucketService) ResumeBucket(bucketID string) (*Bucket, error) {
	bucket, err := s.bucketRepo.GetByID(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket: %w", err)
	}
	if bucket == nil {
		return nil, fmt.Errorf("bucket '%s' not found", bucketID)
	}

	if bucket.Status != BucketStatusPaused {
		return nil, fmt.Errorf("bucket is not paused")
	}

	// Determine appropriate status based on allocation
	minPct := 0.02
	if bucket.MinPct != nil {
		minPct = *bucket.MinPct
	}

	targetPct := 0.0
	if bucket.TargetPct != nil {
		targetPct = *bucket.TargetPct
	}

	var newStatus BucketStatus
	if targetPct >= minPct {
		newStatus = BucketStatusActive
	} else {
		newStatus = BucketStatusAccumulating
	}

	updated, err := s.bucketRepo.UpdateStatus(bucketID, newStatus)
	if err != nil {
		return nil, fmt.Errorf("failed to resume bucket: %w", err)
	}
	if updated == nil {
		return nil, fmt.Errorf("failed to resume bucket '%s' - bucket disappeared during operation", bucketID)
	}

	s.log.Info().
		Str("bucket_id", bucketID).
		Str("new_status", string(newStatus)).
		Msg("Resumed bucket")

	return updated, nil
}

// HibernateBucket puts a bucket into hibernation
//
// Used when a satellite falls below minimum allocation or
// during safety circuit breaker triggers.
func (s *BucketService) HibernateBucket(bucketID string) (*Bucket, error) {
	bucket, err := s.bucketRepo.GetByID(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket: %w", err)
	}
	if bucket == nil {
		return nil, fmt.Errorf("bucket '%s' not found", bucketID)
	}

	if bucket.ID == "core" {
		return nil, fmt.Errorf("cannot hibernate core bucket")
	}

	if bucket.Status == BucketStatusRetired || bucket.Status == BucketStatusResearch {
		return nil, fmt.Errorf("cannot hibernate bucket in '%s' status", bucket.Status)
	}

	updated, err := s.bucketRepo.UpdateStatus(bucketID, BucketStatusHibernating)
	if err != nil {
		return nil, fmt.Errorf("failed to hibernate bucket: %w", err)
	}
	if updated == nil {
		return nil, fmt.Errorf("failed to hibernate bucket '%s' - bucket disappeared during operation", bucketID)
	}

	s.log.Info().Str("bucket_id", bucketID).Msg("Hibernated bucket")
	return updated, nil
}

// RetireSatellite retires a satellite permanently
//
// Prerequisites:
// - Satellite must be paused first
// - All positions should be reassigned or liquidated
// - Cash should be transferred to other buckets
//
// The satellite's data is preserved for historical reporting.
func (s *BucketService) RetireSatellite(satelliteID string) (*Bucket, error) {
	bucket, err := s.bucketRepo.GetByID(satelliteID)
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket: %w", err)
	}
	if bucket == nil {
		return nil, fmt.Errorf("satellite '%s' not found", satelliteID)
	}

	if bucket.Type != BucketTypeSatellite {
		return nil, fmt.Errorf("cannot retire non-satellite bucket")
	}

	if bucket.Status != BucketStatusPaused {
		return nil, fmt.Errorf("satellite must be paused before retirement. Please pause first and ensure all positions are handled")
	}

	// Check if satellite still has cash balances
	balances, err := s.balanceRepo.GetAllBalances(satelliteID)
	if err != nil {
		return nil, fmt.Errorf("failed to check balances: %w", err)
	}

	totalBalance := 0.0
	for _, b := range balances {
		totalBalance += b.Balance
	}

	if totalBalance > 0.01 { // Allow small rounding errors
		return nil, fmt.Errorf("satellite still has %.2f in cash. Please transfer funds before retiring", totalBalance)
	}

	updated, err := s.bucketRepo.UpdateStatus(satelliteID, BucketStatusRetired)
	if err != nil {
		return nil, fmt.Errorf("failed to retire satellite: %w", err)
	}
	if updated == nil {
		return nil, fmt.Errorf("failed to retire satellite '%s' - bucket disappeared during operation", satelliteID)
	}

	s.log.Info().Str("satellite_id", satelliteID).Msg("Retired satellite")
	return updated, nil
}

// --- Settings Methods ---

// SaveSettings saves or updates satellite settings
func (s *BucketService) SaveSettings(settings *SatelliteSettings) (*SatelliteSettings, error) {
	bucket, err := s.bucketRepo.GetByID(settings.SatelliteID)
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket: %w", err)
	}
	if bucket == nil {
		return nil, fmt.Errorf("satellite '%s' not found", settings.SatelliteID)
	}

	if bucket.Type != BucketTypeSatellite {
		return nil, fmt.Errorf("settings can only be saved for satellites")
	}

	if err := settings.Validate(); err != nil {
		return nil, err
	}

	if err := s.bucketRepo.SaveSettings(settings); err != nil {
		return nil, fmt.Errorf("failed to save settings: %w", err)
	}

	s.log.Info().Str("satellite_id", settings.SatelliteID).Msg("Saved settings")
	return settings, nil
}

// --- Circuit Breaker Methods ---

// RecordTradeResult records a trade result for circuit breaker tracking
func (s *BucketService) RecordTradeResult(bucketID string, isWin bool, tradePnL float64) (*Bucket, error) {
	bucket, err := s.bucketRepo.GetByID(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket: %w", err)
	}
	if bucket == nil {
		return nil, fmt.Errorf("bucket '%s' not found", bucketID)
	}

	if isWin {
		// Reset consecutive losses on any win
		if err := s.bucketRepo.ResetConsecutiveLosses(bucketID); err != nil {
			return nil, fmt.Errorf("failed to reset consecutive losses: %w", err)
		}
		s.log.Info().Str("bucket_id", bucketID).Msg("Reset consecutive losses after win")
	} else {
		// Increment consecutive losses
		newCount, err := s.bucketRepo.IncrementConsecutiveLosses(bucketID)
		if err != nil {
			return nil, fmt.Errorf("failed to increment consecutive losses: %w", err)
		}

		s.log.Info().
			Str("bucket_id", bucketID).
			Int("consecutive_losses", newCount).
			Int("max_consecutive_losses", bucket.MaxConsecutiveLosses).
			Msg("Incremented consecutive losses")

		// Check circuit breaker
		if newCount >= bucket.MaxConsecutiveLosses {
			lossStreakPausedAt := time.Now().Format(time.RFC3339)
			_, err := s.bucketRepo.Update(bucketID, map[string]interface{}{
				"status":                BucketStatusPaused,
				"loss_streak_paused_at": lossStreakPausedAt,
			})
			if err != nil {
				return nil, fmt.Errorf("failed to trigger circuit breaker: %w", err)
			}

			s.log.Warn().
				Str("bucket_id", bucketID).
				Int("consecutive_losses", newCount).
				Msg("Circuit breaker triggered - bucket paused")
		}
	}

	result, err := s.bucketRepo.GetByID(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to retrieve bucket after recording trade result: %w", err)
	}
	if result == nil {
		return nil, fmt.Errorf("failed to retrieve bucket '%s' after recording trade result - bucket disappeared during operation", bucketID)
	}

	return result, nil
}

// UpdateHighWaterMark updates high water mark if current value exceeds it
func (s *BucketService) UpdateHighWaterMark(bucketID string, currentValue float64) (*Bucket, error) {
	bucket, err := s.bucketRepo.GetByID(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket: %w", err)
	}
	if bucket == nil {
		return nil, fmt.Errorf("bucket '%s' not found", bucketID)
	}

	if currentValue > bucket.HighWaterMark {
		updated, err := s.bucketRepo.UpdateHighWaterMark(bucketID, currentValue)
		if err != nil {
			return nil, fmt.Errorf("failed to update high water mark: %w", err)
		}
		if updated == nil {
			return nil, fmt.Errorf("failed to update high water mark for '%s' - bucket disappeared during operation", bucketID)
		}

		s.log.Info().
			Str("bucket_id", bucketID).
			Float64("high_water_mark", currentValue).
			Msg("Updated high water mark")

		return updated, nil
	}

	return bucket, nil
}

// ResetConsecutiveLosses resets consecutive losses counter to zero
func (s *BucketService) ResetConsecutiveLosses(bucketID string) error {
	return s.bucketRepo.ResetConsecutiveLosses(bucketID)
}

// --- Update Methods ---

// UpdateBucket updates bucket fields
func (s *BucketService) UpdateBucket(bucketID string, updates map[string]interface{}) (*Bucket, error) {
	return s.bucketRepo.Update(bucketID, updates)
}

// UpdateAllocation updates bucket target allocation
func (s *BucketService) UpdateAllocation(bucketID string, targetPct float64) (*Bucket, error) {
	bucket, err := s.bucketRepo.GetByID(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket: %w", err)
	}
	if bucket == nil {
		return nil, fmt.Errorf("bucket '%s' not found", bucketID)
	}

	// Validate against min/max
	if bucket.MinPct != nil && targetPct < *bucket.MinPct {
		s.log.Warn().
			Str("bucket_id", bucketID).
			Float64("target_pct", targetPct).
			Float64("min_pct", *bucket.MinPct).
			Msgf("Target %.2f%% below min %.2f%%", targetPct*100, *bucket.MinPct*100)
	}

	if bucket.MaxPct != nil && targetPct > *bucket.MaxPct {
		return nil, fmt.Errorf("target %.2f%% exceeds max %.2f%%", targetPct*100, *bucket.MaxPct*100)
	}

	return s.bucketRepo.Update(bucketID, map[string]interface{}{
		"target_pct": targetPct,
	})
}

// CalculateBucketValue calculates total bucket value (positions + cash)
//
// Faithful translation from Python: app/modules/satellites/jobs/bucket_maintenance.py
//
// Calculates current bucket value by:
// 1. Summing market_value_eur for all positions in the bucket
// 2. Summing cash balances for the bucket (all currencies converted to EUR)
//
// Args:
//
//	bucketID: Bucket to calculate value for
//	positionRepo: Position repository for getting positions
//
// Returns:
//
//	Total bucket value in EUR
//
// Note: Uses CurrencyExchangeService to convert USD/GBP/HKD to EUR.
// If exchange service is unavailable, non-EUR currencies are skipped with warning.
func (s *BucketService) CalculateBucketValue(
	bucketID string,
	positionRepo *portfolio.PositionRepository,
) (float64, error) {
	// Get all positions and filter by bucket
	positions, err := positionRepo.GetAll()
	if err != nil {
		return 0, fmt.Errorf("failed to get positions: %w", err)
	}

	// Sum position values for this bucket
	positionsValue := 0.0
	for _, pos := range positions {
		if pos.BucketID == bucketID {
			positionsValue += pos.MarketValueEUR
		}
	}

	// Get cash balances for bucket
	balances, err := s.balanceRepo.GetAllBalances(bucketID)
	if err != nil {
		return 0, fmt.Errorf("failed to get balances: %w", err)
	}

	// Sum all cash balances, converting to EUR
	cashEUR := 0.0
	for _, balance := range balances {
		if balance.Balance <= 0 {
			continue
		}

		if balance.Currency == "EUR" {
			cashEUR += balance.Balance
		} else {
			// Convert to EUR using exchange service
			if s.exchangeService != nil {
				rate, err := s.exchangeService.GetRate(balance.Currency, "EUR")
				if err != nil {
					s.log.Warn().
						Err(err).
						Str("bucket_id", bucketID).
						Str("currency", balance.Currency).
						Float64("balance", balance.Balance).
						Msg("Failed to get exchange rate, skipping currency")
					continue
				}
				cashEUR += balance.Balance * rate
				s.log.Debug().
					Str("bucket_id", bucketID).
					Str("currency", balance.Currency).
					Float64("balance", balance.Balance).
					Float64("rate", rate).
					Float64("eur_value", balance.Balance*rate).
					Msg("Converted currency to EUR")
			} else {
				s.log.Warn().
					Str("bucket_id", bucketID).
					Str("currency", balance.Currency).
					Float64("balance", balance.Balance).
					Msg("Exchange service not available, skipping currency")
			}
		}
	}

	totalValue := positionsValue + cashEUR

	s.log.Debug().
		Str("bucket_id", bucketID).
		Float64("positions_value", positionsValue).
		Float64("cash_eur", cashEUR).
		Float64("total_value", totalValue).
		Msg("Calculated bucket value")

	return totalValue, nil
}
