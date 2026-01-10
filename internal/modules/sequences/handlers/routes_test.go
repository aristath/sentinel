package handlers

import (
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestRegisterRoutes(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := setupTestService()
	handler := NewHandler(service, logger)

	router := chi.NewRouter()

	// Should not panic
	assert.NotPanics(t, func() {
		handler.RegisterRoutes(router)
	}, "RegisterRoutes should not panic")
}
