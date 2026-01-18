// Package universe_monitor provides periodic monitoring of universe state changes
// to invalidate recommendations, sequences, and evaluations when portfolio state,
// cash balances, settings, or securities universe changes.
package universe_monitor

import (
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/planning"
	planningrepo "github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// UniverseMonitor monitors universe state and invalidates recommendations when state changes
type UniverseMonitor struct {
	securityRepo       *universe.SecurityRepository
	positionRepo       *portfolio.PositionRepository
	cashManager        domain.CashManager
	configRepo         planningrepo.ConfigRepositoryInterface
	recommendationRepo planning.RecommendationRepositoryInterface // Interface - can be DB or in-memory
	plannerRepo        planningrepo.PlannerRepositoryInterface    // Interface - can be DB or in-memory
	settingsRepo       *settings.Repository                       // For global settings query
	log                zerolog.Logger

	// In-memory state
	lastHash   string
	hashMutex  sync.RWMutex
	checkMutex sync.Mutex // Prevents concurrent execution of checkAndInvalidate
	ticker     *time.Ticker
	stopChan   chan struct{}
	stopOnce   sync.Once
	startOnce  sync.Once
}

// NewUniverseMonitor creates a new universe monitor service
func NewUniverseMonitor(
	securityRepo *universe.SecurityRepository,
	positionRepo *portfolio.PositionRepository,
	cashManager domain.CashManager,
	configRepo planningrepo.ConfigRepositoryInterface,
	recommendationRepo planning.RecommendationRepositoryInterface, // Interface - can be DB or in-memory
	plannerRepo planningrepo.PlannerRepositoryInterface, // Interface - can be DB or in-memory
	settingsRepo *settings.Repository,
	log zerolog.Logger,
) *UniverseMonitor {
	return &UniverseMonitor{
		securityRepo:       securityRepo,
		positionRepo:       positionRepo,
		cashManager:        cashManager,
		configRepo:         configRepo,
		recommendationRepo: recommendationRepo,
		plannerRepo:        plannerRepo,
		settingsRepo:       settingsRepo,
		log:                log.With().Str("component", "universe_monitor").Logger(),
	}
}

// Start begins the periodic monitoring (runs every minute)
// Safe to call multiple times - will only start once
func (m *UniverseMonitor) Start() {
	m.startOnce.Do(func() {
		m.ticker = time.NewTicker(1 * time.Minute)
		m.stopChan = make(chan struct{})

		m.log.Info().Msg("Universe monitor started (checking every minute)")

		// Run immediately on start
		m.checkAndInvalidate()

		// Start periodic checks
		go m.run()
	})
}

// Stop stops the periodic monitoring
// Safe to call multiple times - will only stop once
func (m *UniverseMonitor) Stop() {
	m.stopOnce.Do(func() {
		if m.ticker != nil {
			m.ticker.Stop()
		}
		if m.stopChan != nil {
			close(m.stopChan)
		}
		m.log.Info().Msg("Universe monitor stopped")
	})
}

// run executes the periodic check loop
func (m *UniverseMonitor) run() {
	for {
		select {
		case <-m.ticker.C:
			m.checkAndInvalidate()
		case <-m.stopChan:
			return
		}
	}
}

// checkAndInvalidate checks if universe state has changed and invalidates if needed
// Uses checkMutex to prevent concurrent execution (e.g., if previous check is still running)
func (m *UniverseMonitor) checkAndInvalidate() {
	m.checkMutex.Lock()
	defer m.checkMutex.Unlock()

	currentHash, err := m.calculateUniverseHash()
	if err != nil {
		m.log.Warn().Err(err).Msg("Failed to calculate universe hash, skipping check")
		return // Will retry next minute
	}

	m.hashMutex.RLock()
	lastHash := m.lastHash
	m.hashMutex.RUnlock()

	if lastHash != "" && currentHash != lastHash {
		m.log.Info().
			Str("old_hash", lastHash).
			Str("new_hash", currentHash).
			Msg("Universe state changed - invalidating recommendations")

		// Invalidate with retry
		m.invalidateAllWithRetry()

		// Update hash
		m.hashMutex.Lock()
		m.lastHash = currentHash
		m.hashMutex.Unlock()
	} else if lastHash == "" {
		// First run - just set hash, don't invalidate
		m.hashMutex.Lock()
		m.lastHash = currentHash
		m.hashMutex.Unlock()
		m.log.Debug().Str("hash", currentHash).Msg("Initial universe hash set")
	}
}

// calculateUniverseHash calculates a hash from current universe state
// Includes: all securities ISINs with quantities, cash balances, global settings, planner settings
func (m *UniverseMonitor) calculateUniverseHash() (string, error) {
	// 1. Get all securities in universe
	allSecurities, err := m.securityRepo.GetAll()
	if err != nil {
		return "", fmt.Errorf("failed to get all securities: %w", err)
	}

	// 2. Get all positions (ISIN -> quantity map)
	positions, err := m.positionRepo.GetAll()
	if err != nil {
		return "", fmt.Errorf("failed to get positions: %w", err)
	}

	positionMap := make(map[string]float64) // ISIN -> quantity
	for _, pos := range positions {
		if pos.ISIN != "" {
			positionMap[strings.ToUpper(pos.ISIN)] = pos.Quantity
		}
	}

	// 3. Build ISIN:quantity string (sorted by ISIN, include all securities even if qty=0)
	isinParts := make([]string, 0, len(allSecurities))
	for _, sec := range allSecurities {
		isin := strings.ToUpper(sec.ISIN)
		if isin == "" {
			continue // Skip securities without ISIN
		}
		quantity := positionMap[isin]
		// Round quantity to 2 decimal places for stability
		roundedQty := math.Round(quantity*100) / 100
		isinParts = append(isinParts, fmt.Sprintf("%s:%.2f", isin, roundedQty))
	}
	sort.Strings(isinParts)
	securitiesString := strings.Join(isinParts, ",")

	// 4. Get cash balances
	cashBalances, err := m.cashManager.GetAllCashBalances()
	if err != nil {
		return "", fmt.Errorf("failed to get cash balances: %w", err)
	}
	if cashBalances == nil {
		cashBalances = make(map[string]float64) // Defensive: handle nil map
	}

	// Build currency:amount string (sorted by currency, only include non-zero amounts)
	cashParts := make([]string, 0, len(cashBalances))
	for currency := range cashBalances {
		amount := cashBalances[currency]
		// Only include non-zero cash balances to avoid hash changes from rounding
		if amount != 0 {
			cashParts = append(cashParts, currency)
		}
	}
	sort.Strings(cashParts)
	cashStrings := make([]string, 0, len(cashParts))
	for _, currency := range cashParts {
		amount := cashBalances[currency]
		// Round to 2 decimal places for stability
		rounded := math.Round(amount*100) / 100
		cashStrings = append(cashStrings, fmt.Sprintf("%s:%.2f", strings.ToUpper(currency), rounded))
	}
	cashString := strings.Join(cashStrings, ",")

	// 5. Get global settings (query config.db.settings directly)
	globalSettings, err := m.getAllGlobalSettings()
	if err != nil {
		return "", fmt.Errorf("failed to get global settings: %w", err)
	}
	if globalSettings == nil {
		globalSettings = make(map[string]string) // Defensive: handle nil map
	}
	// Marshal settings (Go's json.Marshal sorts map keys since Go 1.12+ for deterministic output)
	globalSettingsJSON, err := json.Marshal(globalSettings)
	if err != nil {
		return "", fmt.Errorf("failed to marshal global settings: %w", err)
	}

	// 6. Get planner settings
	plannerConfig, err := m.configRepo.GetDefaultConfig()
	if err != nil {
		return "", fmt.Errorf("failed to get planner settings: %w", err)
	}
	if plannerConfig == nil {
		return "", fmt.Errorf("planner config is nil")
	}
	plannerSettingsJSON, err := json.Marshal(plannerConfig)
	if err != nil {
		return "", fmt.Errorf("failed to marshal planner settings: %w", err)
	}

	// 7. Combine all parts and hash
	combined := fmt.Sprintf("%s|%s|%s|%s", securitiesString, cashString, string(globalSettingsJSON), string(plannerSettingsJSON))

	// Generate MD5 hash
	hash := md5.Sum([]byte(combined))
	return hex.EncodeToString(hash[:]), nil
}

// getAllGlobalSettings retrieves all settings from settings repository
func (m *UniverseMonitor) getAllGlobalSettings() (map[string]string, error) {
	if m.settingsRepo == nil {
		return make(map[string]string), nil
	}

	return m.settingsRepo.GetAll()
}

// invalidateAllWithRetry invalidates all recommendations, sequences, and evaluations with retry logic
func (m *UniverseMonitor) invalidateAllWithRetry() {
	maxRetries := 3
	retryDelay := 10 * time.Second

	for attempt := 1; attempt <= maxRetries; attempt++ {
		err := m.invalidateAll()
		if err == nil {
			m.log.Info().Int("attempt", attempt).Msg("Successfully invalidated all recommendations and sequences")
			return // Success
		}

		if attempt < maxRetries {
			m.log.Warn().
				Int("attempt", attempt).
				Int("max_retries", maxRetries).
				Err(err).
				Msg("Invalidation failed, retrying...")
			time.Sleep(retryDelay)
		} else {
			m.log.Error().
				Int("attempt", attempt).
				Err(err).
				Msg("Invalidation failed after all retries")
		}
	}
}

// invalidateAll deletes all recommendations, sequences, and evaluations
func (m *UniverseMonitor) invalidateAll() error {
	// Delete all pending recommendations
	_, err := m.recommendationRepo.DismissAllPending()
	if err != nil {
		return fmt.Errorf("failed to dismiss recommendations: %w", err)
	}

	// Delete all sequences
	err = m.plannerRepo.DeleteAllSequences()
	if err != nil {
		return fmt.Errorf("failed to delete sequences: %w", err)
	}

	// Delete all evaluations
	err = m.plannerRepo.DeleteAllEvaluations()
	if err != nil {
		return fmt.Errorf("failed to delete evaluations: %w", err)
	}

	// Delete all best results
	err = m.plannerRepo.DeleteAllBestResults()
	if err != nil {
		return fmt.Errorf("failed to delete best results: %w", err)
	}

	return nil
}
