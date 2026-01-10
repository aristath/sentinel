package calculators

import (
	"github.com/aristath/sentinel/internal/modules/planning/domain"
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
type SecurityRepository interface {
	GetTagsForSecurity(symbol string) ([]string, error)
}

// contains checks if a string slice contains a specific string.
func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}
