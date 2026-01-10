package handlers

import (
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/stretchr/testify/assert"
)

func TestRegisterRoutes(t *testing.T) {
	handler := setupTestHandler(t)

	router := chi.NewRouter()

	// Should not panic
	assert.NotPanics(t, func() {
		handler.RegisterRoutes(router)
	}, "RegisterRoutes should not panic")
}
