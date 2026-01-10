package opportunities

import (
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
)

// securityRepositoryAdapter adapts universe.SecurityRepository to the opportunities.SecurityRepository interface.
// This follows Clean Architecture - opportunities module defines what it needs via interface,
// and the adapter bridges between infrastructure (universe) and application (opportunities) layers.
type securityRepositoryAdapter struct {
	universeRepo *universe.SecurityRepository
}

// NewSecurityRepositoryAdapter creates a new adapter wrapping universe.SecurityRepository.
func NewSecurityRepositoryAdapter(universeRepo *universe.SecurityRepository) SecurityRepository {
	return &securityRepositoryAdapter{
		universeRepo: universeRepo,
	}
}

// GetAllActive returns all active securities, converting from universe.Security to domain.Security.
func (a *securityRepositoryAdapter) GetAllActive() ([]domain.Security, error) {
	universeSecurities, err := a.universeRepo.GetAllActive()
	if err != nil {
		return nil, err
	}

	return convertUniverseToDomain(universeSecurities), nil
}

// GetByTags returns securities with specified tags, converting from universe.Security to domain.Security.
func (a *securityRepositoryAdapter) GetByTags(tags []string) ([]domain.Security, error) {
	universeSecurities, err := a.universeRepo.GetByTags(tags)
	if err != nil {
		return nil, err
	}

	return convertUniverseToDomain(universeSecurities), nil
}

// GetPositionsByTags returns securities with specified tags that are in the position list.
func (a *securityRepositoryAdapter) GetPositionsByTags(positionSymbols []string, tags []string) ([]domain.Security, error) {
	universeSecurities, err := a.universeRepo.GetPositionsByTags(positionSymbols, tags)
	if err != nil {
		return nil, err
	}

	return convertUniverseToDomain(universeSecurities), nil
}

// GetTagsForSecurity returns tags for a security symbol.
func (a *securityRepositoryAdapter) GetTagsForSecurity(symbol string) ([]string, error) {
	return a.universeRepo.GetTagsForSecurity(symbol)
}

// convertUniverseToDomain converts a slice of universe.Security to domain.Security.
// Maps only the fields needed by the opportunities module.
func convertUniverseToDomain(universeSecurities []universe.Security) []domain.Security {
	domainSecurities := make([]domain.Security, len(universeSecurities))
	for i, sec := range universeSecurities {
		domainSecurities[i] = domain.Security{
			Symbol:    sec.Symbol,
			Name:      sec.Name,
			ISIN:      sec.ISIN,
			Country:   sec.Country,
			Currency:  domain.Currency(sec.Currency),
			Active:    sec.Active,
			AllowSell: sec.AllowSell,
			AllowBuy:  sec.AllowBuy,
			MinLot:    sec.MinLot,
		}
	}
	return domainSecurities
}
