package opportunities

import "github.com/aristath/sentinel/internal/domain"

// SecurityRepository defines the interface for security data access needed by the opportunities module.
// This follows the Dependency Inversion Principle - the module defines what it needs,
// and the infrastructure layer (universe.SecurityRepository) implements it.
type SecurityRepository interface {
	// GetAllActive returns all active securities in the universe.
	GetAllActive() ([]domain.Security, error)

	// GetByTags returns securities that have any of the specified tags.
	GetByTags(tags []string) ([]domain.Security, error)

	// GetPositionsByTags returns securities that have any of the specified tags
	// and are currently held in the portfolio (filtered by positionSymbols).
	GetPositionsByTags(positionSymbols []string, tags []string) ([]domain.Security, error)

	// GetTagsForSecurity returns all tags associated with a specific security symbol.
	GetTagsForSecurity(symbol string) ([]string, error)
}
