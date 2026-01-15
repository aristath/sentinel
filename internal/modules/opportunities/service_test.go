package opportunities

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/progress"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestIdentifyOpportunitiesWithProgress_CallsCallback(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(nil, nil, log)

	ctx := &domain.OpportunityContext{
		AllowBuy:         true,
		AllowSell:        true,
		AvailableCashEUR: 1000,
	}
	config := domain.NewDefaultConfiguration()

	var progressUpdates []progress.Update
	callback := func(update progress.Update) {
		progressUpdates = append(progressUpdates, update)
	}

	_, err := service.IdentifyOpportunitiesWithProgress(ctx, config, callback)
	require.NoError(t, err)

	// Should have received progress updates (one per calculator + completion)
	assert.NotEmpty(t, progressUpdates, "Should receive progress updates")

	// All updates should be in the opportunity_identification phase
	for _, update := range progressUpdates {
		assert.Equal(t, "opportunity_identification", update.Phase)
	}
}

func TestIdentifyOpportunitiesWithProgress_NilCallback(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(nil, nil, log)

	ctx := &domain.OpportunityContext{
		AllowBuy:         true,
		AllowSell:        true,
		AvailableCashEUR: 1000,
	}
	config := domain.NewDefaultConfiguration()

	// Should not panic with nil callback
	_, err := service.IdentifyOpportunitiesWithProgress(ctx, config, nil)
	require.NoError(t, err)
}

func TestIdentifyOpportunitiesWithProgress_ProgressDetails(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(nil, nil, log)

	ctx := &domain.OpportunityContext{
		AllowBuy:         true,
		AllowSell:        true,
		AvailableCashEUR: 1000,
	}
	config := domain.NewDefaultConfiguration()

	var lastUpdate progress.Update
	callback := func(update progress.Update) {
		lastUpdate = update
	}

	_, err := service.IdentifyOpportunitiesWithProgress(ctx, config, callback)
	require.NoError(t, err)

	// Last update should have details
	assert.NotNil(t, lastUpdate.Details, "Final update should have details")
}

func TestIdentifyOpportunitiesWithExclusions_DelegatesToProgressMethod(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(nil, nil, log)

	ctx := &domain.OpportunityContext{
		AllowBuy:         true,
		AllowSell:        true,
		AvailableCashEUR: 1000,
	}
	config := domain.NewDefaultConfiguration()

	// IdentifyOpportunitiesWithExclusions should work (delegates internally)
	_, err := service.IdentifyOpportunitiesWithExclusions(ctx, config)
	require.NoError(t, err)
}

func TestIdentifyOpportunitiesWithProgress_NilContext(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(nil, nil, log)

	config := domain.NewDefaultConfiguration()

	_, err := service.IdentifyOpportunitiesWithProgress(nil, config, nil)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "context is nil")
}

func TestIdentifyOpportunitiesWithProgress_NilConfig(t *testing.T) {
	log := zerolog.Nop()
	service := NewService(nil, nil, log)

	ctx := &domain.OpportunityContext{
		AllowBuy:  true,
		AllowSell: true,
	}

	_, err := service.IdentifyOpportunitiesWithProgress(ctx, nil, nil)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "configuration is nil")
}
