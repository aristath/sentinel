package planning

import (
	"fmt"
	"sync"

	"github.com/aristath/arduino-trader/internal/modules/opportunities"
	"github.com/aristath/arduino-trader/internal/modules/planning/evaluation"
	"github.com/aristath/arduino-trader/internal/modules/planning/planner"
	"github.com/aristath/arduino-trader/internal/modules/planning/repository"
	"github.com/aristath/arduino-trader/internal/modules/sequences"
	"github.com/rs/zerolog"
)

// PlannerLoader manages per-bucket planner instances with caching.
type PlannerLoader struct {
	configRepo           *repository.ConfigRepository
	opportunitiesService *opportunities.Service
	sequencesService     *sequences.Service
	evaluationService    *evaluation.Service
	log                  zerolog.Logger

	mu    sync.RWMutex
	cache map[string]*planner.Planner // bucket_id -> planner instance
}

// NewPlannerLoader creates a new planner loader.
func NewPlannerLoader(
	configRepo *repository.ConfigRepository,
	opportunitiesService *opportunities.Service,
	sequencesService *sequences.Service,
	evaluationService *evaluation.Service,
	log zerolog.Logger,
) *PlannerLoader {
	return &PlannerLoader{
		configRepo:           configRepo,
		opportunitiesService: opportunitiesService,
		sequencesService:     sequencesService,
		evaluationService:    evaluationService,
		log:                  log.With().Str("component", "planner_loader").Logger(),
		cache:                make(map[string]*planner.Planner),
	}
}

// LoadPlannerForBucket loads or retrieves from cache a planner for a specific bucket.
func (l *PlannerLoader) LoadPlannerForBucket(bucketID string) (*planner.Planner, error) {
	// Fast path: check cache with read lock
	l.mu.RLock()
	cached, exists := l.cache[bucketID]
	l.mu.RUnlock()

	if exists {
		l.log.Debug().Str("bucket_id", bucketID).Msg("Returning cached planner")
		return cached, nil
	}

	// Slow path: acquire write lock and double-check
	l.mu.Lock()
	defer l.mu.Unlock()

	// Double-check: another goroutine may have created it while we waited for the lock
	if cached, exists := l.cache[bucketID]; exists {
		l.log.Debug().Str("bucket_id", bucketID).Msg("Returning planner created by another goroutine")
		return cached, nil
	}

	// Create new planner while holding write lock
	return l.createAndCachePlannerLocked(bucketID)
}

// ReloadPlannerForBucket forces a reload of the planner for a specific bucket.
// Used for hot-reload when configuration changes.
func (l *PlannerLoader) ReloadPlannerForBucket(bucketID string) (*planner.Planner, error) {
	l.log.Info().Str("bucket_id", bucketID).Msg("Reloading planner configuration")

	// Remove from cache first
	l.mu.Lock()
	delete(l.cache, bucketID)
	l.mu.Unlock()

	// Create fresh instance
	return l.createAndCachePlanner(bucketID)
}

// ClearCache clears all cached planner instances.
// Useful for system-wide configuration reloads.
func (l *PlannerLoader) ClearCache() {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.cache = make(map[string]*planner.Planner)
	l.log.Info().Msg("Cleared planner cache")
}

// createAndCachePlanner creates a new planner instance and stores it in cache.
// DEPRECATED: Use LoadPlannerForBucket instead, which handles locking correctly.
// This method is kept for ReloadPlannerForBucket which manages its own locking.
func (l *PlannerLoader) createAndCachePlanner(bucketID string) (*planner.Planner, error) {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.createAndCachePlannerLocked(bucketID)
}

// createAndCachePlannerLocked creates a new planner instance and stores it in cache.
// Caller must hold l.mu write lock.
func (l *PlannerLoader) createAndCachePlannerLocked(bucketID string) (*planner.Planner, error) {
	// Fetch configuration for this bucket
	cfg, err := l.configRepo.GetByBucket(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get config for bucket %s: %w", bucketID, err)
	}

	if cfg == nil {
		// No bucket-specific config, try to get default config
		cfg, err = l.configRepo.GetDefaultConfig()
		if err != nil {
			return nil, fmt.Errorf("failed to get default config for bucket %s: %w", bucketID, err)
		}
		if cfg == nil {
			return nil, fmt.Errorf("no configuration found for bucket %s (no bucket-specific or default config)", bucketID)
		}
		l.log.Warn().
			Str("bucket_id", bucketID).
			Msg("No bucket-specific config found, using default config")
	}

	// Create planner instance
	// Note: The planner doesn't need the config at construction time since it's
	// passed to CreatePlan. We're just creating the planner with the required services.
	p := planner.NewPlanner(
		l.opportunitiesService,
		l.sequencesService,
		l.evaluationService,
		l.log,
	)

	// Cache it (caller holds lock)
	l.cache[bucketID] = p

	l.log.Info().
		Str("bucket_id", bucketID).
		Str("config_name", cfg.Name).
		Msg("Created and cached new planner instance")

	return p, nil
}

// GetDefaultPlanner returns a planner using the default configuration.
// Used for main portfolio (non-satellite) planning.
func (l *PlannerLoader) GetDefaultPlanner() (*planner.Planner, error) {
	// Fast path: check cache with read lock
	l.mu.RLock()
	cached, exists := l.cache["__default__"]
	l.mu.RUnlock()

	if exists {
		return cached, nil
	}

	// Slow path: acquire write lock and double-check
	l.mu.Lock()
	defer l.mu.Unlock()

	// Double-check: another goroutine may have created it while we waited for the lock
	if cached, exists := l.cache["__default__"]; exists {
		return cached, nil
	}

	// Create default planner while holding write lock
	p := planner.NewPlanner(
		l.opportunitiesService,
		l.sequencesService,
		l.evaluationService,
		l.log,
	)

	l.cache["__default__"] = p
	l.log.Info().Msg("Created and cached default planner instance")

	return p, nil
}
