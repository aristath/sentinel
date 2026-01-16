package work

import (
	"context"
	"fmt"
)

// PlannerCache defines the cache interface for planner work types
type PlannerCache interface {
	Has(key string) bool
	Get(key string) interface{}
	Set(key string, value interface{})
	Delete(key string)
	DeletePrefix(prefix string)
}

// OptimizerServiceInterface defines the optimizer service interface
type OptimizerServiceInterface interface {
	CalculateWeights() (map[string]float64, error)
}

// OpportunityContextBuilderInterface defines the context builder interface
type OpportunityContextBuilderInterface interface {
	Build() (interface{}, error)
}

// PlannerServiceInterface defines the planner service interface
type PlannerServiceInterface interface {
	CreatePlan(ctx interface{}) (interface{}, error)
}

// RecommendationRepoInterface defines the recommendation repository interface
type RecommendationRepoInterface interface {
	Store(recommendations interface{}) error
}

// EventManagerInterface defines the event manager interface
type EventManagerInterface interface {
	Emit(event string, data interface{})
}

// PlannerDeps contains all dependencies for planner work types
type PlannerDeps struct {
	Cache              PlannerCache
	OptimizerService   OptimizerServiceInterface
	ContextBuilder     OpportunityContextBuilderInterface
	PlannerService     PlannerServiceInterface
	RecommendationRepo RecommendationRepoInterface
	EventManager       EventManagerInterface
}

// RegisterPlannerWorkTypes registers all planner work types with the registry
func RegisterPlannerWorkTypes(registry *Registry, deps *PlannerDeps) {
	// planner:weights - Calculate optimizer weights
	registry.Register(&WorkType{
		ID:           "planner:weights",
		Priority:     PriorityCritical,
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			if deps.Cache.Has("optimizer_weights") {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			weights, err := deps.OptimizerService.CalculateWeights()
			if err != nil {
				return fmt.Errorf("failed to calculate weights: %w", err)
			}

			deps.Cache.Set("optimizer_weights", weights)
			return nil
		},
	})

	// planner:context - Build opportunity context
	registry.Register(&WorkType{
		ID:           "planner:context",
		DependsOn:    []string{"planner:weights"},
		Priority:     PriorityCritical,
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			if deps.Cache.Has("opportunity_context") {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			// Build context (adapter gets weights from cache automatically)
			opportunityContext, err := deps.ContextBuilder.Build()
			if err != nil {
				return fmt.Errorf("failed to build opportunity context: %w", err)
			}

			deps.Cache.Set("opportunity_context", opportunityContext)
			return nil
		},
	})

	// planner:plan - Create trade plan
	registry.Register(&WorkType{
		ID:           "planner:plan",
		DependsOn:    []string{"planner:context"},
		Priority:     PriorityCritical,
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			if deps.Cache.Has("trade_plan") {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			// Get context from cache
			opportunityContext := deps.Cache.Get("opportunity_context")
			if opportunityContext == nil {
				return fmt.Errorf("opportunity context not found in cache")
			}

			// Create plan
			plan, err := deps.PlannerService.CreatePlan(opportunityContext)
			if err != nil {
				return fmt.Errorf("failed to create trade plan: %w", err)
			}

			deps.Cache.Set("trade_plan", plan)
			return nil
		},
	})

	// planner:recommendations - Store recommendations and emit event
	registry.Register(&WorkType{
		ID:           "planner:recommendations",
		DependsOn:    []string{"planner:plan"},
		Priority:     PriorityCritical,
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			// This runs whenever there's a trade plan to store
			if !deps.Cache.Has("trade_plan") {
				return nil
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			// Get plan from cache
			plan := deps.Cache.Get("trade_plan")
			if plan == nil {
				return fmt.Errorf("trade plan not found in cache")
			}

			// Store recommendations
			err := deps.RecommendationRepo.Store(plan)
			if err != nil {
				return fmt.Errorf("failed to store recommendations: %w", err)
			}

			// Emit event to trigger trading
			deps.EventManager.Emit("RecommendationsReady", nil)

			// Clear cache after successful storage
			deps.Cache.Delete("trade_plan")

			return nil
		},
	})
}
