package deployment

import (
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// BinaryDeployer handles atomic binary deployment
type BinaryDeployer struct {
	log Logger
}

// NewBinaryDeployer creates a new binary deployer
func NewBinaryDeployer(log Logger) *BinaryDeployer {
	return &BinaryDeployer{
		log: log,
	}
}

// DeployBinary performs an atomic binary swap
func (d *BinaryDeployer) DeployBinary(tempBinaryPath string, deployDir string, binaryName string, backup bool) error {
	targetPath := filepath.Join(deployDir, binaryName)

	// Ensure deploy directory exists
	if err := os.MkdirAll(deployDir, 0755); err != nil {
		return fmt.Errorf("failed to create deploy directory: %w", err)
	}

	// Backup current binary if it exists and backup is requested
	if backup {
		if err := d.BackupCurrentBinary(deployDir, binaryName); err != nil {
			d.log.Warn().
				Err(err).
				Msg("Failed to backup current binary, continuing anyway")
		}
	}

	// Perform atomic swap using rename (atomic on most filesystems)
	// First, try to remove existing binary if it exists
	if _, err := os.Stat(targetPath); err == nil {
		// Remove old binary (rename is atomic, but we want to ensure clean state)
		if err := os.Remove(targetPath); err != nil {
			return fmt.Errorf("failed to remove existing binary: %w", err)
		}
	}

	// Atomic rename (rename is atomic on Unix filesystems)
	if err := os.Rename(tempBinaryPath, targetPath); err != nil {
		return fmt.Errorf("failed to deploy binary (atomic swap): %w", err)
	}

	d.log.Info().
		Str("binary", binaryName).
		Str("target", targetPath).
		Msg("Successfully deployed binary (atomic swap)")

	return nil
}

// BackupCurrentBinary creates a backup of the current binary
func (d *BinaryDeployer) BackupCurrentBinary(deployDir string, binaryName string) error {
	binaryPath := filepath.Join(deployDir, binaryName)

	// Check if binary exists
	if _, err := os.Stat(binaryPath); os.IsNotExist(err) {
		// No binary to backup
		return nil
	}

	// Create backup filename with timestamp
	timestamp := time.Now().Format("20060102-150405")
	backupName := fmt.Sprintf("%s.backup.%s", binaryName, timestamp)
	backupPath := filepath.Join(deployDir, backupName)

	// Copy binary to backup location
	data, err := os.ReadFile(binaryPath)
	if err != nil {
		return fmt.Errorf("failed to read binary for backup: %w", err)
	}

	if err := os.WriteFile(backupPath, data, 0755); err != nil {
		return fmt.Errorf("failed to write backup: %w", err)
	}

	d.log.Debug().
		Str("binary", binaryName).
		Str("backup", backupPath).
		Msg("Created binary backup")

	// Clean up old backups (keep last 5)
	if err := d.cleanupOldBackups(deployDir, binaryName); err != nil {
		d.log.Warn().
			Err(err).
			Msg("Failed to cleanup old backups")
	}

	return nil
}

// cleanupOldBackups removes old backup files, keeping the most recent ones
func (d *BinaryDeployer) cleanupOldBackups(deployDir string, binaryName string) error {
	pattern := filepath.Join(deployDir, fmt.Sprintf("%s.backup.*", binaryName))
	matches, err := filepath.Glob(pattern)
	if err != nil {
		return err
	}

	// Keep last 5 backups
	if len(matches) <= 5 {
		return nil
	}

	// Sort by modification time (most recent first)
	type backupFile struct {
		path string
		time time.Time
	}

	files := make([]backupFile, 0, len(matches))
	for _, match := range matches {
		info, err := os.Stat(match)
		if err != nil {
			continue
		}
		files = append(files, backupFile{
			path: match,
			time: info.ModTime(),
		})
	}

	// Sort by time (descending) - simple bubble sort for small lists
	for i := 0; i < len(files)-1; i++ {
		for j := i + 1; j < len(files); j++ {
			if files[i].time.Before(files[j].time) {
				files[i], files[j] = files[j], files[i]
			}
		}
	}

	// Remove oldest backups
	toRemove := files[5:]
	for _, file := range toRemove {
		if err := os.Remove(file.path); err != nil {
			d.log.Warn().
				Err(err).
				Str("path", file.path).
				Msg("Failed to remove old backup")
		} else {
			d.log.Debug().
				Str("path", file.path).
				Msg("Removed old backup")
		}
	}

	return nil
}
