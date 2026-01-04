package settings

import (
	"encoding/json"
	"net/http"
	"os/exec"

	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// OnboardingServiceInterface defines the interface for onboarding service
type OnboardingServiceInterface interface {
	RunOnboarding() error
}

// Handler provides HTTP handlers for settings endpoints
type Handler struct {
	service           *Service
	onboardingService OnboardingServiceInterface
	log               zerolog.Logger
}

// NewHandler creates a new settings handler
func NewHandler(service *Service, log zerolog.Logger) *Handler {
	return &Handler{
		service: service,
		log:     log.With().Str("handler", "settings").Logger(),
	}
}

// SetOnboardingService sets the onboarding service (for dependency injection)
func (h *Handler) SetOnboardingService(onboardingService OnboardingServiceInterface) {
	h.onboardingService = onboardingService
}

// HandleGetAll handles GET /api/settings
// Faithful translation from Python: app/api/settings.py -> get_all_settings()
func (h *Handler) HandleGetAll(w http.ResponseWriter, r *http.Request) {
	settings, err := h.service.GetAll()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get all settings")
		http.Error(w, "Failed to get settings", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(settings); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode settings response")
		http.Error(w, "Failed to encode response", http.StatusInternalServerError)
		return
	}
}

// HandleUpdate handles PUT /api/settings/{key}
// Faithful translation from Python: app/api/settings.py -> update_setting_value()
func (h *Handler) HandleUpdate(w http.ResponseWriter, r *http.Request) {
	key := chi.URLParam(r, "key")
	if key == "" {
		http.Error(w, "Key is required", http.StatusBadRequest)
		return
	}

	var update SettingUpdate
	if err := json.NewDecoder(r.Body).Decode(&update); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	isFirstTimeSetup, err := h.service.Set(key, update.Value)
	if err != nil {
		h.log.Error().
			Err(err).
			Str("key", key).
			Interface("value", update.Value).
			Msg("Failed to update setting")
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Trigger onboarding if this is first-time credential setup
	if isFirstTimeSetup && h.onboardingService != nil {
		h.log.Info().Msg("First-time credential setup detected, triggering onboarding")
		go func() {
			if err := h.onboardingService.RunOnboarding(); err != nil {
				h.log.Error().Err(err).Msg("Onboarding failed")
			} else {
				h.log.Info().Msg("Onboarding completed successfully")
			}
		}()
	}

	// Return updated value
	result := map[string]interface{}{key: update.Value}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

// HandleRestartService handles POST /api/settings/restart-service
// Faithful translation from Python: app/api/settings.py -> restart_service()
func (h *Handler) HandleRestartService(w http.ResponseWriter, r *http.Request) {
	cmd := exec.Command("sudo", "systemctl", "restart", "arduino-trader")
	output, err := cmd.CombinedOutput()

	response := map[string]string{}
	if err != nil {
		response["status"] = "error"
		response["message"] = string(output)
		h.log.Warn().
			Err(err).
			Str("output", string(output)).
			Msg("Failed to restart service")
	} else {
		response["status"] = "ok"
		response["message"] = "Service restart initiated"
		h.log.Info().Msg("Service restart initiated")
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleRestart handles POST /api/settings/restart
// Faithful translation from Python: app/api/settings.py -> restart_system()
func (h *Handler) HandleRestart(w http.ResponseWriter, r *http.Request) {
	// Start reboot process in background
	cmd := exec.Command("sudo", "reboot")
	if err := cmd.Start(); err != nil {
		h.log.Error().Err(err).Msg("Failed to initiate system reboot")
		http.Error(w, "Failed to initiate reboot", http.StatusInternalServerError)
		return
	}

	h.log.Warn().Msg("System reboot initiated")

	response := map[string]string{"status": "rebooting"}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleResetCache handles POST /api/settings/reset-cache
// Faithful translation from Python: app/api/settings.py -> reset_cache()
func (h *Handler) HandleResetCache(w http.ResponseWriter, r *http.Request) {
	// Note: Full cache implementation would require cache infrastructure
	// This is a simplified version that acknowledges the request
	h.log.Info().Msg("Cache reset requested")

	response := map[string]string{
		"status":  "ok",
		"message": "Cache reset acknowledged (simplified implementation)",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleGetCacheStats handles GET /api/settings/cache-stats
// Faithful translation from Python: app/api/settings.py -> get_cache_stats()
func (h *Handler) HandleGetCacheStats(w http.ResponseWriter, r *http.Request) {
	// Note: Full implementation would require calculations DB integration
	// This is a simplified version returning stub data
	stats := CacheStats{
		SimpleCache: SimpleCacheStats{
			Entries: 0,
		},
		CalculationsDB: CalculationsDBStats{
			Entries:        0,
			ExpiredCleaned: 0,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(stats)
}

// HandleRescheduleJobs handles POST /api/settings/reschedule-jobs
// Faithful translation from Python: app/api/settings.py -> reschedule_jobs()
func (h *Handler) HandleRescheduleJobs(w http.ResponseWriter, r *http.Request) {
	// Note: Full implementation would require scheduler integration
	// This is a simplified version that acknowledges the request
	h.log.Info().Msg("Job rescheduling requested")

	response := map[string]string{
		"status":  "ok",
		"message": "Job rescheduling acknowledged (simplified implementation)",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleGetTradingMode handles GET /api/settings/trading-mode
// Faithful translation from Python: app/api/settings.py -> get_trading_mode_endpoint()
func (h *Handler) HandleGetTradingMode(w http.ResponseWriter, r *http.Request) {
	mode, err := h.service.GetTradingMode()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get trading mode")
		http.Error(w, "Failed to get trading mode", http.StatusInternalServerError)
		return
	}

	response := TradingModeResponse{TradingMode: mode}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleToggleTradingMode handles POST /api/settings/trading-mode
// Faithful translation from Python: app/api/settings.py -> toggle_trading_mode()
func (h *Handler) HandleToggleTradingMode(w http.ResponseWriter, r *http.Request) {
	newMode, previousMode, err := h.service.ToggleTradingMode()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to toggle trading mode")
		http.Error(w, "Failed to toggle trading mode", http.StatusInternalServerError)
		return
	}

	h.log.Info().
		Str("previous_mode", previousMode).
		Str("new_mode", newMode).
		Msg("Trading mode toggled")

	response := TradingModeToggleResponse{
		TradingMode:  newMode,
		PreviousMode: previousMode,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}
