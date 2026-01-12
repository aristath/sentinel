package deployment

import (
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/aristath/sentinel/pkg/embedded"
)

// AppLabDeployer handles Arduino App Lab deployment
// Replaces the old SketchDeployer with full App Lab support
type AppLabDeployer struct {
	log Logger
}

// SketchDeployer is an alias for AppLabDeployer (backwards compatibility)
type SketchDeployer = AppLabDeployer

// AppName is the name of the display app
const AppName = "sentinel-display"

// AppDir is the directory where the app is deployed
const AppDir = "/home/arduino/ArduinoApps/" + AppName

// NewSketchDeployer creates a new App Lab deployer (backwards compatible name)
func NewSketchDeployer(log Logger) *AppLabDeployer {
	return NewAppLabDeployer(log)
}

// NewAppLabDeployer creates a new App Lab deployer
func NewAppLabDeployer(log Logger) *AppLabDeployer {
	return &AppLabDeployer{
		log: log,
	}
}

// DeployApp deploys the full Arduino App Lab application
// This includes app.yaml, python/main.py, and the sketch directory
func (d *AppLabDeployer) DeployApp() error {
	d.log.Info().
		Str("target", AppDir).
		Msg("Deploying Arduino App Lab application")

	// Get the display directory from embedded files
	displayFS, err := fs.Sub(embedded.Files, "display")
	if err != nil {
		return fmt.Errorf("failed to get display directory from embedded files: %w", err)
	}

	// Create target directory
	if err := os.MkdirAll(AppDir, 0755); err != nil {
		return fmt.Errorf("failed to create target directory: %w", err)
	}

	// Extract all App Lab files to target directory
	if err := d.extractAppFiles(displayFS, AppDir); err != nil {
		return fmt.Errorf("failed to extract App Lab files: %w", err)
	}

	// Verify required files exist
	requiredFiles := []string{"app.yaml", "python/main.py", "sketch/sketch.ino", "sketch/sketch.yaml"}
	for _, file := range requiredFiles {
		filePath := filepath.Join(AppDir, file)
		if _, err := os.Stat(filePath); os.IsNotExist(err) {
			return fmt.Errorf("required file not found after extraction: %s", filePath)
		}
	}

	d.log.Info().
		Str("target", AppDir).
		Msg("Arduino App Lab application deployed successfully")

	return nil
}

// DeployAndRestart deploys the app and restarts it using arduino-app-cli
func (d *AppLabDeployer) DeployAndRestart() error {
	// First, stop the app if it's running
	if err := d.StopApp(); err != nil {
		d.log.Warn().Err(err).Msg("Failed to stop app (may not be running)")
		// Continue anyway - app might not be running
	}

	// Deploy the app files
	if err := d.DeployApp(); err != nil {
		return fmt.Errorf("failed to deploy app: %w", err)
	}

	// Wait a moment for files to settle
	time.Sleep(500 * time.Millisecond)

	// Start the app
	if err := d.StartApp(); err != nil {
		return fmt.Errorf("failed to start app: %w", err)
	}

	return nil
}

// StartApp starts the display app using arduino-app-cli
func (d *AppLabDeployer) StartApp() error {
	d.log.Info().Str("app", AppName).Msg("Starting Arduino App Lab application")

	// Use arduino-app-cli to start the app
	// Command: arduino-app-cli app start .
	cmd := exec.Command("arduino-app-cli", "app", "start", ".")
	cmd.Dir = AppDir

	output, err := cmd.CombinedOutput()
	if err != nil {
		d.log.Error().
			Err(err).
			Str("output", string(output)).
			Msg("Failed to start app")
		return fmt.Errorf("failed to start app: %w (output: %s)", err, string(output))
	}

	d.log.Info().
		Str("app", AppName).
		Str("output", string(output)).
		Msg("Arduino App Lab application started")

	return nil
}

// StopApp stops the display app using arduino-app-cli
func (d *AppLabDeployer) StopApp() error {
	d.log.Info().Str("app", AppName).Msg("Stopping Arduino App Lab application")

	// Use arduino-app-cli to stop the app
	// Command: arduino-app-cli app stop .
	cmd := exec.Command("arduino-app-cli", "app", "stop", ".")
	cmd.Dir = AppDir

	output, err := cmd.CombinedOutput()
	if err != nil {
		d.log.Warn().
			Err(err).
			Str("output", string(output)).
			Msg("Failed to stop app (may not be running)")
		return fmt.Errorf("failed to stop app: %w (output: %s)", err, string(output))
	}

	d.log.Info().
		Str("app", AppName).
		Str("output", string(output)).
		Msg("Arduino App Lab application stopped")

	return nil
}

// RestartApp restarts the display app
func (d *AppLabDeployer) RestartApp() error {
	if err := d.StopApp(); err != nil {
		d.log.Warn().Err(err).Msg("Failed to stop app during restart")
		// Continue anyway
	}

	time.Sleep(500 * time.Millisecond)

	return d.StartApp()
}

// IsAppRunning checks if the display app is running
func (d *AppLabDeployer) IsAppRunning() bool {
	// Check if the app directory exists and has required files
	if _, err := os.Stat(filepath.Join(AppDir, "app.yaml")); os.IsNotExist(err) {
		return false
	}

	// Try to get app status using arduino-app-cli
	// Note: This is a best-effort check - arduino-app-cli may not have a status command
	cmd := exec.Command("arduino-app-cli", "app", "logs", ".")
	cmd.Dir = AppDir

	err := cmd.Run()
	return err == nil
}

// DeploySketch is kept for backwards compatibility but now deploys the full app
func (d *AppLabDeployer) DeploySketch(sketchPath string) error {
	// For backwards compatibility, just deploy the full app
	return d.DeployApp()
}

// extractAppFiles extracts all files from embed.FS to target directory
func (d *AppLabDeployer) extractAppFiles(sourceFS fs.FS, targetDir string) error {
	return fs.WalkDir(sourceFS, ".", func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}

		// Skip the root directory itself if it's just "."
		if path == "." && entry.IsDir() {
			return nil
		}

		targetPath := filepath.Join(targetDir, path)

		if entry.IsDir() {
			// Create directory
			return os.MkdirAll(targetPath, 0755)
		}

		// Extract file
		return d.extractFile(sourceFS, path, targetPath)
	})
}

// extractFile extracts a single file from embed.FS to target path
func (d *AppLabDeployer) extractFile(sourceFS fs.FS, sourcePath string, targetPath string) error {
	// Open source file from embedded filesystem
	sourceFile, err := sourceFS.Open(sourcePath)
	if err != nil {
		return fmt.Errorf("failed to open embedded file %s: %w", sourcePath, err)
	}
	defer sourceFile.Close()

	// Create target directory if needed
	targetDir := filepath.Dir(targetPath)
	if err := os.MkdirAll(targetDir, 0755); err != nil {
		return err
	}

	// Create target file
	targetFile, err := os.Create(targetPath)
	if err != nil {
		return fmt.Errorf("failed to create target file %s: %w", targetPath, err)
	}
	defer targetFile.Close()

	// Copy file contents
	if _, err := io.Copy(targetFile, sourceFile); err != nil {
		return fmt.Errorf("failed to copy file contents: %w", err)
	}

	// Set file permissions (make .py files executable)
	mode := os.FileMode(0644)
	if filepath.Ext(targetPath) == ".py" {
		mode = 0755
	}
	if err := os.Chmod(targetPath, mode); err != nil {
		return fmt.Errorf("failed to set file permissions: %w", err)
	}

	d.log.Debug().
		Str("source", sourcePath).
		Str("target", targetPath).
		Msg("Extracted App Lab file")

	return nil
}
