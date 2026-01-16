// Package calculators implements opportunity identification calculators for portfolio management.
// Each calculator identifies specific types of trading opportunities (profit taking, averaging down,
// rebalancing, etc.) based on current portfolio state and market conditions.
package calculators

import (
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/scoring/scorers"
	"github.com/aristath/sentinel/internal/modules/universe"
)

// TagFilter defines the interface for tag-based pre-filtering of opportunities.
// Implementations provide intelligent filtering to reduce candidate sets for performance.
type TagFilter interface {
	// GetOpportunityCandidates returns securities that match opportunity tags (buy candidates).
	GetOpportunityCandidates(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) ([]string, error)

	// GetSellCandidates returns securities that match sell-opportunity tags.
	GetSellCandidates(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) ([]string, error)

	// IsMarketVolatile determines if current market conditions are volatile.
	IsMarketVolatile(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) bool
}

// SecurityRepository defines the interface for security repository operations needed by calculators.
// After removing universe.Security: Uses universe.Security directly (single source of truth).
type SecurityRepository interface {
	GetTagsForSecurity(symbol string) ([]string, error)
	GetByTags(tags []string) ([]universe.Security, error)
}

// BuildConcentrationContext builds a ConcentrationContext from an OpportunityContext.
// This is used by calculators to perform concentration guardrail checks.
func BuildConcentrationContext(ctx *domain.OpportunityContext) *scorers.ConcentrationContext {
	if ctx == nil {
		return nil
	}

	// Build positions map from enriched positions (ISIN -> value)
	positions := make(map[string]float64)
	for _, pos := range ctx.EnrichedPositions {
		if pos.ISIN != "" {
			positions[pos.ISIN] = pos.MarketValueEUR
		}
	}

	return &scorers.ConcentrationContext{
		Positions:            positions,
		TotalValue:           ctx.TotalPortfolioValueEUR,
		GeographyAllocations: ctx.GeographyAllocations,
	}
}

// concentrationScorer is a package-level instance for concentration checks.
// This avoids creating new instances for each check while keeping the API simple.
var concentrationScorer = scorers.NewConcentrationScorer()

// defaultConcentrationThresholds caches the default thresholds for reuse.
var defaultConcentrationThresholds = scorers.DefaultConcentrationThresholds()

// CheckConcentrationGuardrail checks if a proposed buy would exceed concentration limits.
// Returns (passes, reason) - if passes is false, reason explains why.
func CheckConcentrationGuardrail(
	isin string,
	geography string,
	proposedValueEUR float64,
	ctx *domain.OpportunityContext,
) (bool, string) {
	concentrationCtx := BuildConcentrationContext(ctx)

	result := concentrationScorer.CheckConcentration(
		isin,
		geography,
		proposedValueEUR,
		concentrationCtx,
		defaultConcentrationThresholds,
	)

	return result.Passes, result.Reason
}

// GetMaxPositionWeight returns the maximum allowed position weight from concentration thresholds.
// This is used by sell calculators to identify over-concentrated positions for priority boosting.
func GetMaxPositionWeight() float64 {
	return defaultConcentrationThresholds.MaxPositionWeight
}
