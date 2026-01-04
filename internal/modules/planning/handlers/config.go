package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/aristath/arduino-trader/internal/modules/planning"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// ConfigHandler handles CRUD operations for planner configurations.
type ConfigHandler struct {
	service *planning.Service
	log     zerolog.Logger
}

// NewConfigHandler creates a new config handler.
func NewConfigHandler(service *planning.Service, log zerolog.Logger) *ConfigHandler {
	return &ConfigHandler{
		service: service,
		log:     log.With().Str("handler", "config").Logger(),
	}
}

// ConfigListResponse represents a list of configurations.
type ConfigListResponse struct {
	Configs []ConfigSummary `json:"configs"`
	Total   int             `json:"total"`
}

// ConfigSummary provides a summary of a configuration.
type ConfigSummary struct {
	ID        int    `json:"id"`
	Name      string `json:"name"`
	CreatedAt string `json:"created_at"`
	UpdatedAt string `json:"updated_at"`
}

// ConfigResponse wraps a single configuration.
type ConfigResponse struct {
	Config *domain.PlannerConfiguration `json:"config"`
}

// ValidationResponse indicates validation result.
type ValidationResponse struct {
	Valid  bool     `json:"valid"`
	Errors []string `json:"errors,omitempty"`
}

// HistoryResponse contains configuration version history.
type HistoryResponse struct {
	History []HistoryEntry `json:"history"`
	Total   int            `json:"total"`
}

// HistoryEntry represents a single version in configuration history.
type HistoryEntry struct {
	Version   int    `json:"version"`
	CreatedAt string `json:"created_at"`
	Changes   string `json:"changes,omitempty"`
}

// ServeHTTP routes config requests to appropriate handlers.
func (h *ConfigHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Parse URL path to determine operation
	pathParts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")

	// Expected paths:
	// /api/planning/configs - GET (list), POST (create)
	// /api/planning/configs/:id - GET (retrieve), PUT (update), DELETE (delete)
	// /api/planning/configs/:id/validate - POST (validate)
	// /api/planning/configs/:id/history - GET (version history)

	if len(pathParts) == 3 {
		// /api/planning/configs
		switch r.Method {
		case http.MethodGet:
			h.handleList(w, r)
		case http.MethodPost:
			h.handleCreate(w, r)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
		return
	}

	if len(pathParts) == 4 {
		// /api/planning/configs/:id
		configID := pathParts[3]

		switch r.Method {
		case http.MethodGet:
			h.handleGet(w, r, configID)
		case http.MethodPut:
			h.handleUpdate(w, r, configID)
		case http.MethodDelete:
			h.handleDelete(w, r, configID)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
		return
	}

	if len(pathParts) == 5 {
		// /api/planning/configs/:id/validate or /api/planning/configs/:id/history
		configID := pathParts[3]
		action := pathParts[4]

		switch action {
		case "validate":
			if r.Method == http.MethodPost {
				h.handleValidate(w, r, configID)
			} else {
				http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			}
		case "history":
			if r.Method == http.MethodGet {
				h.handleHistory(w, r, configID)
			} else {
				http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			}
		default:
			http.Error(w, "Unknown action", http.StatusNotFound)
		}
		return
	}

	http.Error(w, "Not found", http.StatusNotFound)
}

func (h *ConfigHandler) handleList(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Listing configurations")

	// TODO: Implement actual list retrieval from database
	response := ConfigListResponse{
		Configs: []ConfigSummary{
			{ID: 1, Name: "default", CreatedAt: "2024-01-01T00:00:00Z", UpdatedAt: "2024-01-01T00:00:00Z"},
		},
		Total: 1,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (h *ConfigHandler) handleGet(w http.ResponseWriter, r *http.Request, configID string) {
	h.log.Debug().Str("config_id", configID).Msg("Getting configuration")

	// TODO: Implement actual config retrieval
	http.Error(w, "Not implemented", http.StatusNotImplemented)
}

func (h *ConfigHandler) handleCreate(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Creating configuration")

	var config domain.PlannerConfiguration
	if err := json.NewDecoder(r.Body).Decode(&config); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// TODO: Implement actual config creation
	response := ConfigResponse{Config: &config}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(response)
}

func (h *ConfigHandler) handleUpdate(w http.ResponseWriter, r *http.Request, configID string) {
	h.log.Debug().Str("config_id", configID).Msg("Updating configuration")

	var config domain.PlannerConfiguration
	if err := json.NewDecoder(r.Body).Decode(&config); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// TODO: Implement actual config update
	response := ConfigResponse{Config: &config}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (h *ConfigHandler) handleDelete(w http.ResponseWriter, r *http.Request, configID string) {
	h.log.Debug().Str("config_id", configID).Msg("Deleting configuration")

	id, err := strconv.Atoi(configID)
	if err != nil {
		http.Error(w, "Invalid config ID", http.StatusBadRequest)
		return
	}

	// TODO: Implement actual config deletion
	h.log.Info().Int("config_id", id).Msg("Configuration deleted (placeholder)")

	w.WriteHeader(http.StatusNoContent)
}

func (h *ConfigHandler) handleValidate(w http.ResponseWriter, r *http.Request, configID string) {
	h.log.Debug().Str("config_id", configID).Msg("Validating configuration")

	// TODO: Implement actual config validation
	response := ValidationResponse{
		Valid:  true,
		Errors: []string{},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (h *ConfigHandler) handleHistory(w http.ResponseWriter, r *http.Request, configID string) {
	h.log.Debug().Str("config_id", configID).Msg("Getting configuration history")

	// TODO: Implement actual history retrieval
	response := HistoryResponse{
		History: []HistoryEntry{
			{Version: 1, CreatedAt: "2024-01-01T00:00:00Z", Changes: "Initial version"},
		},
		Total: 1,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}
