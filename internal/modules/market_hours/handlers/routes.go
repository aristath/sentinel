package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all market hours routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/market-hours", func(r chi.Router) {
		r.Get("/status", h.HandleGetStatus)
		r.Get("/status/{exchange}", func(w http.ResponseWriter, r *http.Request) {
			exchange := chi.URLParam(r, "exchange")
			h.HandleGetStatusByExchange(w, r, exchange)
		})
		r.Get("/open-markets", h.HandleGetOpenMarkets)
		r.Get("/holidays", h.HandleGetHolidays)
		r.Get("/validate-trading-window", h.HandleValidateTradingWindow)
	})
}
