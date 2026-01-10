package handlers

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestRegisterRoutes(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	db := setupTestDB(t)
	defer db.Close()

	historyDB := universe.NewHistoryDB(db, logger)
	mockRepo := &mockPositionRepository{}
	handler := NewHandler(historyDB, mockRepo, logger)

	router := chi.NewRouter()

	// Should not panic
	assert.NotPanics(t, func() {
		handler.RegisterRoutes(router)
	}, "RegisterRoutes should not panic")
}
