package work

import (
	"context"
	"encoding/json"
	"fmt"
	"time"
)

// OptimizerServiceInterface defines the optimizer service interface
type OptimizerServiceInterface interface {
	CalculateWeights(ctx context.Context) (map[string]float64, error)
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
	Cache              *Cache // SQLite cache for JSON storage
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
		Interval:     5 * time.Minute, // Run every 5 minutes
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			expiresAt := deps.Cache.GetExpiresAt("optimizer_weights")
			if expiresAt > 0 && time.Now().Unix() < expiresAt {
				return nil // Still valid, skip work
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			// Report started phase
			if progress != nil {
				progress.ReportPhase("started", "Calculating optimizer weights")
			}

			weights, err := deps.OptimizerService.CalculateWeights(ctx)
			if err != nil {
				return fmt.Errorf("failed to calculate weights: %w", err)
			}

			// Report completed phase
			if progress != nil {
				progress.ReportPhase("completed", fmt.Sprintf("Calculated weights for %d securities", len(weights)))
			}

			// Marshal new weights to JSON for comparison
			newWeightsJSON, err := json.Marshal(weights)
			if err != nil {
				return fmt.Errorf("failed to marshal weights: %w", err)
			}

			// Get existing cached weights for comparison
			var existingWeights map[string]float64
			err = deps.Cache.GetJSON("optimizer_weights", &existingWeights)
			if err != nil {
				// Cache miss or expired - store new weights and delete dependent caches
				expiresAt := time.Now().Add(5 * time.Minute).Unix()
				if err := deps.Cache.SetJSON("optimizer_weights", weights, expiresAt); err != nil {
					return fmt.Errorf("failed to store weights: %w", err)
				}
				// Delete dependent caches
				_ = deps.Cache.Delete("opportunity-context")
				_ = deps.Cache.Delete("sequences")
				_ = deps.Cache.Delete("best-sequence")
			} else {
				// Compare weights
				existingWeightsJSON, err := json.Marshal(existingWeights)
				if err != nil || string(newWeightsJSON) != string(existingWeightsJSON) {
					// Weights changed - update and delete dependent caches
					expiresAt := time.Now().Add(5 * time.Minute).Unix()
					if err := deps.Cache.SetJSON("optimizer_weights", weights, expiresAt); err != nil {
						return fmt.Errorf("failed to store weights: %w", err)
					}
					// Delete dependent caches
					_ = deps.Cache.Delete("opportunity-context")
					_ = deps.Cache.Delete("sequences")
					_ = deps.Cache.Delete("best-sequence")
				} else {
					// Weights unchanged - extend expiration of all caches by 5 minutes
					extension := 5 * time.Minute
					_ = deps.Cache.ExtendExpiration("optimizer_weights", extension)
					_ = deps.Cache.ExtendExpiration("opportunity-context", extension)
					_ = deps.Cache.ExtendExpiration("sequences", extension)
					_ = deps.Cache.ExtendExpiration("best-sequence", extension)
				}
			}

			return nil
		},
	})

	// planner:context - Build opportunity context
	registry.Register(&WorkType{
		ID:           "planner:context",
		DependsOn:    []string{"planner:weights"},
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			expiresAt := deps.Cache.GetExpiresAt("opportunity-context")
			if expiresAt > 0 && time.Now().Unix() < expiresAt {
				return nil // Still valid, skip work
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			// Build context (adapter gets weights from cache automatically)
			opportunityContext, err := deps.ContextBuilder.Build()
			if err != nil {
				return fmt.Errorf("failed to build opportunity context: %w", err)
			}

			expiresAt := time.Now().Add(5 * time.Minute).Unix()
			if err := deps.Cache.SetJSON("opportunity-context", opportunityContext, expiresAt); err != nil {
				return fmt.Errorf("failed to store opportunity context: %w", err)
			}
			return nil
		},
	})

	// planner:plan - Create trade plan
	registry.Register(&WorkType{
		ID:           "planner:plan",
		DependsOn:    []string{"planner:context"},
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			expiresAt := deps.Cache.GetExpiresAt("best-sequence")
			if expiresAt > 0 && time.Now().Unix() < expiresAt {
				return nil // Still valid, skip work
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {
			// Create plan (adapter gets context from cache automatically)
			// This will cache sequences and best-sequence internally via CreatePlanWithCache
			_, err := deps.PlannerService.CreatePlan(nil)
			if err != nil {
				return fmt.Errorf("failed to create trade plan: %w", err)
			}

			// Plan is already cached as "best-sequence" by CreatePlanWithCache, no need to cache again
			return nil
		},
	})

	// planner:recommendations - Store recommendations and emit event
	registry.Register(&WorkType{
		ID:           "planner:recommendations",
		DependsOn:    []string{"planner:plan"},
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			// This runs whenever there's a best-sequence to store
			expiresAt := deps.Cache.GetExpiresAt("best-sequence")
			if expiresAt == 0 || time.Now().Unix() >= expiresAt {
				return nil // No valid plan to store
			}
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			// Get plan from cache - unmarshal as interface{} (JSON unmarshals to map[string]interface{})
			// The adapter receives interface{} and will unmarshal to *HolisticPlan
			var plan interface{}
			if err := deps.Cache.GetJSON("best-sequence", &plan); err != nil {
				return fmt.Errorf("best-sequence not found in cache: %w", err)
			}

			// Store recommendations - adapter handles conversion from JSON map to *HolisticPlan
			err := deps.RecommendationRepo.Store(plan)
			if err != nil {
				return fmt.Errorf("failed to store recommendations: %w", err)
			}

			// Emit event to trigger trading
			deps.EventManager.Emit("RecommendationsReady", nil)

			// Clear cache after successful storage
			_ = deps.Cache.Delete("best-sequence")

			return nil
		},
	})
}
