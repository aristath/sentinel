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
	registry.Register(&WorkType{
		ID:           "maintenance:backup",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour,
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
	registry.Register(&WorkType{
		ID:           "maintenance:r2-backup",
		DependsOn:    []string{"maintenance:backup"},
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour,
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
	registry.Register(&WorkType{
		ID:           "maintenance:r2-rotation",
		DependsOn:    []string{"maintenance:r2-backup"},
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour,
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
	registry.Register(&WorkType{
		ID:           "maintenance:vacuum",
		DependsOn:    []string{"maintenance:backup"},
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour,
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
	registry.Register(&WorkType{
		ID:           "maintenance:health",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour,
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
	registry.Register(&WorkType{
		ID:           "maintenance:cleanup:history",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour,
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
	registry.Register(&WorkType{
		ID:           "maintenance:cleanup:cache",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour,
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
	registry.Register(&WorkType{
		ID:           "maintenance:cleanup:recommendations",
		Priority:     PriorityLow,
		MarketTiming: AnyTime,
		Interval:     1 * time.Hour,
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
	registry.Register(&WorkType{
		ID:           "maintenance:cleanup:client-data",
		Priority:     PriorityLow,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour,
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
