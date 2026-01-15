package work

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
)

// MockBackupService mocks the backup service
type MockBackupService struct {
	mock.Mock
}

func (m *MockBackupService) RunDailyBackup() error {
	args := m.Called()
	return args.Error(0)
}

func (m *MockBackupService) BackedUpToday() bool {
	args := m.Called()
	return args.Bool(0)
}

// MockR2BackupService mocks the R2 backup service
type MockR2BackupService struct {
	mock.Mock
}

func (m *MockR2BackupService) UploadBackup() error {
	args := m.Called()
	return args.Error(0)
}

func (m *MockR2BackupService) RotateBackups() error {
	args := m.Called()
	return args.Error(0)
}

// MockVacuumService mocks the database vacuum service
type MockVacuumService struct {
	mock.Mock
}

func (m *MockVacuumService) VacuumDatabases() error {
	args := m.Called()
	return args.Error(0)
}

// MockHealthCheckService mocks the health check service
type MockHealthCheckService struct {
	mock.Mock
}

func (m *MockHealthCheckService) RunHealthChecks() error {
	args := m.Called()
	return args.Error(0)
}

// MockCleanupService mocks cleanup services
type MockCleanupService struct {
	mock.Mock
}

func (m *MockCleanupService) CleanupHistory() error {
	args := m.Called()
	return args.Error(0)
}

func (m *MockCleanupService) CleanupCache() error {
	args := m.Called()
	return args.Error(0)
}

func (m *MockCleanupService) CleanupRecommendations() error {
	args := m.Called()
	return args.Error(0)
}

func (m *MockCleanupService) CleanupClientData() error {
	args := m.Called()
	return args.Error(0)
}

func TestRegisterMaintenanceWorkTypes(t *testing.T) {
	registry := NewRegistry()

	deps := &MaintenanceDeps{
		BackupService:      &MockBackupService{},
		R2BackupService:    &MockR2BackupService{},
		VacuumService:      &MockVacuumService{},
		HealthCheckService: &MockHealthCheckService{},
		CleanupService:     &MockCleanupService{},
	}

	RegisterMaintenanceWorkTypes(registry, deps)

	// Verify maintenance work types are registered
	assert.True(t, registry.Has("maintenance:backup"))
	assert.True(t, registry.Has("maintenance:r2-backup"))
	assert.True(t, registry.Has("maintenance:r2-rotation"))
	assert.True(t, registry.Has("maintenance:vacuum"))
	assert.True(t, registry.Has("maintenance:health"))
	assert.True(t, registry.Has("maintenance:cleanup:history"))
	assert.True(t, registry.Has("maintenance:cleanup:cache"))
	assert.True(t, registry.Has("maintenance:cleanup:recommendations"))
	assert.True(t, registry.Has("maintenance:cleanup:client-data"))
}

func TestMaintenanceWorkTypes_Dependencies(t *testing.T) {
	registry := NewRegistry()
	deps := &MaintenanceDeps{
		BackupService:      &MockBackupService{},
		R2BackupService:    &MockR2BackupService{},
		VacuumService:      &MockVacuumService{},
		HealthCheckService: &MockHealthCheckService{},
		CleanupService:     &MockCleanupService{},
	}

	RegisterMaintenanceWorkTypes(registry, deps)

	// maintenance:r2-backup depends on maintenance:backup
	r2BackupWt := registry.Get("maintenance:r2-backup")
	require.NotNil(t, r2BackupWt)
	assert.Contains(t, r2BackupWt.DependsOn, "maintenance:backup")

	// maintenance:r2-rotation depends on maintenance:r2-backup
	r2RotationWt := registry.Get("maintenance:r2-rotation")
	require.NotNil(t, r2RotationWt)
	assert.Contains(t, r2RotationWt.DependsOn, "maintenance:r2-backup")

	// maintenance:vacuum depends on maintenance:backup
	vacuumWt := registry.Get("maintenance:vacuum")
	require.NotNil(t, vacuumWt)
	assert.Contains(t, vacuumWt.DependsOn, "maintenance:backup")
}

func TestMaintenanceBackup_Execute(t *testing.T) {
	registry := NewRegistry()

	backupService := &MockBackupService{}
	backupService.On("RunDailyBackup").Return(nil)
	// BackedUpToday is called by FindSubjects, not Execute
	backupService.On("BackedUpToday").Return(false).Maybe()

	deps := &MaintenanceDeps{
		BackupService:      backupService,
		R2BackupService:    &MockR2BackupService{},
		VacuumService:      &MockVacuumService{},
		HealthCheckService: &MockHealthCheckService{},
		CleanupService:     &MockCleanupService{},
	}

	RegisterMaintenanceWorkTypes(registry, deps)

	wt := registry.Get("maintenance:backup")
	require.NotNil(t, wt)

	err := wt.Execute(context.Background(), "")
	require.NoError(t, err)

	backupService.AssertCalled(t, "RunDailyBackup")
}

func TestMaintenanceBackup_FindSubjects_NotNeeded(t *testing.T) {
	registry := NewRegistry()

	backupService := &MockBackupService{}
	backupService.On("BackedUpToday").Return(true)

	deps := &MaintenanceDeps{
		BackupService:      backupService,
		R2BackupService:    &MockR2BackupService{},
		VacuumService:      &MockVacuumService{},
		HealthCheckService: &MockHealthCheckService{},
		CleanupService:     &MockCleanupService{},
	}

	RegisterMaintenanceWorkTypes(registry, deps)

	wt := registry.Get("maintenance:backup")
	require.NotNil(t, wt)

	// Already backed up = no work needed
	subjects := wt.FindSubjects()
	assert.Nil(t, subjects)
}

func TestMaintenanceWorkTypes_MarketTiming(t *testing.T) {
	registry := NewRegistry()
	deps := &MaintenanceDeps{
		BackupService:      &MockBackupService{},
		R2BackupService:    &MockR2BackupService{},
		VacuumService:      &MockVacuumService{},
		HealthCheckService: &MockHealthCheckService{},
		CleanupService:     &MockCleanupService{},
	}

	RegisterMaintenanceWorkTypes(registry, deps)

	// Most maintenance should run when all markets closed
	allClosedTypes := []string{"maintenance:backup", "maintenance:r2-backup", "maintenance:r2-rotation",
		"maintenance:vacuum", "maintenance:health", "maintenance:cleanup:history",
		"maintenance:cleanup:cache", "maintenance:cleanup:client-data"}
	for _, id := range allClosedTypes {
		wt := registry.Get(id)
		require.NotNil(t, wt, "work type %s should exist", id)
		assert.Equal(t, AllMarketsClosed, wt.MarketTiming, "work type %s should be AllMarketsClosed", id)
	}

	// maintenance:cleanup:recommendations runs anytime (hourly)
	recGcWt := registry.Get("maintenance:cleanup:recommendations")
	require.NotNil(t, recGcWt)
	assert.Equal(t, AnyTime, recGcWt.MarketTiming)
}

func TestMaintenanceWorkTypes_Priority(t *testing.T) {
	registry := NewRegistry()
	deps := &MaintenanceDeps{
		BackupService:      &MockBackupService{},
		R2BackupService:    &MockR2BackupService{},
		VacuumService:      &MockVacuumService{},
		HealthCheckService: &MockHealthCheckService{},
		CleanupService:     &MockCleanupService{},
	}

	RegisterMaintenanceWorkTypes(registry, deps)

	// All maintenance work should be low priority
	for _, id := range registry.IDs() {
		if len(id) > 12 && id[:12] == "maintenance:" {
			wt := registry.Get(id)
			require.NotNil(t, wt)
			assert.Equal(t, PriorityLow, wt.Priority, "work type %s should be low priority", id)
		}
	}
}

func TestMaintenanceWorkTypes_Interval(t *testing.T) {
	registry := NewRegistry()
	deps := &MaintenanceDeps{
		BackupService:      &MockBackupService{},
		R2BackupService:    &MockR2BackupService{},
		VacuumService:      &MockVacuumService{},
		HealthCheckService: &MockHealthCheckService{},
		CleanupService:     &MockCleanupService{},
	}

	RegisterMaintenanceWorkTypes(registry, deps)

	// maintenance:backup should have 24h interval
	backupWt := registry.Get("maintenance:backup")
	require.NotNil(t, backupWt)
	assert.Equal(t, 24*time.Hour, backupWt.Interval)

	// maintenance:cleanup:recommendations should have 1h interval
	recGcWt := registry.Get("maintenance:cleanup:recommendations")
	require.NotNil(t, recGcWt)
	assert.Equal(t, 1*time.Hour, recGcWt.Interval)
}
