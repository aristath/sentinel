package handlers

import (
	"testing"

	"github.com/aristath/sentinel/internal/market_regime"
	"github.com/aristath/sentinel/internal/modules/adaptation"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestRegisterRoutes(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	adaptiveService := adaptation.NewAdaptiveMarketService(nil, nil, nil, nil, logger)
	regimePersistence := market_regime.NewRegimePersistence(db, logger)
	handler := NewHandler(regimePersistence, adaptiveService, logger)

	router := chi.NewRouter()

	// Should not panic
	assert.NotPanics(t, func() {
		handler.RegisterRoutes(router)
	}, "RegisterRoutes should not panic")
}
