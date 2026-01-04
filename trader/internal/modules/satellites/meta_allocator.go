package satellites

import (
	"fmt"
	"math"
	"time"

	"github.com/rs/zerolog"

	"github.com/aristath/arduino-trader/internal/modules/trading"
)

// AllocationRecommendation represents recommended allocation adjustment for a satellite
type AllocationRecommendation struct {
	BucketID             string  `json:"bucket_id"`
	CurrentAllocationPct float64 `json:"current_allocation_pct"`
	TargetAllocationPct  float64 `json:"target_allocation_pct"`
	NewAllocationPct     float64 `json:"new_allocation_pct"` // After dampening
	AdjustmentPct        float64 `json:"adjustment_pct"`     // Change amount
	PerformanceScore     float64 `json:"performance_score"`
	Reason               string  `json:"reason"`
}

// ReallocationResult represents result of meta-allocator rebalancing
type ReallocationResult struct {
	TotalSatelliteBudget float64                     `json:"total_satellite_budget"` // Total % allocated to satellites
	Recommendations      []*AllocationRecommendation `json:"recommendations"`
	DampeningFactor      float64                     `json:"dampening_factor"`
	EvaluationPeriodDays int                         `json:"evaluation_period_days"`
	SatellitesEvaluated  int                         `json:"satellites_evaluated"`
	SatellitesImproved   int                         `json:"satellites_improved"`
	SatellitesReduced    int                         `json:"satellites_reduced"`
	Timestamp            string                      `json:"timestamp"`
}

// MetaAllocator manages performance-based allocation rebalancing.
//
// Implements performance-based allocation rebalancing:
// - Evaluates satellites quarterly (every 3 months)
// - Calculates performance scores (Sharpe, Sortino, win rate, profit factor)
// - Reallocates budget based on relative performance
// - Applies dampening to avoid excessive churn
// - Enforces min/max allocation constraints
//
// Faithful translation from Python: app/modules/satellites/services/meta_allocator.py
type MetaAllocator struct {
	bucketService  *BucketService
	balanceService *BalanceService
	balanceRepo    *BalanceRepository
	tradeRepo      *trading.TradeRepository
	log            zerolog.Logger
}

// NewMetaAllocator creates a new meta allocator
func NewMetaAllocator(
	bucketService *BucketService,
	balanceService *BalanceService,
	balanceRepo *BalanceRepository,
	tradeRepo *trading.TradeRepository,
	log zerolog.Logger,
) *MetaAllocator {
	return &MetaAllocator{
		bucketService:  bucketService,
		balanceService: balanceService,
		balanceRepo:    balanceRepo,
		tradeRepo:      tradeRepo,
		log:            log,
	}
}

// EvaluateAndReallocate evaluates satellite performance and recommends allocation changes.
//
// Args:
//
//	evaluationMonths: Months of history to evaluate (default 3 for quarterly)
//	dampeningFactor: How much to move toward target (0.5 = 50% of the way)
//	applyChanges: Whether to actually apply the changes (default False for dry-run)
//
// Returns:
//
//	ReallocationResult with recommendations
func (m *MetaAllocator) EvaluateAndReallocate(
	evaluationMonths int,
	dampeningFactor float64,
	applyChanges bool,
) (*ReallocationResult, error) {
	evaluationDays := evaluationMonths * 30

	// Get all satellites (excluding core)
	allBuckets, err := m.bucketService.GetAllBuckets()
	if err != nil {
		return nil, fmt.Errorf("failed to get buckets: %w", err)
	}

	var satellites []*Bucket
	for _, b := range allBuckets {
		if b.ID != "core" {
			satellites = append(satellites, b)
		}
	}

	if len(satellites) == 0 {
		m.log.Info().Msg("No satellites to evaluate")
		return &ReallocationResult{
			TotalSatelliteBudget: 0.0,
			Recommendations:      []*AllocationRecommendation{},
			DampeningFactor:      dampeningFactor,
			EvaluationPeriodDays: evaluationDays,
			SatellitesEvaluated:  0,
			SatellitesImproved:   0,
			SatellitesReduced:    0,
			Timestamp:            time.Now().Format(time.RFC3339),
		}, nil
	}

	// Get current satellite budget from settings
	settings, err := m.balanceRepo.GetAllAllocationSettings()
	if err != nil {
		return nil, fmt.Errorf("failed to get settings: %w", err)
	}

	satelliteBudgetPct := 0.20 // Default 20%
	if val, ok := settings["satellite_budget_pct"]; ok {
		satelliteBudgetPct = val
	}

	// Calculate performance metrics for each satellite
	performanceScores := make(map[string]float64)

	for _, satellite := range satellites {
		// Load satellite-specific settings (with default fallback)
		settings, err := m.bucketService.GetSettings(satellite.ID)
		if err != nil {
			m.log.Warn().
				Err(err).
				Str("bucket_id", satellite.ID).
				Msg("Failed to load settings, using defaults")
			// Use default settings if load fails
			settings = NewSatelliteSettings(satellite.ID)
		}

		// Calculate performance metrics from closed trades
		metrics, err := CalculateBucketPerformance(
			satellite.ID,
			settings, // Pass full settings struct with risk parameters
			m.balanceService,
			m.tradeRepo,
			m.log,
		)

		if err != nil {
			m.log.Error().
				Err(err).
				Str("bucket_id", satellite.ID).
				Msg("Error calculating performance")
			performanceScores[satellite.ID] = 0.0
		} else if metrics != nil {
			performanceScores[satellite.ID] = metrics.CompositeScore
			m.log.Info().
				Str("bucket_id", satellite.ID).
				Float64("score", metrics.CompositeScore).
				Float64("sharpe", metrics.SharpeRatio).
				Float64("sortino", metrics.SortinoRatio).
				Float64("win_rate", metrics.WinRate).
				Float64("profit_factor", metrics.ProfitFactor).
				Msg("Performance metrics calculated")
		} else {
			// Insufficient data - use neutral score
			performanceScores[satellite.ID] = 0.0
			m.log.Warn().
				Str("bucket_id", satellite.ID).
				Msg("Insufficient data for evaluation, using neutral score")
		}
	}

	// Calculate new allocations based on relative performance
	recommendations, err := m.calculateAllocations(
		satellites,
		performanceScores,
		satelliteBudgetPct,
		dampeningFactor,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate allocations: %w", err)
	}

	// Apply changes if requested
	improved := 0
	reduced := 0

	if applyChanges {
		for _, rec := range recommendations {
			if rec.AdjustmentPct > 0.01 { // Increased by >0.01%
				improved++
			} else if rec.AdjustmentPct < -0.01 { // Decreased by >0.01%
				reduced++
			}

			// Update bucket target allocation
			_, err := m.bucketService.UpdateAllocation(rec.BucketID, rec.NewAllocationPct)
			if err != nil {
				return nil, fmt.Errorf("failed to update allocation for %s: %w", rec.BucketID, err)
			}

			m.log.Info().
				Str("bucket_id", rec.BucketID).
				Float64("old_pct", rec.CurrentAllocationPct).
				Float64("new_pct", rec.NewAllocationPct).
				Float64("adjustment", rec.AdjustmentPct).
				Msg("Allocation updated")
		}
	}

	return &ReallocationResult{
		TotalSatelliteBudget: satelliteBudgetPct,
		Recommendations:      recommendations,
		DampeningFactor:      dampeningFactor,
		EvaluationPeriodDays: evaluationDays,
		SatellitesEvaluated:  len(satellites),
		SatellitesImproved:   improved,
		SatellitesReduced:    reduced,
		Timestamp:            time.Now().Format(time.RFC3339),
	}, nil
}

// calculateAllocations calculates new allocations based on performance scores.
//
// Algorithm:
// 1. Normalize scores to be non-negative (shift by min score)
// 2. Allocate proportionally to normalized scores
// 3. Apply min/max constraints
// 4. Apply dampening to smooth changes
//
// Args:
//
//	satellites: List of satellite buckets
//	performanceScores: Map of bucket_id -> score
//	totalBudgetPct: Total % to allocate to satellites
//	dampeningFactor: How much to move toward target (0-1)
//
// Returns:
//
//	List of AllocationRecommendation objects
func (m *MetaAllocator) calculateAllocations(
	satellites []*Bucket,
	performanceScores map[string]float64,
	totalBudgetPct float64,
	dampeningFactor float64,
) ([]*AllocationRecommendation, error) {
	// Get constraints from settings
	settings, err := m.balanceRepo.GetAllAllocationSettings()
	if err != nil {
		return nil, fmt.Errorf("failed to get settings: %w", err)
	}

	minSatellitePct := 0.03 // 3%
	if val, ok := settings["satellite_min_pct"]; ok {
		minSatellitePct = val
	}

	maxSatellitePct := 0.12 // 12%
	if val, ok := settings["satellite_max_pct"]; ok {
		maxSatellitePct = val
	}

	// Normalize scores to be non-negative
	minScore := math.Inf(1)
	for _, score := range performanceScores {
		if score < minScore {
			minScore = score
		}
	}

	normalizedScores := make(map[string]float64)
	totalScore := 0.0
	for satID, score := range performanceScores {
		normalized := score - minScore + 0.01 // Add small epsilon
		normalizedScores[satID] = normalized
		totalScore += normalized
	}

	var recommendations []*AllocationRecommendation

	for _, satellite := range satellites {
		currentPct := 0.0
		if satellite.TargetPct != nil {
			currentPct = *satellite.TargetPct
		}

		satID := satellite.ID
		score := normalizedScores[satID]

		// Calculate raw target allocation (proportional to score)
		rawTargetPct := 0.0
		if totalScore > 0 {
			rawTargetPct = (score / totalScore) * totalBudgetPct
		} else {
			// Equal allocation if no scores
			rawTargetPct = totalBudgetPct / float64(len(satellites))
		}

		// Apply constraints
		constrainedTargetPct := rawTargetPct
		if constrainedTargetPct < minSatellitePct {
			constrainedTargetPct = minSatellitePct
		}
		if constrainedTargetPct > maxSatellitePct {
			constrainedTargetPct = maxSatellitePct
		}

		// Apply dampening (move partway toward target)
		newPct := currentPct + (constrainedTargetPct-currentPct)*dampeningFactor

		adjustmentPct := newPct - currentPct

		// Determine reason
		reason := ""
		if math.Abs(adjustmentPct) < 0.005 { // <0.5% change
			reason = "No significant change"
		} else if adjustmentPct > 0 {
			perfScore := performanceScores[satID]
			if perfScore > 0 {
				reason = fmt.Sprintf("Increased due to strong performance (score: %.2f)", perfScore)
			} else {
				reason = "Increased to maintain minimum allocation"
			}
		} else {
			perfScore := performanceScores[satID]
			if perfScore < 0 {
				reason = fmt.Sprintf("Reduced due to weak performance (score: %.2f)", perfScore)
			} else {
				reason = "Reduced to enforce maximum allocation"
			}
		}

		recommendations = append(recommendations, &AllocationRecommendation{
			BucketID:             satID,
			CurrentAllocationPct: currentPct,
			TargetAllocationPct:  constrainedTargetPct,
			NewAllocationPct:     newPct,
			AdjustmentPct:        adjustmentPct,
			PerformanceScore:     performanceScores[satID],
			Reason:               reason,
		})
	}

	// Normalize to ensure total equals budget (due to constraints)
	totalNew := 0.0
	for _, rec := range recommendations {
		totalNew += rec.NewAllocationPct
	}

	if totalNew > 0 && math.Abs(totalNew-totalBudgetPct) > 0.001 {
		scaleFactor := totalBudgetPct / totalNew
		for _, rec := range recommendations {
			rec.NewAllocationPct *= scaleFactor
			rec.AdjustmentPct = rec.NewAllocationPct - rec.CurrentAllocationPct
		}
	}

	return recommendations, nil
}

// PreviewReallocation previews allocation changes without applying them.
//
// Args:
//
//	evaluationMonths: Months of history to evaluate
//
// Returns:
//
//	ReallocationResult with recommendations (not applied)
func (m *MetaAllocator) PreviewReallocation(evaluationMonths int) (*ReallocationResult, error) {
	return m.EvaluateAndReallocate(evaluationMonths, 0.5, false)
}

// ApplyReallocation evaluates and applies allocation changes.
//
// Args:
//
//	evaluationMonths: Months of history to evaluate
//	dampeningFactor: How much to move toward target
//
// Returns:
//
//	ReallocationResult with applied changes
func (m *MetaAllocator) ApplyReallocation(
	evaluationMonths int,
	dampeningFactor float64,
) (*ReallocationResult, error) {
	return m.EvaluateAndReallocate(evaluationMonths, dampeningFactor, true)
}
