package deployment

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// DeploymentLock handles file-based locking for deployments
type DeploymentLock struct {
	lockPath string
	log      Logger
}

// LockInfo contains lock file information
type LockInfo struct {
	PID       int       `json:"pid"`
	Timestamp time.Time `json:"timestamp"`
	ProcessID string    `json:"process_id,omitempty"`
}

// Logger interface for logging (to avoid circular dependency)
type Logger interface {
	Debug() LogEvent
	Info() LogEvent
	Warn() LogEvent
	Error() LogEvent
}

// LogEvent interface
type LogEvent interface {
	Str(string, string) LogEvent
	Int(string, int) LogEvent
	Err(error) LogEvent
	Dur(string, time.Duration) LogEvent
	Bool(string, bool) LogEvent
	Interface(string, interface{}) LogEvent
	Msg(string)
}

// NewDeploymentLock creates a new deployment lock manager
func NewDeploymentLock(lockPath string, log Logger) *DeploymentLock {
	return &DeploymentLock{
		lockPath: lockPath,
		log:      log,
	}
}

// AcquireLock attempts to acquire a deployment lock
// Returns error if lock exists and is not stale
func (l *DeploymentLock) AcquireLock(timeout time.Duration) error {
	// Check if lock exists
	if info, err := l.CheckLock(); err == nil && info != nil {
		// Lock exists - check if stale
		age := time.Since(info.Timestamp)
		if age < timeout {
			return fmt.Errorf("deployment lock exists (age: %v, timeout: %v)", age, timeout)
		}

		// Lock is stale - remove it
		l.log.Warn().
			Str("age", age.String()).
			Msg("Removing stale deployment lock")
		if err := os.Remove(l.lockPath); err != nil {
			return fmt.Errorf("failed to remove stale lock: %w", err)
		}
	}

	// Create lock file
	info := LockInfo{
		PID:       os.Getpid(),
		Timestamp: time.Now(),
		ProcessID: fmt.Sprintf("%d", os.Getpid()),
	}

	data, err := json.MarshalIndent(info, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal lock info: %w", err)
	}

	// Create directory if it doesn't exist
	dir := filepath.Dir(l.lockPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create lock directory: %w", err)
	}

	if err := os.WriteFile(l.lockPath, data, 0644); err != nil {
		return fmt.Errorf("failed to create lock file: %w", err)
	}

	l.log.Debug().
		Str("lock_path", l.lockPath).
		Int("pid", info.PID).
		Msg("Deployment lock acquired")

	return nil
}

// ReleaseLock releases the deployment lock
func (l *DeploymentLock) ReleaseLock() error {
	if err := os.Remove(l.lockPath); err != nil {
		if os.IsNotExist(err) {
			// Lock already released - not an error
			return nil
		}
		return fmt.Errorf("failed to release lock: %w", err)
	}

	l.log.Debug().
		Str("lock_path", l.lockPath).
		Msg("Deployment lock released")

	return nil
}

// CheckLock checks if lock exists and returns lock info
func (l *DeploymentLock) CheckLock() (*LockInfo, error) {
	data, err := os.ReadFile(l.lockPath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil // No lock exists
		}
		return nil, fmt.Errorf("failed to read lock file: %w", err)
	}

	var info LockInfo
	if err := json.Unmarshal(data, &info); err != nil {
		return nil, fmt.Errorf("failed to parse lock file: %w", err)
	}

	return &info, nil
}

// IsProcessAlive checks if the process with given PID is still running
func (l *DeploymentLock) IsProcessAlive(pid int) bool {
	// On Unix systems, sending signal 0 doesn't kill the process but checks if it exists
	process, err := os.FindProcess(pid)
	if err != nil {
		return false
	}

	// Send signal 0 to check if process exists
	err = process.Signal(os.Signal(nil))
	return err == nil
}

// CleanupStaleLock removes a stale lock if the process is not alive
func (l *DeploymentLock) CleanupStaleLock(timeout time.Duration) error {
	info, err := l.CheckLock()
	if err != nil {
		return err
	}
	if info == nil {
		return nil // No lock exists
	}

	// Check if process is alive
	if l.IsProcessAlive(info.PID) {
		// Process is alive - check if lock is stale
		age := time.Since(info.Timestamp)
		if age < timeout {
			// Lock is valid
			return nil
		}
		// Process exists but lock is stale - remove it anyway
		l.log.Warn().
			Int("pid", info.PID).
			Str("age", age.String()).
			Msg("Removing stale lock (process may be hung)")
	}

	// Process is not alive or lock is stale - remove lock
	return l.ReleaseLock()
}
