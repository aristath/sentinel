package deployment

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// ArtifactTracker tracks the last deployed GitHub Actions run ID
type ArtifactTracker struct {
	trackerFile string
	log         Logger
}

// NewArtifactTracker creates a new artifact tracker
func NewArtifactTracker(trackerFile string, log Logger) *ArtifactTracker {
	return &ArtifactTracker{
		trackerFile: trackerFile,
		log:         log,
	}
}

// GetLastDeployedRunID returns the last deployed run ID, or empty string if none
func (t *ArtifactTracker) GetLastDeployedRunID() (string, error) {
	data, err := os.ReadFile(t.trackerFile)
	if os.IsNotExist(err) {
		return "", nil // No previous deployment
	}
	if err != nil {
		return "", fmt.Errorf("failed to read tracker file: %w", err)
	}

	runID := strings.TrimSpace(string(data))
	if runID == "" {
		return "", nil
	}

	return runID, nil
}

// MarkDeployed records the run ID as deployed
func (t *ArtifactTracker) MarkDeployed(runID string) error {
	// Ensure directory exists
	dir := filepath.Dir(t.trackerFile)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create tracker directory: %w", err)
	}

	// Write run ID to file
	if err := os.WriteFile(t.trackerFile, []byte(runID+"\n"), 0644); err != nil {
		return fmt.Errorf("failed to write tracker file: %w", err)
	}

	t.log.Debug().
		Str("run_id", runID).
		Str("file", t.trackerFile).
		Msg("Marked artifact as deployed")

	return nil
}

// GitHubRun represents a GitHub Actions workflow run
type GitHubRun struct {
	DatabaseID string    `json:"databaseId"`
	Status     string    `json:"status"`
	Conclusion string    `json:"conclusion"`
	HeadSHA    string    `json:"headSha"`
	CreatedAt  time.Time `json:"createdAt"`
}

// GitHubArtifactDeployer handles downloading and deploying artifacts from GitHub Actions
type GitHubArtifactDeployer struct {
	log          Logger
	workflowName string
	artifactName string
	branch       string
	repoDir      string
	tracker      *ArtifactTracker
}

// NewGitHubArtifactDeployer creates a new GitHub artifact deployer
func NewGitHubArtifactDeployer(workflowName, artifactName, branch, repoDir string, tracker *ArtifactTracker, log Logger) *GitHubArtifactDeployer {
	return &GitHubArtifactDeployer{
		log:          log,
		workflowName: workflowName,
		artifactName: artifactName,
		branch:       branch,
		repoDir:      repoDir,
		tracker:      tracker,
	}
}

// CheckForNewBuild checks if a new successful build is available
// Returns the run ID if a new build is available, empty string otherwise
func (g *GitHubArtifactDeployer) CheckForNewBuild() (string, error) {
	// Get last deployed run ID
	lastRunID, err := g.tracker.GetLastDeployedRunID()
	if err != nil {
		return "", fmt.Errorf("failed to get last deployed run ID: %w", err)
	}

	// Get latest successful run
	// gh CLI needs to run from within a git repository to determine the repo context
	cmd := exec.Command("gh", "run", "list",
		"--workflow", g.workflowName,
		"--branch", g.branch,
		"--status", "success",
		"--limit", "1",
		"--json", "databaseId,status,conclusion,headSha,createdAt",
	)
	cmd.Dir = g.repoDir

	output, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("failed to list workflow runs: %w", err)
	}

	var runs []GitHubRun
	if err := json.Unmarshal(output, &runs); err != nil {
		return "", fmt.Errorf("failed to parse workflow runs: %w", err)
	}

	if len(runs) == 0 {
		g.log.Debug().Msg("No successful workflow runs found")
		return "", nil
	}

	latestRun := runs[0]
	latestRunID := latestRun.DatabaseID

	// Check if this is a new build
	if lastRunID == "" {
		g.log.Info().
			Str("run_id", latestRunID).
			Str("commit", latestRun.HeadSHA).
			Msg("No previous deployment found, new build available")
		return latestRunID, nil
	}

	if latestRunID != lastRunID {
		g.log.Info().
			Str("last_run_id", lastRunID).
			Str("latest_run_id", latestRunID).
			Str("commit", latestRun.HeadSHA).
			Msg("New build available")
		return latestRunID, nil
	}

	g.log.Debug().
		Str("run_id", latestRunID).
		Msg("No new build available (already deployed)")

	return "", nil
}

// VerifyBinaryArchitecture verifies that a binary is built for linux/arm64
// Uses `file` command to check the ELF architecture
func (g *GitHubArtifactDeployer) VerifyBinaryArchitecture(binaryPath string) error {
	// Use `file` command to check binary architecture
	cmd := exec.Command("file", binaryPath)
	output, err := cmd.Output()
	if err != nil {
		return fmt.Errorf("failed to check binary architecture: %w", err)
	}

	fileOutput := strings.ToLower(string(output))

	// Check for linux and arm64/aarch64
	hasLinux := strings.Contains(fileOutput, "linux")
	hasARM64 := strings.Contains(fileOutput, "arm64") || strings.Contains(fileOutput, "aarch64")

	if !hasLinux {
		return fmt.Errorf("binary is not built for Linux (detected: %s)", strings.TrimSpace(string(output)))
	}

	if !hasARM64 {
		return fmt.Errorf("binary is not built for ARM64 (detected: %s)", strings.TrimSpace(string(output)))
	}

	g.log.Debug().
		Str("binary", binaryPath).
		Str("file_output", strings.TrimSpace(string(output))).
		Msg("Verified binary architecture: linux/arm64")

	return nil
}

// DownloadArtifact downloads the artifact for a specific run ID
// Returns the path to the downloaded binary
// Verifies that the binary is built for linux/arm64
func (g *GitHubArtifactDeployer) DownloadArtifact(runID string, outputDir string) (string, error) {
	// Ensure output directory exists
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create output directory: %w", err)
	}

	g.log.Info().
		Str("run_id", runID).
		Str("artifact", g.artifactName).
		Str("output_dir", outputDir).
		Msg("Downloading artifact from GitHub Actions")

	// Download artifact using gh CLI
	// gh CLI needs to run from within a git repository to determine the repo context
	cmd := exec.Command("gh", "run", "download",
		runID,
		"--name", g.artifactName,
		"--dir", outputDir,
	)
	cmd.Dir = g.repoDir

	var stderr strings.Builder
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("failed to download artifact: %w (stderr: %s)", err, stderr.String())
	}

	// Find the downloaded binary
	// gh run download extracts artifacts, so we need to find the binary
	// The artifact name might be the directory or the file itself
	artifactPath := filepath.Join(outputDir, g.artifactName)

	var binaryPath string

	// Check if it's a file
	if info, err := os.Stat(artifactPath); err == nil && !info.IsDir() {
		binaryPath = artifactPath
	} else if err == nil && info.IsDir() {
		// Check if it's a directory with the binary inside
		binaryPath = filepath.Join(artifactPath, g.artifactName)
		if _, err := os.Stat(binaryPath); err != nil {
			// Try to find any executable file in the directory
			entries, err := os.ReadDir(artifactPath)
			if err == nil {
				for _, entry := range entries {
					if !entry.IsDir() {
						binaryPath = filepath.Join(artifactPath, entry.Name())
						break
					}
				}
			}
		}
	} else {
		// Try to find any executable file in the output directory
		entries, err := os.ReadDir(outputDir)
		if err != nil {
			return "", fmt.Errorf("failed to read output directory: %w", err)
		}

		for _, entry := range entries {
			if !entry.IsDir() {
				path := filepath.Join(outputDir, entry.Name())
				// Check if it's executable or matches our artifact name
				if strings.Contains(entry.Name(), g.artifactName) || strings.HasSuffix(entry.Name(), "-arm64") {
					binaryPath = path
					break
				}
			}
		}
	}

	if binaryPath == "" {
		return "", fmt.Errorf("downloaded artifact not found in %s", outputDir)
	}

	// Verify binary architecture (CRITICAL: must be linux/arm64)
	if err := g.VerifyBinaryArchitecture(binaryPath); err != nil {
		// Remove the invalid binary
		os.Remove(binaryPath)
		return "", fmt.Errorf("binary architecture verification failed: %w", err)
	}

	g.log.Info().
		Str("binary", binaryPath).
		Msg("Downloaded and verified linux/arm64 binary")

	return binaryPath, nil
}

// DeployLatest checks for a new build and deploys it if available
// Returns the path to the deployed binary, or empty string if no new build
func (g *GitHubArtifactDeployer) DeployLatest(outputDir string) (string, error) {
	// Check for new build
	runID, err := g.CheckForNewBuild()
	if err != nil {
		return "", fmt.Errorf("failed to check for new build: %w", err)
	}

	if runID == "" {
		return "", nil // No new build
	}

	// Download artifact
	binaryPath, err := g.DownloadArtifact(runID, outputDir)
	if err != nil {
		return "", fmt.Errorf("failed to download artifact: %w", err)
	}

	// Mark as deployed
	if err := g.tracker.MarkDeployed(runID); err != nil {
		g.log.Warn().Err(err).Msg("Failed to mark artifact as deployed, but download succeeded")
	}

	g.log.Info().
		Str("run_id", runID).
		Str("binary", binaryPath).
		Msg("Successfully downloaded artifact")

	return binaryPath, nil
}
