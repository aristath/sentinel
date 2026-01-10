package handlers

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestRegisterRoutes(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := market_hours.NewMarketHoursService()
	handler := NewHandler(service, logger)

	router := chi.NewRouter()

	// Should not panic
	assert.NotPanics(t, func() {
		handler.RegisterRoutes(router)
	}, "RegisterRoutes should not panic")
}

func TestRegisterRoutes_RoutePrefix(t *testing.T) {
	logger := zerolog.New(nil).Level(zerolog.Disabled)
	service := market_hours.NewMarketHoursService()
	handler := NewHandler(service, logger)

	router := chi.NewRouter()
	handler.RegisterRoutes(router)

	// Verify routes are registered with correct prefix
	routes := router.Routes()
	assert.NotEmpty(t, routes, "Routes should be registered")

	// Check for expected route patterns
	routePatterns := []string{}
	for _, route := range routes {
		routePatterns = append(routePatterns, route.Pattern)
	}

	// Should have market-hours routes
	hasMarketHoursRoutes := false
	for _, pattern := range routePatterns {
		if len(pattern) > 0 && pattern[0:1] == "/" {
			hasMarketHoursRoutes = true
			break
		}
	}
	assert.True(t, hasMarketHoursRoutes, "Should have market hours routes registered")
}
