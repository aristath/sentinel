package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

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

// ServeHTTP routes config requests to appropriate handlers.
// Routes are registered as /api/planning/config (singular - single config exists).
// Supported endpoints:
//   - GET /api/planning/config - retrieve the single config
//   - PUT /api/planning/config - update the single config
//   - DELETE /api/planning/config - reset config to defaults
//   - POST /api/planning/config/validate - validate the config
func (h *ConfigHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Parse URL path to determine operation
	// Path will be like: /api/planning/config or /api/planning/config/validate
	pathParts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")

	// Remove "api" and "planning" prefixes if present
	// After removal, pathParts should be: ["config"] or ["config", "validate"]
	startIdx := 0
	for i, part := range pathParts {
		if part == "api" || part == "planning" {
			startIdx = i + 1
		} else {
			break
		}
	}
	if startIdx > 0 {
		pathParts = pathParts[startIdx:]
	}

	// Now pathParts should start with "config"
	if len(pathParts) == 0 || pathParts[0] != "config" {
		http.Error(w, "Not found", http.StatusNotFound)
		return
	}

	// Handle different route patterns
	if len(pathParts) == 1 {
		// /api/planning/config
		switch r.Method {
		case http.MethodGet:
			h.handleGet(w, r)
		case http.MethodPut:
			h.handleUpdate(w, r)
		case http.MethodDelete:
			h.handleDelete(w, r)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
		return
	}

	if len(pathParts) == 2 && pathParts[1] == "validate" {
		// /api/planning/config/validate
		if r.Method == http.MethodPost {
			h.handleValidate(w, r)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
		return
	}

	http.Error(w, "Not found", http.StatusNotFound)
}

func (h *ConfigHandler) handleGet(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Getting planner configuration")

	// Get the single config (ID is ignored by repository)
	config, err := h.configRepo.GetDefaultConfig()
	if err != nil {
		// Log the actual error for debugging
		h.log.Error().
			Err(err).
			Str("error_type", fmt.Sprintf("%T", err)).
			Msg("Failed to retrieve configuration")
		http.Error(w, "Failed to retrieve configuration", http.StatusInternalServerError)
		return
	}

	response := ConfigResponse{Config: config}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// UpdateConfigRequest represents a request to update a configuration.
type UpdateConfigRequest struct {
	Config     domain.PlannerConfiguration `json:"config"`
	ChangedBy  string                      `json:"changed_by,omitempty"`
	ChangeNote string                      `json:"change_note,omitempty"`
}

func (h *ConfigHandler) handleUpdate(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Updating planner configuration")

	var req UpdateConfigRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate configuration before updating
	if h.validator != nil {
		if err := h.validator.Validate(&req.Config); err != nil {
			h.log.Warn().Err(err).Msg("Configuration validation failed")
			http.Error(w, fmt.Sprintf("Invalid configuration: %v", err), http.StatusBadRequest)
			return
		}
	}

	// Default changedBy to "api" if not provided
	changedBy := req.ChangedBy
	if changedBy == "" {
		changedBy = "api"
	}

	// Update configuration in database (ID is ignored, always updates the single config)
	err := h.configRepo.UpdateConfig(1, &req.Config, changedBy, req.ChangeNote)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to update configuration")
		http.Error(w, "Failed to update configuration", http.StatusInternalServerError)
		return
	}

	h.log.Info().Str("name", req.Config.Name).Msg("Configuration updated")

	// Emit PLANNER_CONFIG_CHANGED event
	if h.eventManager != nil {
		h.eventManager.Emit(events.PlannerConfigChanged, "planning", map[string]interface{}{
			"action":     "updated",
			"name":       req.Config.Name,
			"changed_by": changedBy,
		})
	}

	response := ConfigResponse{Config: &req.Config}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (h *ConfigHandler) handleDelete(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Resetting planner configuration to defaults")

	// Delete/reset configuration (resets to defaults, ID is ignored)
	if err := h.configRepo.DeleteConfig(1); err != nil {
		h.log.Error().Err(err).Msg("Failed to reset configuration")
		http.Error(w, "Failed to reset configuration", http.StatusInternalServerError)
		return
	}

	h.log.Info().Msg("Configuration reset to defaults")

	// Emit PLANNER_CONFIG_CHANGED event
	if h.eventManager != nil {
		h.eventManager.Emit(events.PlannerConfigChanged, "planning", map[string]interface{}{
			"action": "reset",
		})
	}

	w.WriteHeader(http.StatusNoContent)
}

func (h *ConfigHandler) handleValidate(w http.ResponseWriter, r *http.Request) {
	h.log.Debug().Msg("Validating planner configuration")

	// Retrieve configuration from database
	config, err := h.configRepo.GetDefaultConfig()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to retrieve configuration")
		http.Error(w, "Failed to retrieve configuration", http.StatusInternalServerError)
		return
	}

	// Validate configuration
	var validationErrors []string
	if h.validator != nil {
		if err := h.validator.Validate(config); err != nil {
			// Collect validation errors
			validationErrors = append(validationErrors, err.Error())
			h.log.Warn().Err(err).Msg("Configuration validation failed")
		}
	}

	response := ValidationResponse{
		Valid:  len(validationErrors) == 0,
		Errors: validationErrors,
	}

	h.log.Info().
		Bool("valid", response.Valid).
		Int("error_count", len(validationErrors)).
		Msg("Configuration validation complete")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}
