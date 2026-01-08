// Package server provides the HTTP server and routing for Sentinel.
package server

import (
	"bufio"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// LogHandlers handles log file access and filtering
type LogHandlers struct {
	log     zerolog.Logger
	dataDir string
}

// NewLogHandlers creates a new log handlers instance
func NewLogHandlers(log zerolog.Logger, dataDir string) *LogHandlers {
	return &LogHandlers{
		log:     log.With().Str("component", "log_handlers").Logger(),
		dataDir: dataDir,
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

// LogContentResponse represents log file content
type LogContentResponse struct {
	FileName string   `json:"file_name"`
	Lines    []string `json:"lines"`
	Total    int      `json:"total"`
	Filtered int      `json:"filtered"`
}

// HandleListLogs lists available log files
func (h *LogHandlers) HandleListLogs(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.log.Debug().Msg("Listing log files")

	logsDir := filepath.Join(h.dataDir, "logs")

	// Check if logs directory exists
	if _, err := os.Stat(logsDir); os.IsNotExist(err) {
		// No logs directory, return empty list
		response := LogListResponse{
			LogFiles: []LogFileInfo{},
			Total:    0,
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
		return
	}

	// Read log files
	entries, err := os.ReadDir(logsDir)
	if err != nil {
		h.log.Error().Err(err).Msg("Failed to read logs directory")
		http.Error(w, "Failed to read logs directory", http.StatusInternalServerError)
		return
	}

	logFiles := make([]LogFileInfo, 0)
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		// Only include .log files
		if !strings.HasSuffix(entry.Name(), ".log") {
			continue
		}

		info, err := entry.Info()
		if err != nil {
			h.log.Warn().Err(err).Str("file", entry.Name()).Msg("Failed to get file info")
			continue
		}

		logFile := LogFileInfo{
			Name:         entry.Name(),
			Path:         filepath.Join(logsDir, entry.Name()),
			SizeMB:       float64(info.Size()) / 1024 / 1024,
			ModifiedAt:   info.ModTime(),
			LastModified: info.ModTime().Format("2006-01-02 15:04:05"),
		}

		logFiles = append(logFiles, logFile)
	}

	// Sort by modification time (newest first)
	sort.Slice(logFiles, func(i, j int) bool {
		return logFiles[i].ModifiedAt.After(logFiles[j].ModifiedAt)
	})

	response := LogListResponse{
		LogFiles: logFiles,
		Total:    len(logFiles),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleGetLogs retrieves log content with filtering
func (h *LogHandlers) HandleGetLogs(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Query parameters
	logFile := r.URL.Query().Get("file")
	linesParam := r.URL.Query().Get("lines")
	level := strings.ToUpper(r.URL.Query().Get("level"))
	search := r.URL.Query().Get("search")

	if logFile == "" {
		http.Error(w, "Missing 'file' parameter", http.StatusBadRequest)
		return
	}

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
		Str("file", logFile).
		Int("lines", lines).
		Str("level", level).
		Str("search", search).
		Msg("Getting log content")

	// Validate log file path (prevent directory traversal)
	if strings.Contains(logFile, "..") || strings.Contains(logFile, "/") {
		http.Error(w, "Invalid file name", http.StatusBadRequest)
		return
	}

	logsDir := filepath.Join(h.dataDir, "logs")
	logPath := filepath.Join(logsDir, logFile)

	// Verify file exists and is within logs directory
	if !strings.HasPrefix(logPath, logsDir) {
		http.Error(w, "Invalid file path", http.StatusBadRequest)
		return
	}

	if _, err := os.Stat(logPath); os.IsNotExist(err) {
		http.Error(w, "Log file not found", http.StatusNotFound)
		return
	}

	// Read log file (last N lines)
	logLines, err := h.readLastLines(logPath, lines)
	if err != nil {
		h.log.Error().Err(err).Str("file", logFile).Msg("Failed to read log file")
		http.Error(w, "Failed to read log file", http.StatusInternalServerError)
		return
	}

	totalLines := len(logLines)

	// Apply filters
	filteredLines := h.filterLogs(logLines, level, search)

	response := LogContentResponse{
		FileName: logFile,
		Lines:    filteredLines,
		Total:    totalLines,
		Filtered: len(filteredLines),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// HandleGetErrors retrieves only error logs
func (h *LogHandlers) HandleGetErrors(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	logFile := r.URL.Query().Get("file")
	linesParam := r.URL.Query().Get("lines")

	if logFile == "" {
		http.Error(w, "Missing 'file' parameter", http.StatusBadRequest)
		return
	}

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

	h.log.Debug().Str("file", logFile).Int("lines", lines).Msg("Getting error logs")

	// Validate log file path
	if strings.Contains(logFile, "..") || strings.Contains(logFile, "/") {
		http.Error(w, "Invalid file name", http.StatusBadRequest)
		return
	}

	logsDir := filepath.Join(h.dataDir, "logs")
	logPath := filepath.Join(logsDir, logFile)

	if !strings.HasPrefix(logPath, logsDir) {
		http.Error(w, "Invalid file path", http.StatusBadRequest)
		return
	}

	if _, err := os.Stat(logPath); os.IsNotExist(err) {
		http.Error(w, "Log file not found", http.StatusNotFound)
		return
	}

	// Read log file
	logLines, err := h.readLastLines(logPath, lines)
	if err != nil {
		h.log.Error().Err(err).Str("file", logFile).Msg("Failed to read log file")
		http.Error(w, "Failed to read log file", http.StatusInternalServerError)
		return
	}

	totalLines := len(logLines)

	// Filter for ERROR level only
	errorLines := h.filterLogs(logLines, "ERROR", "")

	response := LogContentResponse{
		FileName: logFile,
		Lines:    errorLines,
		Total:    totalLines,
		Filtered: len(errorLines),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// readLastLines efficiently reads the last N lines from a file
func (h *LogHandlers) readLastLines(filePath string, n int) ([]string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	// Get file size
	stat, err := file.Stat()
	if err != nil {
		return nil, err
	}

	fileSize := stat.Size()

	// For small files, read entire file
	if fileSize < 1024*1024 { // < 1MB
		return h.readAllLines(file)
	}

	// For large files, read from end
	return h.readLastLinesReverse(file, fileSize, n)
}

// readAllLines reads all lines from a file
func (h *LogHandlers) readAllLines(file *os.File) ([]string, error) {
	var lines []string
	scanner := bufio.NewScanner(file)

	// Increase buffer size for long log lines
	buf := make([]byte, 0, 64*1024)
	scanner.Buffer(buf, 1024*1024) // 1MB max line length

	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}

	if err := scanner.Err(); err != nil {
		return nil, err
	}

	return lines, nil
}

// readLastLinesReverse reads last N lines by seeking from end of file
func (h *LogHandlers) readLastLinesReverse(file *os.File, fileSize int64, n int) ([]string, error) {
	// Start from end of file, read backwards in chunks
	const chunkSize = 8192

	// Calculate starting position (read last ~100KB for last N lines)
	startPos := fileSize - (chunkSize * 12)
	if startPos < 0 {
		startPos = 0
	}

	// Seek to starting position
	_, err := file.Seek(startPos, io.SeekStart)
	if err != nil {
		return nil, err
	}

	// Read from starting position to end
	scanner := bufio.NewScanner(file)
	buf := make([]byte, 0, 64*1024)
	scanner.Buffer(buf, 1024*1024)

	allLines := make([]string, 0)
	for scanner.Scan() {
		allLines = append(allLines, scanner.Text())
	}

	if err := scanner.Err(); err != nil {
		return nil, err
	}

	// Return last N lines
	if len(allLines) <= n {
		return allLines, nil
	}

	return allLines[len(allLines)-n:], nil
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
