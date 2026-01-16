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
	registry.Register(&WorkType{
		ID:           "security:sync",
		Priority:     PriorityMedium,
		MarketTiming: AfterMarketClose,
		Interval:     24 * time.Hour,
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
	registry.Register(&WorkType{
		ID:           "security:technical",
		DependsOn:    []string{"security:sync"},
		Priority:     PriorityMedium,
		MarketTiming: AfterMarketClose,
		Interval:     24 * time.Hour,
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
	registry.Register(&WorkType{
		ID:           "security:formula",
		DependsOn:    []string{"security:technical"},
		Priority:     PriorityLow,
		MarketTiming: AfterMarketClose,
		Interval:     30 * 24 * time.Hour, // Monthly
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
	registry.Register(&WorkType{
		ID:           "security:tags",
		DependsOn:    []string{"security:sync"},
		Priority:     PriorityLow,
		MarketTiming: AfterMarketClose,
		Interval:     7 * 24 * time.Hour, // Weekly
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
	registry.Register(&WorkType{
		ID:           "security:metadata",
		Priority:     PriorityLow,
		MarketTiming: AnyTime,
		Interval:     24 * time.Hour, // Daily
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
