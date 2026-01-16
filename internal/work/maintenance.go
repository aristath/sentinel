package work

import (
	"context"
	"fmt"
	"time"
)

// BackupServiceInterface defines the backup service interface
type BackupServiceInterface interface {
	RunDailyBackup() error
	BackedUpToday() bool
}

// R2BackupServiceInterface defines the R2 cloud backup service interface
type R2BackupServiceInterface interface {
	UploadBackup() error
	RotateBackups() error
}

// VacuumServiceInterface defines the database vacuum service interface
type VacuumServiceInterface interface {
	VacuumDatabases() error
}

// HealthCheckServiceInterface defines the health check service interface
type HealthCheckServiceInterface interface {
	RunHealthChecks() error
}

// CleanupServiceInterface defines the cleanup service interface
type CleanupServiceInterface interface {
	CleanupHistory() error
	CleanupCache() error
	CleanupRecommendations() error
	CleanupClientData() error
}

// MaintenanceDeps contains all dependencies for maintenance work types
type MaintenanceDeps struct {
	BackupService      BackupServiceInterface
	R2BackupService    R2BackupServiceInterface
	VacuumService      VacuumServiceInterface
	HealthCheckService HealthCheckServiceInterface
	CleanupService     CleanupServiceInterface
}

// RegisterMaintenanceWorkTypes registers all maintenance work types with the registry
func RegisterMaintenanceWorkTypes(registry *Registry, deps *MaintenanceDeps) {
	// maintenance:backup - Daily local backup
	//
	// Interval: 24 hours (hardcoded)
	// Rationale: Daily backups are industry standard for financial data.
	//            More frequent would waste disk space; less frequent risks data loss.
	//
	// Market timing: AllMarketsClosed
	// Rationale: Backup during off-hours minimizes impact on trading operations.
	//            Uses BackedUpToday() check to prevent duplicate backups if app restarts.
	registry.Register(&WorkType{
		ID:           "maintenance:backup",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour, // Hardcoded - daily backups are optimal
		FindSubjects: func() []string {
			if deps.BackupService.BackedUpToday() {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.BackupService.RunDailyBackup()
			if err != nil {
				return fmt.Errorf("failed to run daily backup: %w", err)
			}

			return nil
		},
	})

	// maintenance:r2-backup - Upload backup to R2 cloud storage
	//
	// Interval: 24 hours (hardcoded)
	// Rationale: Daily cloud backups align with local backups for disaster recovery.
	//
	// Market timing: AllMarketsClosed
	// Rationale: Cloud uploads during off-hours avoid bandwidth competition with trading.
	registry.Register(&WorkType{
		ID:           "maintenance:r2-backup",
		DependsOn:    []string{"maintenance:backup"},
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour, // Hardcoded - daily cloud backups are optimal
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.R2BackupService.UploadBackup()
			if err != nil {
				return fmt.Errorf("failed to upload R2 backup: %w", err)
			}

			return nil
		},
	})

	// maintenance:r2-rotation - Rotate old R2 backups
	//
	// Interval: 24 hours (hardcoded)
	// Rationale: Daily backup rotation manages storage costs while retaining history.
	//
	// Market timing: AllMarketsClosed
	// Rationale: Rotation after backup upload ensures consistent backup sets.
	registry.Register(&WorkType{
		ID:           "maintenance:r2-rotation",
		DependsOn:    []string{"maintenance:r2-backup"},
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour, // Hardcoded - daily rotation is optimal
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.R2BackupService.RotateBackups()
			if err != nil {
				return fmt.Errorf("failed to rotate R2 backups: %w", err)
			}

			return nil
		},
	})

	// maintenance:vacuum - Vacuum databases
	//
	// Interval: 24 hours (hardcoded)
	// Rationale: Daily database vacuum reclaims space and optimizes SQLite performance.
	//
	// Market timing: AllMarketsClosed
	// Rationale: Vacuum can lock tables briefly; run during off-hours for safety.
	registry.Register(&WorkType{
		ID:           "maintenance:vacuum",
		DependsOn:    []string{"maintenance:backup"},
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour, // Hardcoded - daily vacuum is optimal
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.VacuumService.VacuumDatabases()
			if err != nil {
				return fmt.Errorf("failed to vacuum databases: %w", err)
			}

			return nil
		},
	})

	// maintenance:health - Database health checks
	//
	// Interval: 24 hours (hardcoded)
	// Rationale: Daily health checks catch data integrity issues early.
	//
	// Market timing: AllMarketsClosed
	// Rationale: Health checks can be I/O intensive; run during off-hours.
	registry.Register(&WorkType{
		ID:           "maintenance:health",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour, // Hardcoded - daily health checks are optimal
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.HealthCheckService.RunHealthChecks()
			if err != nil {
				return fmt.Errorf("failed to run health checks: %w", err)
			}

			return nil
		},
	})

	// maintenance:cleanup:history - Clean old history data
	//
	// Interval: 24 hours (hardcoded)
	// Rationale: Daily history cleanup prevents database bloat from stale data.
	//
	// Market timing: AllMarketsClosed
	// Rationale: Cleanup operations during off-hours minimize impact on queries.
	registry.Register(&WorkType{
		ID:           "maintenance:cleanup:history",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour, // Hardcoded - daily cleanup is optimal
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.CleanupService.CleanupHistory()
			if err != nil {
				return fmt.Errorf("failed to cleanup history: %w", err)
			}

			return nil
		},
	})

	// maintenance:cleanup:cache - Clean expired cache
	//
	// Interval: 24 hours (hardcoded)
	// Rationale: Daily cache cleanup removes stale entries and frees memory.
	//
	// Market timing: AllMarketsClosed
	// Rationale: Cache cleanup during off-hours avoids cache misses during trading.
	registry.Register(&WorkType{
		ID:           "maintenance:cleanup:cache",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour, // Hardcoded - daily cleanup is optimal
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.CleanupService.CleanupCache()
			if err != nil {
				return fmt.Errorf("failed to cleanup cache: %w", err)
			}

			return nil
		},
	})

	// maintenance:cleanup:recommendations - GC old recommendations (runs hourly)
	//
	// Interval: 1 hour (hardcoded)
	// Rationale: Recommendations are ephemeral (expire after use). Hourly cleanup prevents
	//            recommendation table bloat while being lightweight enough to run frequently.
	//
	// Market timing: AnyTime
	// Rationale: Lightweight operation, can run during market hours without impact.
	registry.Register(&WorkType{
		ID:           "maintenance:cleanup:recommendations",
		Priority:     PriorityLow,
		MarketTiming: AnyTime,
		Interval:     1 * time.Hour, // Hardcoded - hourly GC is optimal
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.CleanupService.CleanupRecommendations()
			if err != nil {
				return fmt.Errorf("failed to cleanup recommendations: %w", err)
			}

			return nil
		},
	})

	// maintenance:cleanup:client-data - Clean expired client data cache
	//
	// Interval: 24 hours (hardcoded)
	// Rationale: Daily client data cleanup prevents stale price/rate data from accumulating.
	//
	// Market timing: AllMarketsClosed
	// Rationale: Cleanup during off-hours ensures fresh data ready for market open.
	registry.Register(&WorkType{
		ID:           "maintenance:cleanup:client-data",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour, // Hardcoded - daily cleanup is optimal
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.CleanupService.CleanupClientData()
			if err != nil {
				return fmt.Errorf("failed to cleanup client data: %w", err)
			}

			return nil
		},
	})
}
