package deployment

import (
	"fmt"
	"os"
	"path/filepath"
)

// StaticDeployer handles static asset deployment
type StaticDeployer struct {
	log Logger
}

// NewStaticDeployer creates a new static deployer
func NewStaticDeployer(log Logger) *StaticDeployer {
	return &StaticDeployer{
		log: log,
	}
}

// DeployStatic copies static assets from repo to deployment directory
func (d *StaticDeployer) DeployStatic(repoDir string, deployDir string) error {
	sourceDir := filepath.Join(repoDir, "trader/static")
	targetDir := filepath.Join(deployDir, "static")

	// Check if source exists
	if _, err := os.Stat(sourceDir); os.IsNotExist(err) {
		d.log.Info().
			Str("source", sourceDir).
			Msg("Static directory does not exist, skipping static deployment")
		return nil
	}

	d.log.Info().
		Str("source", sourceDir).
		Str("target", targetDir).
		Msg("Deploying static assets")

	// Create target directory
	if err := os.MkdirAll(targetDir, 0755); err != nil {
		return fmt.Errorf("failed to create target directory: %w", err)
	}

	// Copy files recursively
	if err := d.copyDirectory(sourceDir, targetDir); err != nil {
		return fmt.Errorf("failed to copy static assets: %w", err)
	}

	d.log.Info().
		Str("target", targetDir).
		Msg("Successfully deployed static assets")

	return nil
}

// copyDirectory recursively copies a directory
func (d *StaticDeployer) copyDirectory(sourceDir string, targetDir string) error {
	return filepath.Walk(sourceDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// Calculate relative path
		relPath, err := filepath.Rel(sourceDir, path)
		if err != nil {
			return err
		}

		targetPath := filepath.Join(targetDir, relPath)

		if info.IsDir() {
			// Create directory
			return os.MkdirAll(targetPath, info.Mode())
		}

		// Copy file
		return d.copyFile(path, targetPath, info.Mode())
	})
}

// copyFile copies a single file
func (d *StaticDeployer) copyFile(sourcePath string, targetPath string, mode os.FileMode) error {
	// Read source file
	data, err := os.ReadFile(sourcePath)
	if err != nil {
		return err
	}

	// Create target directory if needed
	targetDir := filepath.Dir(targetPath)
	if err := os.MkdirAll(targetDir, 0755); err != nil {
		return err
	}

	// Write target file
	if err := os.WriteFile(targetPath, data, mode); err != nil {
		return err
	}

	return nil
}
