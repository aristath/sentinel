package work

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
)

// MockSecurityHistorySyncService mocks the security history sync service
type MockSecurityHistorySyncService struct {
	mock.Mock
}

func (m *MockSecurityHistorySyncService) SyncSecurityHistory(isin string) error {
	args := m.Called(isin)
	return args.Error(0)
}

func (m *MockSecurityHistorySyncService) GetStaleSecurities() []string {
	args := m.Called()
	if args.Get(0) == nil {
		return nil
	}
	return args.Get(0).([]string)
}

// MockTechnicalCalculationService mocks the technical calculation service
type MockTechnicalCalculationService struct {
	mock.Mock
}

func (m *MockTechnicalCalculationService) CalculateTechnicals(isin string) error {
	args := m.Called(isin)
	return args.Error(0)
}

func (m *MockTechnicalCalculationService) GetSecuritiesNeedingTechnicals() []string {
	args := m.Called()
	if args.Get(0) == nil {
		return nil
	}
	return args.Get(0).([]string)
}

// MockFormulaDiscoveryService mocks the formula discovery service
type MockFormulaDiscoveryService struct {
	mock.Mock
}

func (m *MockFormulaDiscoveryService) RunDiscovery(isin string) error {
	args := m.Called(isin)
	return args.Error(0)
}

func (m *MockFormulaDiscoveryService) GetSecuritiesNeedingDiscovery() []string {
	args := m.Called()
	if args.Get(0) == nil {
		return nil
	}
	return args.Get(0).([]string)
}

// MockTagUpdateService mocks the tag update service
type MockTagUpdateService struct {
	mock.Mock
}

func (m *MockTagUpdateService) UpdateTags(isin string) error {
	args := m.Called(isin)
	return args.Error(0)
}

func (m *MockTagUpdateService) GetSecuritiesNeedingTagUpdate() []string {
	args := m.Called()
	if args.Get(0) == nil {
		return nil
	}
	return args.Get(0).([]string)
}

// MockMetadataSyncService mocks the metadata sync service
type MockMetadataSyncService struct {
	mock.Mock
}

func (m *MockMetadataSyncService) SyncMetadata(isin string) error {
	args := m.Called(isin)
	return args.Error(0)
}

func (m *MockMetadataSyncService) GetAllActiveISINs() []string {
	args := m.Called()
	if args.Get(0) == nil {
		return nil
	}
	return args.Get(0).([]string)
}

func TestRegisterSecurityWorkTypes(t *testing.T) {
	registry := NewRegistry()

	deps := &SecurityDeps{
		HistorySyncService:  &MockSecurityHistorySyncService{},
		TechnicalService:    &MockTechnicalCalculationService{},
		FormulaService:      &MockFormulaDiscoveryService{},
		TagService:          &MockTagUpdateService{},
		MetadataSyncService: &MockMetadataSyncService{},
	}

	RegisterSecurityWorkTypes(registry, deps)

	// Verify all 5 security work types are registered
	assert.True(t, registry.Has("security:sync"))
	assert.True(t, registry.Has("security:technical"))
	assert.True(t, registry.Has("security:formula"))
	assert.True(t, registry.Has("security:tags"))
	assert.True(t, registry.Has("security:metadata"))
}

func TestSecurityWorkTypes_Dependencies(t *testing.T) {
	registry := NewRegistry()
	deps := &SecurityDeps{
		HistorySyncService:  &MockSecurityHistorySyncService{},
		TechnicalService:    &MockTechnicalCalculationService{},
		FormulaService:      &MockFormulaDiscoveryService{},
		TagService:          &MockTagUpdateService{},
		MetadataSyncService: &MockMetadataSyncService{},
	}

	RegisterSecurityWorkTypes(registry, deps)

	// security:sync has no dependencies (root)
	syncWt := registry.Get("security:sync")
	require.NotNil(t, syncWt)
	assert.Empty(t, syncWt.DependsOn)

	// security:technical depends on security:sync
	technicalWt := registry.Get("security:technical")
	require.NotNil(t, technicalWt)
	assert.Contains(t, technicalWt.DependsOn, "security:sync")

	// security:formula depends on security:technical
	formulaWt := registry.Get("security:formula")
	require.NotNil(t, formulaWt)
	assert.Contains(t, formulaWt.DependsOn, "security:technical")

	// security:tags depends on security:sync
	tagsWt := registry.Get("security:tags")
	require.NotNil(t, tagsWt)
	assert.Contains(t, tagsWt.DependsOn, "security:sync")
}

func TestSecuritySync_Execute(t *testing.T) {
	registry := NewRegistry()

	historySyncService := &MockSecurityHistorySyncService{}
	historySyncService.On("SyncSecurityHistory", "NL0010273215").Return(nil)
	// GetStaleSecurities is called by FindSubjects, not Execute
	historySyncService.On("GetStaleSecurities").Return([]string{"NL0010273215"}).Maybe()

	deps := &SecurityDeps{
		HistorySyncService:  historySyncService,
		TechnicalService:    &MockTechnicalCalculationService{},
		FormulaService:      &MockFormulaDiscoveryService{},
		TagService:          &MockTagUpdateService{},
		MetadataSyncService: &MockMetadataSyncService{},
	}

	RegisterSecurityWorkTypes(registry, deps)

	wt := registry.Get("security:sync")
	require.NotNil(t, wt)

	// Execute with ISIN as subject
	err := wt.Execute(context.Background(), "NL0010273215", nil)
	require.NoError(t, err)

	historySyncService.AssertCalled(t, "SyncSecurityHistory", "NL0010273215")
}

func TestSecuritySync_FindSubjects(t *testing.T) {
	registry := NewRegistry()

	historySyncService := &MockSecurityHistorySyncService{}
	historySyncService.On("GetStaleSecurities").Return([]string{"NL0010273215", "US0378331005"})

	deps := &SecurityDeps{
		HistorySyncService:  historySyncService,
		TechnicalService:    &MockTechnicalCalculationService{},
		FormulaService:      &MockFormulaDiscoveryService{},
		TagService:          &MockTagUpdateService{},
		MetadataSyncService: &MockMetadataSyncService{},
	}

	RegisterSecurityWorkTypes(registry, deps)

	wt := registry.Get("security:sync")
	require.NotNil(t, wt)

	subjects := wt.FindSubjects()
	assert.ElementsMatch(t, []string{"NL0010273215", "US0378331005"}, subjects)
}

func TestSecurityTechnical_Execute(t *testing.T) {
	registry := NewRegistry()

	technicalService := &MockTechnicalCalculationService{}
	technicalService.On("CalculateTechnicals", "NL0010273215").Return(nil)
	// GetSecuritiesNeedingTechnicals is called by FindSubjects, not Execute
	technicalService.On("GetSecuritiesNeedingTechnicals").Return([]string{"NL0010273215"}).Maybe()

	// Need to set up FindSubjects mock for security:sync too since it's a dependency
	historySyncService := &MockSecurityHistorySyncService{}
	historySyncService.On("GetStaleSecurities").Return([]string{}).Maybe()

	deps := &SecurityDeps{
		HistorySyncService:  historySyncService,
		TechnicalService:    technicalService,
		FormulaService:      &MockFormulaDiscoveryService{},
		TagService:          &MockTagUpdateService{},
		MetadataSyncService: &MockMetadataSyncService{},
	}

	RegisterSecurityWorkTypes(registry, deps)

	wt := registry.Get("security:technical")
	require.NotNil(t, wt)

	err := wt.Execute(context.Background(), "NL0010273215", nil)
	require.NoError(t, err)

	technicalService.AssertCalled(t, "CalculateTechnicals", "NL0010273215")
}

func TestSecurityWorkTypes_MarketTiming(t *testing.T) {
	registry := NewRegistry()
	deps := &SecurityDeps{
		HistorySyncService:  &MockSecurityHistorySyncService{},
		TechnicalService:    &MockTechnicalCalculationService{},
		FormulaService:      &MockFormulaDiscoveryService{},
		TagService:          &MockTagUpdateService{},
		MetadataSyncService: &MockMetadataSyncService{},
	}

	RegisterSecurityWorkTypes(registry, deps)

	// All security work should run after market close
	for _, id := range []string{"security:sync", "security:technical", "security:formula", "security:tags"} {
		wt := registry.Get(id)
		require.NotNil(t, wt, "work type %s should exist", id)
		assert.Equal(t, AfterMarketClose, wt.MarketTiming, "work type %s should be AfterMarketClose", id)
	}
}

func TestSecurityWorkTypes_Interval(t *testing.T) {
	registry := NewRegistry()
	deps := &SecurityDeps{
		HistorySyncService:  &MockSecurityHistorySyncService{},
		TechnicalService:    &MockTechnicalCalculationService{},
		FormulaService:      &MockFormulaDiscoveryService{},
		TagService:          &MockTagUpdateService{},
		MetadataSyncService: &MockMetadataSyncService{},
	}

	RegisterSecurityWorkTypes(registry, deps)

	// security:sync should have 24h interval
	syncWt := registry.Get("security:sync")
	require.NotNil(t, syncWt)
	assert.Equal(t, 24*time.Hour, syncWt.Interval)

	// security:technical should have 24h interval
	technicalWt := registry.Get("security:technical")
	require.NotNil(t, technicalWt)
	assert.Equal(t, 24*time.Hour, technicalWt.Interval)

	// security:formula should have 30 day interval
	formulaWt := registry.Get("security:formula")
	require.NotNil(t, formulaWt)
	assert.Equal(t, 30*24*time.Hour, formulaWt.Interval)

	// security:tags should have 7 day interval
	tagsWt := registry.Get("security:tags")
	require.NotNil(t, tagsWt)
	assert.Equal(t, 7*24*time.Hour, tagsWt.Interval)

	// security:metadata should have 24h interval
	metadataWt := registry.Get("security:metadata")
	require.NotNil(t, metadataWt)
	assert.Equal(t, 24*time.Hour, metadataWt.Interval)
}

func TestSecurityMetadata_Execute(t *testing.T) {
	registry := NewRegistry()

	metadataService := &MockMetadataSyncService{}
	metadataService.On("SyncMetadata", "NL0010273215").Return(nil)
	metadataService.On("GetAllActiveISINs").Return([]string{"NL0010273215"}).Maybe()

	deps := &SecurityDeps{
		HistorySyncService:  &MockSecurityHistorySyncService{},
		TechnicalService:    &MockTechnicalCalculationService{},
		FormulaService:      &MockFormulaDiscoveryService{},
		TagService:          &MockTagUpdateService{},
		MetadataSyncService: metadataService,
	}

	RegisterSecurityWorkTypes(registry, deps)

	wt := registry.Get("security:metadata")
	require.NotNil(t, wt)

	// Execute with ISIN as subject
	err := wt.Execute(context.Background(), "NL0010273215", nil)
	require.NoError(t, err)

	metadataService.AssertCalled(t, "SyncMetadata", "NL0010273215")
}

func TestSecurityMetadata_FindSubjects(t *testing.T) {
	registry := NewRegistry()

	metadataService := &MockMetadataSyncService{}
	metadataService.On("GetAllActiveISINs").Return([]string{"NL0010273215", "US0378331005", "IE00B4L5Y983"})

	deps := &SecurityDeps{
		HistorySyncService:  &MockSecurityHistorySyncService{},
		TechnicalService:    &MockTechnicalCalculationService{},
		FormulaService:      &MockFormulaDiscoveryService{},
		TagService:          &MockTagUpdateService{},
		MetadataSyncService: metadataService,
	}

	RegisterSecurityWorkTypes(registry, deps)

	wt := registry.Get("security:metadata")
	require.NotNil(t, wt)

	subjects := wt.FindSubjects()
	assert.ElementsMatch(t, []string{"NL0010273215", "US0378331005", "IE00B4L5Y983"}, subjects)
}

func TestSecurityMetadata_MarketTiming(t *testing.T) {
	registry := NewRegistry()
	deps := &SecurityDeps{
		HistorySyncService:  &MockSecurityHistorySyncService{},
		TechnicalService:    &MockTechnicalCalculationService{},
		FormulaService:      &MockFormulaDiscoveryService{},
		TagService:          &MockTagUpdateService{},
		MetadataSyncService: &MockMetadataSyncService{},
	}

	RegisterSecurityWorkTypes(registry, deps)

	// security:metadata should run AnyTime (not dependent on market hours)
	metadataWt := registry.Get("security:metadata")
	require.NotNil(t, metadataWt)
	assert.Equal(t, AnyTime, metadataWt.MarketTiming)
}

func TestSecurityMetadata_NoDependencies(t *testing.T) {
	registry := NewRegistry()
	deps := &SecurityDeps{
		HistorySyncService:  &MockSecurityHistorySyncService{},
		TechnicalService:    &MockTechnicalCalculationService{},
		FormulaService:      &MockFormulaDiscoveryService{},
		TagService:          &MockTagUpdateService{},
		MetadataSyncService: &MockMetadataSyncService{},
	}

	RegisterSecurityWorkTypes(registry, deps)

	// security:metadata has no dependencies (can run independently)
	metadataWt := registry.Get("security:metadata")
	require.NotNil(t, metadataWt)
	assert.Empty(t, metadataWt.DependsOn)
}
