package calculations

import (
	"errors"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockSecuritySyncer implements SecuritySyncer for testing
type mockSecuritySyncer struct {
	refreshedSymbols []string
	err              error
}

func (m *mockSecuritySyncer) RefreshSingleSecurity(symbol string) error {
	if m.err != nil {
		return m.err
	}
	m.refreshedSymbols = append(m.refreshedSymbols, symbol)
	return nil
}

func TestDefaultSyncProcessor_NeedsSync_NeverSynced(t *testing.T) {
	processor := NewDefaultSyncProcessor(nil, zerolog.Nop())

	security := universe.Security{
		ISIN:       "TEST_ISIN",
		Symbol:     "TEST",
		LastSynced: nil, // Never synced
	}

	assert.True(t, processor.NeedsSync(security), "Should need sync when never synced")
}

func TestDefaultSyncProcessor_NeedsSync_RecentlysynSynced(t *testing.T) {
	processor := NewDefaultSyncProcessor(nil, zerolog.Nop())

	recent := time.Now().Add(-1 * time.Hour).Unix() // 1 hour ago
	security := universe.Security{
		ISIN:       "TEST_ISIN",
		Symbol:     "TEST",
		LastSynced: &recent,
	}

	assert.False(t, processor.NeedsSync(security), "Should not need sync when synced recently")
}

func TestDefaultSyncProcessor_NeedsSync_OldSync(t *testing.T) {
	processor := NewDefaultSyncProcessor(nil, zerolog.Nop())

	old := time.Now().Add(-25 * time.Hour).Unix() // 25 hours ago
	security := universe.Security{
		ISIN:       "TEST_ISIN",
		Symbol:     "TEST",
		LastSynced: &old,
	}

	assert.True(t, processor.NeedsSync(security), "Should need sync when synced > 24h ago")
}

func TestDefaultSyncProcessor_NeedsSync_ExactThreshold(t *testing.T) {
	processor := NewDefaultSyncProcessor(nil, zerolog.Nop())

	// Exactly at threshold (24 hours ago)
	threshold := time.Now().Add(-24 * time.Hour).Unix()
	security := universe.Security{
		ISIN:       "TEST_ISIN",
		Symbol:     "TEST",
		LastSynced: &threshold,
	}

	// At exactly the threshold, should NOT need sync (using < comparison, not <=)
	assert.False(t, processor.NeedsSync(security), "Should not need sync at exactly 24h threshold")
}

func TestDefaultSyncProcessor_NeedsSync_JustPastThreshold(t *testing.T) {
	processor := NewDefaultSyncProcessor(nil, zerolog.Nop())

	// One second past threshold
	pastThreshold := time.Now().Add(-24*time.Hour - 1*time.Second).Unix()
	security := universe.Security{
		ISIN:       "TEST_ISIN",
		Symbol:     "TEST",
		LastSynced: &pastThreshold,
	}

	// Just past threshold should need sync
	assert.True(t, processor.NeedsSync(security), "Should need sync when past 24h threshold")
}

func TestDefaultSyncProcessor_ProcessSync_Success(t *testing.T) {
	syncer := &mockSecuritySyncer{}
	processor := NewDefaultSyncProcessor(syncer, zerolog.Nop())

	security := universe.Security{
		ISIN:   "TEST_ISIN",
		Symbol: "TEST",
	}

	err := processor.ProcessSync(security)
	require.NoError(t, err)
	assert.Contains(t, syncer.refreshedSymbols, "TEST")
}

func TestDefaultSyncProcessor_ProcessSync_Error(t *testing.T) {
	syncer := &mockSecuritySyncer{err: errors.New("sync failed")}
	processor := NewDefaultSyncProcessor(syncer, zerolog.Nop())

	security := universe.Security{
		ISIN:   "TEST_ISIN",
		Symbol: "TEST",
	}

	err := processor.ProcessSync(security)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "sync failed")
}

func TestDefaultSyncProcessor_ProcessSync_MultipleSecurities(t *testing.T) {
	syncer := &mockSecuritySyncer{}
	processor := NewDefaultSyncProcessor(syncer, zerolog.Nop())

	securities := []universe.Security{
		{ISIN: "ISIN1", Symbol: "SYM1"},
		{ISIN: "ISIN2", Symbol: "SYM2"},
		{ISIN: "ISIN3", Symbol: "SYM3"},
	}

	for _, sec := range securities {
		err := processor.ProcessSync(sec)
		require.NoError(t, err)
	}

	assert.Len(t, syncer.refreshedSymbols, 3)
	assert.Contains(t, syncer.refreshedSymbols, "SYM1")
	assert.Contains(t, syncer.refreshedSymbols, "SYM2")
	assert.Contains(t, syncer.refreshedSymbols, "SYM3")
}
