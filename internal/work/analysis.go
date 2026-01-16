package work

import (
	"context"
	"fmt"
	"time"
)

// MarketRegimeServiceInterface defines the market regime analysis service interface
type MarketRegimeServiceInterface interface {
	AnalyzeMarketRegime() error
	NeedsAnalysis() bool
}

// AnalysisDeps contains all dependencies for analysis work types
type AnalysisDeps struct {
	MarketRegimeService MarketRegimeServiceInterface
}

// RegisterAnalysisWorkTypes registers all analysis work types with the registry
func RegisterAnalysisWorkTypes(registry *Registry, deps *AnalysisDeps) {
	// analysis:market-regime - Daily market regime analysis
	registry.Register(&WorkType{
		ID:           "analysis:market-regime",
		Priority:     PriorityMedium,
		MarketTiming: AllMarketsClosed,
		Interval:     24 * time.Hour,
		FindSubjects: func() []string {
			if deps.MarketRegimeService.NeedsAnalysis() {
				return []string{""}
			}
			return nil
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.MarketRegimeService.AnalyzeMarketRegime()
			if err != nil {
				return fmt.Errorf("failed to analyze market regime: %w", err)
			}

			return nil
		},
	})
}
