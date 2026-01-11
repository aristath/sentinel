// Package server provides the HTTP server and routing for Sentinel.
package server

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os/exec"
	"strconv"
	"strings"

	"github.com/rs/zerolog"
)

// LogHandlers handles log access via journalctl
type LogHandlers struct {
	log zerolog.Logger
}

// NewLogHandlers creates a new log handlers instance
func NewLogHandlers(log zerolog.Logger) *LogHandlers {
	return &LogHandlers{
		log: log.With().Str("component", "log_handlers").Logger(),
	}
}

// LogFileInfo represents information about a log file
type LogFileInfo struct {
	Name         string    `json:"name"`
	Path         string    `json:"path"`
	SizeMB       float64   `json:"size_mb"`
	ModifiedAt   time.Time `json:"modified_at"`
	Lines        int       `json:"lines,omitempty"`
	LastModified string    `json:"last_modified"` // Human-readable
}

// LogListResponse represents the list of available log files
type LogListResponse struct {
	LogFiles []LogFileInfo `json:"log_files"`
	Total    int           `json:"total"`
}

// LogContentResponse represents log content
type LogContentResponse struct {
	Lines  []string `json:"lines"`
	Total  int      `json:"total"`
	Status string   `json:"status"`
}

// HandleListLogs returns available log sources
func (h *LogHandlers) HandleListLogs(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Debug().Msg("Listing log sources")

	// Return single log source from journalctl
	response := LogListResponse{
		LogFiles: []LogFileInfo{
			{
				Name:         "sentinel",
				LastModified: "systemd journal",
			},
		},
		Total: 1,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleGetLogs retrieves log content from journalctl with filtering
func (h *LogHandlers) HandleGetLogs(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Query parameters
	linesParam := r.URL.Query().Get("lines")
	level := strings.ToUpper(r.URL.Query().Get("level"))
	search := r.URL.Query().Get("search")

	// Default to last 100 lines
	lines := 100
	if linesParam != "" {
		if parsed, err := strconv.Atoi(linesParam); err == nil {
			lines = parsed
			if lines > 10000 {
				lines = 10000 // Max 10k lines for safety
			}
		}
	}

	h.log.Debug().
		Int("lines", lines).
		Str("level", level).
		Str("search", search).
		Msg("Getting log content from journalctl")

	// Build journalctl command
	cmd := exec.Command("journalctl", "-u", "sentinel",
		fmt.Sprintf("--lines=%d", lines),
		"--output=short",
		"--no-pager")

	output, err := cmd.Output()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to read journalctl logs")
		http.Error(w, "Failed to read logs", http.StatusInternalServerError)
		return
	}

	// Parse output into lines
	logLines := strings.Split(strings.TrimSpace(string(output)), "\n")
	if len(logLines) == 1 && logLines[0] == "" {
		logLines = []string{}
	}

	totalLines := len(logLines)

	// Apply filters
	filteredLines := h.filterLogs(logLines, level, search)

	response := LogContentResponse{
		Lines:  filteredLines,
		Total:  totalLines,
		Status: "ok",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleGetErrors retrieves only error logs from journalctl
func (h *LogHandlers) HandleGetErrors(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	linesParam := r.URL.Query().Get("lines")

	// Default to last 500 lines for error search
	lines := 500
	if linesParam != "" {
		if parsed, err := strconv.Atoi(linesParam); err == nil {
			lines = parsed
			if lines > 10000 {
				lines = 10000
			}
		}
	}

	h.log.Debug().Int("lines", lines).Msg("Getting error logs from journalctl")

	// Build journalctl command
	cmd := exec.Command("journalctl", "-u", "sentinel",
		fmt.Sprintf("--lines=%d", lines),
		"--output=short",
		"--no-pager")

	output, err := cmd.Output()
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to read journalctl logs")
		http.Error(w, "Failed to read logs", http.StatusInternalServerError)
		return
	}

	// Parse output into lines
	logLines := strings.Split(strings.TrimSpace(string(output)), "\n")
	if len(logLines) == 1 && logLines[0] == "" {
		logLines = []string{}
	}

	totalLines := len(logLines)

	// Filter for ERROR level only
	errorLines := h.filterLogs(logLines, "ERROR", "")

	response := LogContentResponse{
		Lines:  errorLines,
		Total:  totalLines,
		Status: "ok",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// filterLogs filters log lines by level and search term
func (h *LogHandlers) filterLogs(lines []string, level string, search string) []string {
	if level == "" && search == "" {
		return lines
	}

	filtered := make([]string, 0)

	for _, line := range lines {
		// Skip empty lines
		if strings.TrimSpace(line) == "" {
			continue
		}

		// Filter by level if specified
		if level != "" {
			if !h.lineMatchesLevel(line, level) {
				continue
			}
		}

		// Filter by search term if specified
		if search != "" {
			if !strings.Contains(strings.ToLower(line), strings.ToLower(search)) {
				continue
			}
		}

		filtered = append(filtered, line)
	}

	return filtered
}

// lineMatchesLevel checks if a log line matches the specified level
func (h *LogHandlers) lineMatchesLevel(line string, level string) bool {
	// Support both zerolog JSON format and plain text format

	// Check for JSON format: {"level":"error",...}
	if strings.Contains(line, `"level"`) {
		return strings.Contains(strings.ToLower(line), `"level":"`+strings.ToLower(level)+`"`)
	}

	// Check for plain text format: ERROR: message or [ERROR] message
	upperLine := strings.ToUpper(line)
	upperLevel := strings.ToUpper(level)

	return strings.Contains(upperLine, upperLevel+":") ||
		strings.Contains(upperLine, "["+upperLevel+"]") ||
		strings.Contains(upperLine, " "+upperLevel+" ")
}
