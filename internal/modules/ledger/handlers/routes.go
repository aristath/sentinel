package handlers

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// RegisterRoutes registers all ledger routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/ledger", func(r chi.Router) {
		// Trade endpoints
		r.Get("/trades", h.HandleGetTrades)
		r.Get("/trades/summary", h.HandleGetTradesSummary)
		r.Get("/trades/{id}", func(w http.ResponseWriter, r *http.Request) {
			id := chi.URLParam(r, "id")
			h.HandleGetTradeByID(w, r, id)
		})

		// Cash flow endpoints
		r.Route("/cash-flows", func(r chi.Router) {
			r.Get("/all", h.HandleGetAllCashFlows)
			r.Get("/deposits", h.HandleGetDeposits)
			r.Get("/withdrawals", h.HandleGetWithdrawals)
			r.Get("/fees", h.HandleGetFees)
			r.Get("/summary", h.HandleGetCashFlowsSummary)
		})

		// Dividend endpoints
		r.Route("/dividends", func(r chi.Router) {
			r.Get("/history", h.HandleGetDividendHistory)
			r.Get("/reinvestment-stats", h.HandleGetDividendReinvestmentStats)
			r.Get("/pending-reinvestments", h.HandleGetPendingReinvestments)
		})

		// DRIP tracking
		r.Get("/drip-tracking", h.HandleGetDRIPTracking)
	})
}
