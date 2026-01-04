package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/planning/config"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/planning/repository"
	"github.com/rs/zerolog"
)

// ConfigHandler handles CRUD operations for planner configurations.
type ConfigHandler struct {
	configRepo *repository.ConfigRepository
	validator  *config.Validator
	log        zerolog.Logger
}

// NewConfigHandler creates a new config handler.
func NewConfigHandler(
	configRepo *repository.ConfigRepository,
	validator *config.Validator,
	log zerolog.Logger,
) *ConfigHandler {
	return &ConfigHandler{
		configRepo: configRepo,
		validator:  validator,
		log:        log.With().Str("handler", "config").Logger(),
	}
}

// ConfigListResponse represents a list of configurations.
type ConfigListResponse struct {
	Configs []ConfigSummary `json:"configs"`
	Total   int             `json:"total"`
}

// ConfigSummary provides a summary of a configuration.
type ConfigSummary struct {
	ID        int64   `json:"id"`
	Name      string  `json:"name"`
	BucketID  *string `json:"bucket_id,omitempty"`
	CreatedAt string  `json:"created_at"`
	UpdatedAt string  `json:"updated_at"`
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
	// /api/planning/configs/bucket/:bucket_id - GET (retrieve by bucket)

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
		// /api/planning/configs/:id or /api/planning/configs/bucket
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
		// or /api/planning/configs/bucket/:bucket_id
		resourceType := pathParts[3]
		resourceID := pathParts[4]

		if resourceType == "bucket" {
			// /api/planning/configs/bucket/:bucket_id
			if r.Method == http.MethodGet {
				h.handleGetByBucket(w, r, resourceID)
			} else {
				http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			}
			return
		}

		// Otherwise it's /api/planning/configs/:id/validate or history
		configID := resourceType
		action := resourceID

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
			BucketID:  cfg.BucketID,
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

func (h *ConfigHandler) handleGetByBucket(w http.ResponseWriter, r *http.Request, bucketID string) {
	h.log.Debug().Str("bucket_id", bucketID).Msg("Getting configuration by bucket")

	config, err := h.configRepo.GetByBucket(bucketID)
	if err != nil {
		h.log.Error().Err(err).Str("bucket_id", bucketID).Msg("Failed to retrieve configuration")
		http.Error(w, "Configuration not found", http.StatusNotFound)
		return
	}

	if config == nil {
		// No bucket-specific config found, return 404
		http.Error(w, "No configuration found for this bucket", http.StatusNotFound)
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
