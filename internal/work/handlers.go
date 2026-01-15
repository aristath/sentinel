package work

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
)

// Handlers provides HTTP handlers for the work processor
type Handlers struct {
	processor *Processor
	registry  *Registry
}

// NewHandlers creates new HTTP handlers for the work processor
func NewHandlers(processor *Processor, registry *Registry) *Handlers {
	return &Handlers{
		processor: processor,
		registry:  registry,
	}
}

// RegisterRoutes registers HTTP routes for work management
func (h *Handlers) RegisterRoutes(r chi.Router) {
	r.Route("/api/work", func(r chi.Router) {
		r.Get("/types", h.ListWorkTypes)
		r.Post("/{workType}/execute", h.ExecuteWorkType)
		r.Post("/{workType}/{subject}/execute", h.ExecuteWorkTypeWithSubject)
		r.Post("/trigger", h.TriggerProcessor)
	})
}

// ListWorkTypes returns all registered work types
func (h *Handlers) ListWorkTypes(w http.ResponseWriter, r *http.Request) {
	types := h.registry.ByPriority()

	response := make([]map[string]any, 0, len(types))
	for _, wt := range types {
		response = append(response, map[string]any{
			"id":            wt.ID,
			"priority":      wt.Priority.String(),
			"market_timing": wt.MarketTiming.String(),
			"depends_on":    wt.DependsOn,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// ExecuteWorkType manually executes a work type (global work)
func (h *Handlers) ExecuteWorkType(w http.ResponseWriter, r *http.Request) {
	workType := chi.URLParam(r, "workType")

	err := h.processor.ExecuteNow(workType, "")
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status":    "executed",
		"work_type": workType,
	})
}

// ExecuteWorkTypeWithSubject manually executes a work type with a subject
func (h *Handlers) ExecuteWorkTypeWithSubject(w http.ResponseWriter, r *http.Request) {
	workType := chi.URLParam(r, "workType")
	subject := chi.URLParam(r, "subject")

	err := h.processor.ExecuteNow(workType, subject)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status":    "executed",
		"work_type": workType,
		"subject":   subject,
	})
}

// TriggerProcessor triggers the processor to check for work
func (h *Handlers) TriggerProcessor(w http.ResponseWriter, r *http.Request) {
	h.processor.Trigger()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "triggered",
	})
}
