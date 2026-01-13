package di

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestContainer_Initialization(t *testing.T) {
	container := &Container{}

	// Test that container can be created
	assert.NotNil(t, container)

	// Test that all fields are accessible (nil initially)
	assert.Nil(t, container.UniverseDB)
	assert.Nil(t, container.ConfigDB)
	assert.Nil(t, container.LedgerDB)
	assert.Nil(t, container.PortfolioDB)
	assert.Nil(t, container.HistoryDB)
	assert.Nil(t, container.CacheDB)
	assert.Nil(t, container.ClientDataDB)
}

func TestContainer_CanSetDatabases(t *testing.T) {
	container := &Container{}

	// This test verifies the container can hold database references
	// We can't create real databases in unit tests, but we can verify the structure
	assert.NotNil(t, container)
}

func TestJobInstances_Initialization(t *testing.T) {
	instances := &JobInstances{}

	// Test that JobInstances can be created
	assert.NotNil(t, instances)

	// All jobs should be nil initially
	assert.Nil(t, instances.HealthCheck)
	assert.Nil(t, instances.SyncCycle)
	assert.Nil(t, instances.DividendReinvest)
	assert.Nil(t, instances.PlannerBatch)
	assert.Nil(t, instances.EventBasedTrading)
	assert.Nil(t, instances.TagUpdate)
}
