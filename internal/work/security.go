package work

import (
	"context"
	"fmt"
	"time"
)

// SecurityHistorySyncServiceInterface defines the security history sync service interface
type SecurityHistorySyncServiceInterface interface {
	SyncSecurityHistory(isin string) error
	GetStaleSecurities() []string
}

// TechnicalCalculationServiceInterface defines the technical calculation service interface
type TechnicalCalculationServiceInterface interface {
	CalculateTechnicals(isin string) error
	GetSecuritiesNeedingTechnicals() []string
}

// FormulaDiscoveryServiceInterface defines the formula discovery service interface
type FormulaDiscoveryServiceInterface interface {
	RunDiscovery(isin string) error
	GetSecuritiesNeedingDiscovery() []string
}

// TagUpdateServiceInterface defines the tag update service interface
type TagUpdateServiceInterface interface {
	UpdateTags(isin string) error
	GetSecuritiesNeedingTagUpdate() []string
}

// MetadataSyncServiceInterface defines the metadata sync service interface
type MetadataSyncServiceInterface interface {
	SyncMetadata(isin string) error
	GetAllActiveISINs() []string
}

// SecurityDeps contains all dependencies for security work types
type SecurityDeps struct {
	HistorySyncService  SecurityHistorySyncServiceInterface
	TechnicalService    TechnicalCalculationServiceInterface
	FormulaService      FormulaDiscoveryServiceInterface
	TagService          TagUpdateServiceInterface
	MetadataSyncService MetadataSyncServiceInterface
}

// RegisterSecurityWorkTypes registers all per-security work types with the registry
func RegisterSecurityWorkTypes(registry *Registry, deps *SecurityDeps) {
	// security:sync - Sync historical data for a security
	//
	// Interval: 24 hours (hardcoded)
	// Rationale: Historical data providers (exchanges, data vendors) update daily after market close.
	//            Syncing more frequently would fetch duplicate data; less frequently would miss updates.
	//
	// Market timing: AfterMarketClose
	// Rationale: Ensures complete daily data is available before fetching.
	registry.Register(&WorkType{
		ID:           "security:sync",
		Priority:     PriorityMedium,
		MarketTiming: AfterMarketClose,
		Interval:     24 * time.Hour, // Hardcoded - matches data provider refresh
		FindSubjects: func() []string {
			return deps.HistorySyncService.GetStaleSecurities()
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.HistorySyncService.SyncSecurityHistory(subject)
			if err != nil {
				return fmt.Errorf("failed to sync security %s: %w", subject, err)
			}

			return nil
		},
	})

	// security:technical - Calculate technical indicators for a security
	//
	// Interval: 24 hours (hardcoded)
	// Rationale: Technical indicators (RSI, MACD, moving averages) use daily price data.
	//            Daily calculation captures market trends without noise from intraday volatility.
	//
	// Market timing: AfterMarketClose
	// Rationale: Depends on security:sync completing with fresh daily data.
	registry.Register(&WorkType{
		ID:           "security:technical",
		DependsOn:    []string{"security:sync"},
		Priority:     PriorityMedium,
		MarketTiming: AfterMarketClose,
		Interval:     24 * time.Hour, // Hardcoded - daily technicals are optimal
		FindSubjects: func() []string {
			return deps.TechnicalService.GetSecuritiesNeedingTechnicals()
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.TechnicalService.CalculateTechnicals(subject)
			if err != nil {
				return fmt.Errorf("failed to calculate technicals for %s: %w", subject, err)
			}

			return nil
		},
	})

	// security:formula - Run formula discovery for a security
	//
	// Interval: 30 days (hardcoded)
	// Rationale: Symbolic regression is computationally expensive (genetic programming, hours per security).
	//            Monthly discovery balances capturing new patterns vs resource usage.
	//            More frequent would waste compute; less frequent would miss regime changes.
	//
	// Market timing: AfterMarketClose
	// Rationale: CPU-intensive operation should not run during active trading hours.
	registry.Register(&WorkType{
		ID:           "security:formula",
		DependsOn:    []string{"security:technical"},
		Priority:     PriorityLow,
		MarketTiming: AfterMarketClose,
		Interval:     30 * 24 * time.Hour, // Hardcoded - monthly for expensive computation
		FindSubjects: func() []string {
			return deps.FormulaService.GetSecuritiesNeedingDiscovery()
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.FormulaService.RunDiscovery(subject)
			if err != nil {
				return fmt.Errorf("failed to run formula discovery for %s: %w", subject, err)
			}

			return nil
		},
	})

	// security:tags - Update tags for a security
	//
	// Interval: 7 days (hardcoded)
	// Rationale: Tags (momentum, value, quality) are derived from medium-term trends.
	//            Weekly updates capture market changes without excessive tag churn.
	//
	// Market timing: AfterMarketClose
	// Rationale: Depends on security:sync for fresh data to calculate tags.
	registry.Register(&WorkType{
		ID:           "security:tags",
		DependsOn:    []string{"security:sync"},
		Priority:     PriorityLow,
		MarketTiming: AfterMarketClose,
		Interval:     7 * 24 * time.Hour, // Hardcoded - weekly tag updates are optimal
		FindSubjects: func() []string {
			return deps.TagService.GetSecuritiesNeedingTagUpdate()
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.TagService.UpdateTags(subject)
			if err != nil {
				return fmt.Errorf("failed to update tags for %s: %w", subject, err)
			}

			return nil
		},
	})

	// security:metadata - Sync Tradernet metadata for a security
	// Syncs geography (from CntryOfRisk), industry (raw sector code), min_lot (from quotes.x_lot)
	//
	// Interval: 24 hours (hardcoded)
	// Rationale: Metadata (geography, industry, lot size) changes infrequently but impacts allocation.
	//            Daily sync ensures current data without excessive API calls.
	//
	// Market timing: AnyTime
	// Rationale: Metadata sync is independent of market hours and can run anytime.
	registry.Register(&WorkType{
		ID:           "security:metadata",
		Priority:     PriorityLow,
		MarketTiming: AnyTime,
		Interval:     24 * time.Hour, // Hardcoded - daily metadata sync is optimal
		FindSubjects: func() []string {
			return deps.MetadataSyncService.GetAllActiveISINs()
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.MetadataSyncService.SyncMetadata(subject)
			if err != nil {
				return fmt.Errorf("failed to sync metadata for %s: %w", subject, err)
			}

			return nil
		},
	})
}
