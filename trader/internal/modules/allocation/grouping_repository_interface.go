package allocation

// GroupingRepositoryInterface defines the contract for grouping repository operations
type GroupingRepositoryInterface interface {
	// GetCountryGroups returns all country groups as a map of group name -> country names
	GetCountryGroups() (map[string][]string, error)

	// GetIndustryGroups returns all industry groups as a map of group name -> industry names
	GetIndustryGroups() (map[string][]string, error)

	// SetCountryGroup sets countries for a country group (replaces existing)
	SetCountryGroup(groupName string, countryNames []string) error

	// SetIndustryGroup sets industries for an industry group (replaces existing)
	SetIndustryGroup(groupName string, industryNames []string) error

	// DeleteCountryGroup deletes a country group
	DeleteCountryGroup(groupName string) error

	// DeleteIndustryGroup deletes an industry group
	DeleteIndustryGroup(groupName string) error

	// GetAvailableCountries returns all distinct countries from securities
	GetAvailableCountries() ([]string, error)

	// GetAvailableIndustries returns all distinct industries from securities
	GetAvailableIndustries() ([]string, error)
}

// Compile-time check that GroupingRepository implements GroupingRepositoryInterface
var _ GroupingRepositoryInterface = (*GroupingRepository)(nil)
