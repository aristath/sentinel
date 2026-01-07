package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/modules/planning/config"
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/rs/zerolog"
)

// ConfigHandler handles CRUD operations for planner configurations.
type ConfigHandler struct {
	configRepo   *repository.ConfigRepository
	validator    *config.Validator
	eventManager *events.Manager
	log          zerolog.Logger
}

// NewConfigHandler creates a new config handler.
func NewConfigHandler(
	configRepo *repository.ConfigRepository,
	validator *config.Validator,
	eventManager *events.Manager,
	log zerolog.Logger,
) *ConfigHandler {
	return &ConfigHandler{
		configRepo:   configRepo,
		validator:    validator,
		eventManager: eventManager,
		log:          log.With().Str("handler", "config").Logger(),
	}
}

// ConfigListResponse represents a list of configurations.
type ConfigListResponse struct {
	Configs []ConfigSummary `json:"configs"`
	Total   int             `json:"total"`
}

// ConfigSummary provides a summary of a configuration.
type ConfigSummary struct {
	ID        int64  `json:"id"`
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

	// Expected paths (routes are registered under /planning prefix):
	// /planning/configs - GET (list), POST (create)
	// /planning/configs/:id - GET (retrieve), PUT (update), DELETE (delete)
	// /planning/configs/validate - POST (validate)
	// /planning/configs/:id/history - GET (version history)

	// Remove "planning" prefix if present (routes are registered under /planning)
	// So pathParts will be: ["planning", "configs"] or ["planning", "configs", "id"]
	if len(pathParts) > 0 && pathParts[0] == "planning" {
		pathParts = pathParts[1:]
	}

	if len(pathParts) == 1 && pathParts[0] == "configs" {
		// /planning/configs
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

	if len(pathParts) == 2 && pathParts[0] == "configs" {
		secondPart := pathParts[1]

		if secondPart == "validate" {
			// /planning/configs/validate (no ID - validates request body)
			if r.Method == http.MethodPost {
				// For validate without ID, we'll extract ID from request body if needed
				// For now, pass empty string and let handler extract from body
				h.handleValidate(w, r, "")
			} else {
				http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			}
			return
		}

		// /planning/configs/:id
		configID := secondPart

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

	if len(pathParts) == 3 && pathParts[0] == "configs" {
		// /planning/configs/:id/history
		configID := pathParts[1]
		action := pathParts[2]

		if action == "history" {
			if r.Method == http.MethodGet {
				h.handleHistory(w, r, configID)
			} else {
				http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			}
			return
		}

		http.Error(w, "Invalid path", http.StatusBadRequest)
		return
	}

	http.Error(w, "Not found", http.StatusNotFound)
}

func (h *ConfigHandler) handleList(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Listing configurations")

	configs, err := h.configRepo.ListConfigs()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to list configurations")
		http.Error(w, "Failed to retrieve configurations", http.StatusInternalServerError)
		return
	}

	// Build summaries
	summaries := make([]ConfigSummary, len(configs))
	for i, cfg := range configs {
		summaries[i] = ConfigSummary{
			ID:        cfg.ID,
			Name:      cfg.Name,
			CreatedAt: cfg.CreatedAt.Format(time.RFC3339),
			UpdatedAt: cfg.UpdatedAt.Format(time.RFC3339),
		}
	}

	response := ConfigListResponse{
		Configs: summaries,
		Total:   len(summaries),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (h *ConfigHandler) handleGet(w http.ResponseWriter, r *http.Request, configID string) {
	h.log.Debug().Str("config_id", configID).Msg("Getting configuration")

	id, err := strconv.ParseInt(configID, 10, 64)
	if err != nil {
		http.Error(w, "Invalid config ID", http.StatusBadRequest)
		return
	}

	config, err := h.configRepo.GetConfig(id)
	if err != nil {
		h.log.Error().Err(err).Int64("config_id", id).Msg("Failed to retrieve configuration")
		http.Error(w, "Configuration not found", http.StatusNotFound)
		return
	}

	response := ConfigResponse{Config: config}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// CreateConfigRequest represents a request to create a configuration.
type CreateConfigRequest struct {
	Config    domain.PlannerConfiguration `json:"config"`
	IsDefault bool                        `json:"is_default,omitempty"`
}

func (h *ConfigHandler) handleCreate(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Creating configuration")

	var req CreateConfigRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate configuration before creating
	if h.validator != nil {
		if err := h.validator.Validate(&req.Config); err != nil {
			h.log.Warn().Err(err).Msg("Configuration validation failed")
			http.Error(w, fmt.Sprintf("Invalid configuration: %v", err), http.StatusBadRequest)
			return
		}
	}

	// Create configuration in database
	configID, err := h.configRepo.CreateConfig(&req.Config, req.IsDefault)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to create configuration")
		http.Error(w, "Failed to create configuration", http.StatusInternalServerError)
		return
	}

	h.log.Info().Int64("config_id", configID).Str("name", req.Config.Name).Msg("Configuration created")

	// Emit PLANNER_CONFIG_CHANGED event
	if h.eventManager != nil {
		h.eventManager.Emit(events.PlannerConfigChanged, "planning", map[string]interface{}{
			"config_id": configID,
			"action":    "created",
			"name":      req.Config.Name,
		})
	}

	response := ConfigResponse{Config: &req.Config}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(response)
}

// UpdateConfigRequest represents a request to update a configuration.
type UpdateConfigRequest struct {
	Config     domain.PlannerConfiguration `json:"config"`
	ChangedBy  string                      `json:"changed_by,omitempty"`
	ChangeNote string                      `json:"change_note,omitempty"`
}

func (h *ConfigHandler) handleUpdate(w http.ResponseWriter, r *http.Request, configID string) {
	h.log.Debug().Str("config_id", configID).Msg("Updating configuration")

	id, err := strconv.ParseInt(configID, 10, 64)
	if err != nil {
		http.Error(w, "Invalid config ID", http.StatusBadRequest)
		return
	}

	var req UpdateConfigRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate configuration before updating
	if h.validator != nil {
		if err := h.validator.Validate(&req.Config); err != nil {
			h.log.Warn().Err(err).Int64("config_id", id).Msg("Configuration validation failed")
			http.Error(w, fmt.Sprintf("Invalid configuration: %v", err), http.StatusBadRequest)
			return
		}
	}

	// Default changedBy to "api" if not provided
	changedBy := req.ChangedBy
	if changedBy == "" {
		changedBy = "api"
	}

	// Update configuration in database
	err = h.configRepo.UpdateConfig(id, &req.Config, changedBy, req.ChangeNote)
	if err != nil {
		h.log.Error().Err(err).Int64("config_id", id).Msg("Failed to update configuration")
		http.Error(w, "Failed to update configuration", http.StatusInternalServerError)
		return
	}

	h.log.Info().Int64("config_id", id).Str("name", req.Config.Name).Msg("Configuration updated")

	// Emit PLANNER_CONFIG_CHANGED event
	if h.eventManager != nil {
		h.eventManager.Emit(events.PlannerConfigChanged, "planning", map[string]interface{}{
			"config_id":  id,
			"action":     "updated",
			"name":       req.Config.Name,
			"changed_by": changedBy,
		})
	}

	response := ConfigResponse{Config: &req.Config}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (h *ConfigHandler) handleDelete(w http.ResponseWriter, r *http.Request, configID string) {
	h.log.Debug().Str("config_id", configID).Msg("Deleting configuration")

	id, err := strconv.ParseInt(configID, 10, 64)
	if err != nil {
		http.Error(w, "Invalid config ID", http.StatusBadRequest)
		return
	}

	// Delete configuration from database
	// Note: DeleteConfig checks if the config is the default and returns an error if so
	if err := h.configRepo.DeleteConfig(id); err != nil {
		h.log.Error().Err(err).Int64("config_id", id).Msg("Failed to delete configuration")
		// Check if error is due to trying to delete default config
		if err.Error() == "cannot delete default config" {
			http.Error(w, "Cannot delete the default configuration", http.StatusForbidden)
			return
		}
		http.Error(w, "Failed to delete configuration", http.StatusInternalServerError)
		return
	}

	h.log.Info().Int64("config_id", id).Msg("Configuration deleted")

	// Emit PLANNER_CONFIG_CHANGED event
	if h.eventManager != nil {
		h.eventManager.Emit(events.PlannerConfigChanged, "planning", map[string]interface{}{
			"config_id": id,
			"action":    "deleted",
		})
	}

	w.WriteHeader(http.StatusNoContent)
}

func (h *ConfigHandler) handleValidate(w http.ResponseWriter, r *http.Request, configID string) {
	h.log.Debug().Str("config_id", configID).Msg("Validating configuration")

	id, err := strconv.ParseInt(configID, 10, 64)
	if err != nil {
		http.Error(w, "Invalid config ID", http.StatusBadRequest)
		return
	}

	// Retrieve configuration from database
	config, err := h.configRepo.GetConfig(id)
	if err != nil {
		h.log.Error().Err(err).Int64("config_id", id).Msg("Failed to retrieve configuration")
		http.Error(w, "Configuration not found", http.StatusNotFound)
		return
	}

	// Validate configuration
	var validationErrors []string
	if h.validator != nil {
		if err := h.validator.Validate(config); err != nil {
			// Collect validation errors
			validationErrors = append(validationErrors, err.Error())
			h.log.Warn().Err(err).Int64("config_id", id).Msg("Configuration validation failed")
		}
	}

	response := ValidationResponse{
		Valid:  len(validationErrors) == 0,
		Errors: validationErrors,
	}

	h.log.Info().
		Int64("config_id", id).
		Bool("valid", response.Valid).
		Int("error_count", len(validationErrors)).
		Msg("Configuration validation complete")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (h *ConfigHandler) handleHistory(w http.ResponseWriter, r *http.Request, configID string) {
	h.log.Debug().Str("config_id", configID).Msg("Getting configuration history")

	id, err := strconv.ParseInt(configID, 10, 64)
	if err != nil {
		http.Error(w, "Invalid config ID", http.StatusBadRequest)
		return
	}

	// Retrieve configuration history from database (limit 0 = no limit)
	history, err := h.configRepo.GetConfigHistory(id, 0)
	if err != nil {
		h.log.Error().Err(err).Int64("config_id", id).Msg("Failed to retrieve configuration history")
		http.Error(w, "Failed to retrieve configuration history", http.StatusInternalServerError)
		return
	}

	// Build history entries
	entries := make([]HistoryEntry, len(history))
	for i, record := range history {
		entries[i] = HistoryEntry{
			Version:   i + 1, // Use index as version number (records are sorted by created_at DESC)
			CreatedAt: record.CreatedAt.Format(time.RFC3339),
			Changes:   record.ChangeNote,
		}
	}

	response := HistoryResponse{
		History: entries,
		Total:   len(entries),
	}

	h.log.Info().
		Int64("config_id", id).
		Int("history_count", len(entries)).
		Msg("Configuration history retrieved")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}
