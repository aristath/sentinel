package opportunities

import "github.com/aristath/sentinel/internal/modules/universe"

// SecurityRepository defines the interface for security data access needed by the opportunities module.
// After removing universe.Security: Uses universe.Security directly (single source of truth).
type SecurityRepository interface {
	// GetAllActive returns all active securities in the universe.
	GetAllActive() ([]universe.Security, error)

	// GetByTags returns securities that have any of the specified tags.
	GetByTags(tags []string) ([]universe.Security, error)

	// GetPositionsByTags returns securities that have any of the specified tags
	// and are currently held in the portfolio (filtered by positionSymbols).
	GetPositionsByTags(positionSymbols []string, tags []string) ([]universe.Security, error)

	// GetTagsForSecurity returns all tags associated with a specific security symbol.
	GetTagsForSecurity(symbol string) ([]string, error)
}
