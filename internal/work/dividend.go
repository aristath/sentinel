package work

import (
	"context"
	"fmt"
)

// DividendDetectionServiceInterface defines the dividend detection service interface
type DividendDetectionServiceInterface interface {
	DetectUnreinvestedDividends() (any, error)
	HasPendingDividends() bool
}

// DividendAnalysisServiceInterface defines the dividend analysis service interface
type DividendAnalysisServiceInterface interface {
	AnalyzeDividends(dividends any) (any, error)
}

// DividendRecommendationServiceInterface defines the dividend recommendation service interface
type DividendRecommendationServiceInterface interface {
	CreateRecommendations(analysis any) (any, error)
}

// DividendExecutionServiceInterface defines the dividend execution service interface
type DividendExecutionServiceInterface interface {
	ExecuteTrades(recommendations any) error
}

// DividendCacheInterface defines the cache interface for dividend work
type DividendCacheInterface interface {
	Has(key string) bool
	Get(key string) any
	Set(key string, value any)
	Delete(key string)
}

// DividendDeps contains all dependencies for dividend work types
type DividendDeps struct {
	DetectionService      DividendDetectionServiceInterface
	AnalysisService       DividendAnalysisServiceInterface
	RecommendationService DividendRecommendationServiceInterface
	ExecutionService      DividendExecutionServiceInterface
	Cache                 DividendCacheInterface
}

// RegisterDividendWorkTypes registers all dividend work types with the registry
func RegisterDividendWorkTypes(registry *Registry, deps *DividendDeps) {
	// dividend:detect - Find unreinvested dividends
	registry.Register(&WorkType{
		ID:           "dividend:detect",
		Priority:     PriorityHigh,
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			if deps.DetectionService.HasPendingDividends() {
				return []string{""}
			}
			return nil
		},
		Execute: func(ctx context.Context, subject string) error {

			dividends, err := deps.DetectionService.DetectUnreinvestedDividends()
			if err != nil {
				return fmt.Errorf("failed to detect dividends: %w", err)
			}

			deps.Cache.Set("detected_dividends", dividends)
			return nil
		},
	})

	// dividend:analyze - Analyze dividend yields
	registry.Register(&WorkType{
		ID:           "dividend:analyze",
		DependsOn:    []string{"dividend:detect"},
		Priority:     PriorityHigh,
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			if deps.Cache.Has("detected_dividends") && !deps.Cache.Has("dividend_analysis") {
				return []string{""}
			}
			return nil
		},
		Execute: func(ctx context.Context, subject string) error {

			dividends := deps.Cache.Get("detected_dividends")
			if dividends == nil {
				return fmt.Errorf("no dividends to analyze")
			}

			analysis, err := deps.AnalysisService.AnalyzeDividends(dividends)
			if err != nil {
				return fmt.Errorf("failed to analyze dividends: %w", err)
			}

			deps.Cache.Set("dividend_analysis", analysis)
			return nil
		},
	})

	// dividend:recommend - Create dividend recommendations
	registry.Register(&WorkType{
		ID:           "dividend:recommend",
		DependsOn:    []string{"dividend:analyze"},
		Priority:     PriorityHigh,
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			if deps.Cache.Has("dividend_analysis") && !deps.Cache.Has("dividend_recommendations") {
				return []string{""}
			}
			return nil
		},
		Execute: func(ctx context.Context, subject string) error {

			analysis := deps.Cache.Get("dividend_analysis")
			if analysis == nil {
				return fmt.Errorf("no analysis for recommendations")
			}

			recommendations, err := deps.RecommendationService.CreateRecommendations(analysis)
			if err != nil {
				return fmt.Errorf("failed to create recommendations: %w", err)
			}

			deps.Cache.Set("dividend_recommendations", recommendations)
			return nil
		},
	})

	// dividend:execute - Execute dividend trades
	registry.Register(&WorkType{
		ID:           "dividend:execute",
		DependsOn:    []string{"dividend:recommend"},
		Priority:     PriorityHigh,
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			if deps.Cache.Has("dividend_recommendations") {
				return []string{""}
			}
			return nil
		},
		Execute: func(ctx context.Context, subject string) error {

			recommendations := deps.Cache.Get("dividend_recommendations")
			if recommendations == nil {
				return fmt.Errorf("no recommendations to execute")
			}

			err := deps.ExecutionService.ExecuteTrades(recommendations)
			if err != nil {
				return fmt.Errorf("failed to execute trades: %w", err)
			}

			// Clear dividend cache after execution
			deps.Cache.Delete("detected_dividends")
			deps.Cache.Delete("dividend_analysis")
			deps.Cache.Delete("dividend_recommendations")

			return nil
		},
	})
}
