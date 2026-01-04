package universe

import (
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestHistoricalSyncServiceCreation(t *testing.T) {
	log := zerolog.Nop()

	service := NewHistoricalSyncService(
		nil, // yahooClient
		nil, // securityRepo
		nil, // historyDB
		1*time.Second,
		log,
	)

	assert.NotNil(t, service)
	assert.Equal(t, 1*time.Second, service.rateLimitDelay)
}

func TestHistoricalSyncService_SyncWithoutClients(t *testing.T) {
	log := zerolog.Nop()

	service := NewHistoricalSyncService(
		nil,
		nil,
		nil,
		0, // no rate limit for tests
		log,
	)

	// Should panic with nil security repo (nil pointer dereference)
	assert.Panics(t, func() {
		_ = service.SyncHistoricalPrices("AAPL.US")
	})
}

// Note: Full integration tests with real Yahoo Finance and database
// should be in integration test suite. These are unit tests focusing
// on service logic without external dependencies.
