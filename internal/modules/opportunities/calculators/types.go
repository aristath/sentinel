package calculators

import (
	appdomain "github.com/aristath/sentinel/internal/domain"
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
	GetByTags(tags []string) ([]appdomain.Security, error)
}
