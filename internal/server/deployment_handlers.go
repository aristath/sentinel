// Package server provides the HTTP server and routing for Sentinel.
package server

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"

	"github.com/aristath/sentinel/internal/deployment"
)

// DeploymentHandlers handles deployment-related HTTP endpoints
type DeploymentHandlers struct {
	deploymentManager *deployment.Manager
	log               zerolog.Logger
}

// NewDeploymentHandlers creates new deployment handlers
func NewDeploymentHandlers(deploymentManager *deployment.Manager, log zerolog.Logger) *DeploymentHandlers {
	return &DeploymentHandlers{
		deploymentManager: deploymentManager,
		log:               log.With().Str("component", "deployment_handlers").Logger(),
	}
}

// RegisterRoutes registers deployment routes
func (h *DeploymentHandlers) RegisterRoutes(r chi.Router) {
	r.Route("/system/deployment", func(r chi.Router) {
		r.Get("/status", h.HandleGetStatus)
		r.Post("/deploy", h.HandleTriggerDeployment)
		r.Post("/hard-update", h.HandleHardUpdate)
	})
}

// HandleGetStatus returns the current deployment status
func (h *DeploymentHandlers) HandleGetStatus(w http.ResponseWriter, r *http.Request) {
	status, err := h.deploymentManager.GetStatus()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to get deployment status")
		http.Error(w, "Failed to get deployment status", http.StatusInternalServerError)
		return
	}

	uptime, err := h.deploymentManager.GetUptime()
	if err != nil {
		h.log.Warn().Err(err).Msg("Failed to get uptime")
	}

	response := map[string]interface{}{
		"status": status,
		"uptime": uptime.String(),
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(response); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode deployment status response")
		http.Error(w, "Failed to encode response", http.StatusInternalServerError)
		return
	}
}

// HandleTriggerDeployment triggers a manual deployment
func (h *DeploymentHandlers) HandleTriggerDeployment(w http.ResponseWriter, r *http.Request) {
	h.log.Info().Msg("Manual deployment triggered via API")

	result, err := h.deploymentManager.Deploy()
	if err != nil {
		h.log.Error().Err(err).Msg("Deployment failed")
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"success": false,
			"error":   err.Error(),
		})
		return
	}

	response := map[string]interface{}{
		"success":         result.Success,
		"deployed":        result.Deployed,
		"commit_before":   result.CommitBefore,
		"commit_after":    result.CommitAfter,
		"services":        result.ServicesDeployed,
		"sketch_deployed": result.SketchDeployed,
		"duration":        result.Duration.String(),
		"error":           result.Error,
	}

	w.Header().Set("Content-Type", "application/json")
	if result.Success {
		w.WriteHeader(http.StatusOK)
	} else {
		w.WriteHeader(http.StatusInternalServerError)
	}

	if err := json.NewEncoder(w).Encode(response); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode deployment response")
		http.Error(w, "Failed to encode response", http.StatusInternalServerError)
		return
	}
}

// HandleHardUpdate triggers a hard update (forces all deployments without change detection)
func (h *DeploymentHandlers) HandleHardUpdate(w http.ResponseWriter, r *http.Request) {
	h.log.Info().Msg("Hard update triggered via API")

	result, err := h.deploymentManager.HardUpdate()
	if err != nil {
		h.log.Error().Err(err).Msg("Hard update failed")
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":  "error",
			"success": false,
			"error":   err.Error(),
			"message": err.Error(),
		})
		return
	}

	status := "success"
	if !result.Success {
		status = "error"
	}
	message := "Hard update completed successfully"
	if result.Error != "" {
		message = result.Error
	}

	response := map[string]interface{}{
		"status":          status,
		"success":         result.Success,
		"deployed":        result.Deployed,
		"commit_before":   result.CommitBefore,
		"commit_after":    result.CommitAfter,
		"services":        result.ServicesDeployed,
		"sketch_deployed": result.SketchDeployed,
		"duration":        result.Duration.String(),
		"error":           result.Error,
		"message":         message,
	}

	w.Header().Set("Content-Type", "application/json")
	if result.Success {
		w.WriteHeader(http.StatusOK)
	} else {
		w.WriteHeader(http.StatusInternalServerError)
	}

	if err := json.NewEncoder(w).Encode(response); err != nil {
		h.log.Error().Err(err).Msg("Failed to encode hard update response")
		http.Error(w, "Failed to encode response", http.StatusInternalServerError)
		return
	}
}
