package server

import (
	"encoding/json"
	"net/http"
	"runtime"
)

// handleHealth handles health check requests
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	response := map[string]interface{}{
		"status":  "healthy",
		"version": "1.0.0",
		"service": "arduino-trader",
	}

	s.writeJSON(w, http.StatusOK, response)
}

// handleSystemStatus handles system status requests
func (s *Server) handleSystemStatus(w http.ResponseWriter, r *http.Request) {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	response := map[string]interface{}{
		"status": "running",
		"memory": map[string]interface{}{
			"alloc_mb":       m.Alloc / 1024 / 1024,
			"total_alloc_mb": m.TotalAlloc / 1024 / 1024,
			"sys_mb":         m.Sys / 1024 / 1024,
			"num_gc":         m.NumGC,
		},
		"goroutines": runtime.NumGoroutine(),
	}

	s.writeJSON(w, http.StatusOK, response)
}

// writeJSON writes a JSON response
func (s *Server) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	if err := json.NewEncoder(w).Encode(data); err != nil {
		s.log.Error().Err(err).Msg("Failed to encode JSON response")
	}
}

// writeError writes an error response
func (s *Server) writeError(w http.ResponseWriter, status int, message string) {
	s.writeJSON(w, status, map[string]string{
		"error": message,
	})
}
