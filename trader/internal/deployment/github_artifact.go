package deployment

import (
	"archive/zip"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
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
	DatabaseID databaseIDString `json:"databaseId"`
	Status     string           `json:"status"`
	Conclusion string           `json:"conclusion"`
	HeadSHA    string           `json:"headSha"`
	CreatedAt  time.Time        `json:"createdAt"`
}

// databaseIDString handles unmarshaling databaseId from both number and string
// GitHub API returns it as a number, but we need it as a string for comparison
type databaseIDString string

// UnmarshalJSON handles both number and string types for databaseId
func (d *databaseIDString) UnmarshalJSON(data []byte) error {
	// Try number first
	var num int64
	if err := json.Unmarshal(data, &num); err == nil {
		*d = databaseIDString(fmt.Sprintf("%d", num))
		return nil
	}
	// Fall back to string
	var str string
	if err := json.Unmarshal(data, &str); err != nil {
		return err
	}
	*d = databaseIDString(str)
	return nil
}

// GitHubArtifactDeployer handles downloading and deploying artifacts from GitHub Actions
type GitHubArtifactDeployer struct {
	log          Logger
	workflowName string
	artifactName string
	branch       string
	githubRepo   string // GitHub repository in format "owner/repo"
	tracker      *ArtifactTracker
	httpClient   *http.Client
}

// NewGitHubArtifactDeployer creates a new GitHub artifact deployer
func NewGitHubArtifactDeployer(workflowName, artifactName, branch, githubRepo string, tracker *ArtifactTracker, log Logger) *GitHubArtifactDeployer {
	return &GitHubArtifactDeployer{
		log:          log,
		workflowName: workflowName,
		artifactName: artifactName,
		branch:       branch,
		githubRepo:   githubRepo,
		tracker:      tracker,
		httpClient:   &http.Client{Timeout: 60 * time.Second},
	}
}

// CheckForNewBuild checks if a new successful build is available using GitHub REST API
// Returns the run ID if a new build is available, empty string otherwise
func (g *GitHubArtifactDeployer) CheckForNewBuild() (string, error) {
	// Get last deployed run ID
	lastRunID, err := g.tracker.GetLastDeployedRunID()
	if err != nil {
		return "", fmt.Errorf("failed to get last deployed run ID: %w", err)
	}

	// Get GitHub token from environment
	githubToken := os.Getenv("GITHUB_TOKEN")
	if githubToken == "" {
		return "", fmt.Errorf("GITHUB_TOKEN environment variable is required")
	}

	// Get workflow ID first
	workflowID, err := g.getWorkflowID(githubToken)
	if err != nil {
		return "", fmt.Errorf("failed to get workflow ID: %w", err)
	}

	// Get latest successful run using GitHub API
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/workflows/%s/runs?branch=%s&status=success&per_page=1", g.githubRepo, workflowID, g.branch)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+githubToken)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")

	resp, err := g.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to list workflow runs: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("GitHub API returned status %d: %s", resp.StatusCode, string(body))
	}

	var runsResponse struct {
		WorkflowRuns []struct {
			ID         int64  `json:"id"`
			Status     string `json:"status"`
			Conclusion string `json:"conclusion"`
			HeadSHA    string `json:"head_sha"`
			CreatedAt  string `json:"created_at"`
		} `json:"workflow_runs"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&runsResponse); err != nil {
		return "", fmt.Errorf("failed to parse workflow runs: %w", err)
	}

	if len(runsResponse.WorkflowRuns) == 0 {
		g.log.Debug().Msg("No successful workflow runs found")
		return "", nil
	}

	latestRun := runsResponse.WorkflowRuns[0]
	latestRunID := fmt.Sprintf("%d", latestRun.ID)

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

// getWorkflowID gets the workflow ID by name
func (g *GitHubArtifactDeployer) getWorkflowID(githubToken string) (string, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/workflows", g.githubRepo)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+githubToken)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")

	resp, err := g.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to list workflows: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("GitHub API returned status %d: %s", resp.StatusCode, string(body))
	}

	var workflowsResponse struct {
		Workflows []struct {
			ID   int64  `json:"id"`
			Name string `json:"name"`
			Path string `json:"path"`
		} `json:"workflows"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&workflowsResponse); err != nil {
		return "", fmt.Errorf("failed to parse workflows: %w", err)
	}

	// Find workflow by name (match either name or path)
	// Also check if workflowName matches the filename part of the path
	for _, workflow := range workflowsResponse.Workflows {
		if workflow.Name == g.workflowName || workflow.Path == g.workflowName {
			return fmt.Sprintf("%d", workflow.ID), nil
		}
		// Check if workflowName matches the filename part of the path
		// e.g., "build-go.yml" should match ".github/workflows/build-go.yml"
		if strings.HasSuffix(workflow.Path, "/"+g.workflowName) || strings.HasSuffix(workflow.Path, g.workflowName) {
			return fmt.Sprintf("%d", workflow.ID), nil
		}
	}

	return "", fmt.Errorf("workflow %s not found", g.workflowName)
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

// DownloadArtifact downloads the artifact for a specific run ID using GitHub REST API
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

	// Get GitHub token from environment
	githubToken := os.Getenv("GITHUB_TOKEN")
	if githubToken == "" {
		return "", fmt.Errorf("GITHUB_TOKEN environment variable is required")
	}

	// Get artifacts for the run
	artifactID, err := g.getArtifactIDForRun(runID, githubToken)
	if err != nil {
		return "", fmt.Errorf("failed to get artifact ID: %w", err)
	}

	// Download artifact zip file
	zipPath := filepath.Join(outputDir, "artifact.zip")
	if err := g.downloadArtifactZip(artifactID, zipPath, githubToken); err != nil {
		return "", fmt.Errorf("failed to download artifact zip: %w", err)
	}
	defer os.Remove(zipPath) // Clean up zip file

	// Extract zip file
	extractDir := filepath.Join(outputDir, "extracted")
	if err := os.MkdirAll(extractDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create extract directory: %w", err)
	}

	if err := g.extractZip(zipPath, extractDir); err != nil {
		return "", fmt.Errorf("failed to extract artifact: %w", err)
	}

	// Find the downloaded binary in extracted directory
	var binaryPath string

	// Check if artifact name is a file or directory in extracted dir
	artifactPath := filepath.Join(extractDir, g.artifactName)
	if info, err := os.Stat(artifactPath); err == nil && !info.IsDir() {
		binaryPath = artifactPath
	} else if err == nil && info.IsDir() {
		// Check if it's a directory with the binary inside
		binaryPath = filepath.Join(artifactPath, g.artifactName)
		if _, err := os.Stat(binaryPath); err != nil {
			// Try to find any file in the directory
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
		// Try to find any file matching artifact name in extracted directory
		entries, err := os.ReadDir(extractDir)
		if err != nil {
			return "", fmt.Errorf("failed to read extract directory: %w", err)
		}

		for _, entry := range entries {
			if !entry.IsDir() {
				path := filepath.Join(extractDir, entry.Name())
				// Check if it matches our artifact name
				if strings.Contains(entry.Name(), g.artifactName) || strings.HasSuffix(entry.Name(), "-arm64") {
					binaryPath = path
					break
				}
			}
		}
	}

	if binaryPath == "" {
		return "", fmt.Errorf("downloaded artifact not found in %s", extractDir)
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

// getArtifactIDForRun gets the artifact ID for a specific run
func (g *GitHubArtifactDeployer) getArtifactIDForRun(runID string, githubToken string) (int64, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/runs/%s/artifacts", g.githubRepo, runID)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return 0, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+githubToken)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")

	resp, err := g.httpClient.Do(req)
	if err != nil {
		return 0, fmt.Errorf("failed to list artifacts: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return 0, fmt.Errorf("GitHub API returned status %d: %s", resp.StatusCode, string(body))
	}

	var artifactsResponse struct {
		Artifacts []struct {
			ID   int64  `json:"id"`
			Name string `json:"name"`
		} `json:"artifacts"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&artifactsResponse); err != nil {
		return 0, fmt.Errorf("failed to parse artifacts: %w", err)
	}

	// Find artifact by name
	for _, artifact := range artifactsResponse.Artifacts {
		if artifact.Name == g.artifactName {
			return artifact.ID, nil
		}
	}

	return 0, fmt.Errorf("artifact %s not found in run %s", g.artifactName, runID)
}

// downloadArtifactZip downloads the artifact zip file
func (g *GitHubArtifactDeployer) downloadArtifactZip(artifactID int64, zipPath string, githubToken string) error {
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/artifacts/%d/zip", g.githubRepo, artifactID)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+githubToken)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")

	resp, err := g.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to download artifact: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("GitHub API returned status %d: %s", resp.StatusCode, string(body))
	}

	// Create zip file
	zipFile, err := os.Create(zipPath)
	if err != nil {
		return fmt.Errorf("failed to create zip file: %w", err)
	}
	defer zipFile.Close()

	// Copy response body to file
	if _, err := io.Copy(zipFile, resp.Body); err != nil {
		return fmt.Errorf("failed to write zip file: %w", err)
	}

	return nil
}

// extractZip extracts a zip file to a directory
func (g *GitHubArtifactDeployer) extractZip(zipPath string, extractDir string) error {
	r, err := zip.OpenReader(zipPath)
	if err != nil {
		return fmt.Errorf("failed to open zip file: %w", err)
	}
	defer r.Close()

	for _, f := range r.File {
		path := filepath.Join(extractDir, f.Name)

		// Check for ZipSlip vulnerability
		if !strings.HasPrefix(path, filepath.Clean(extractDir)+string(os.PathSeparator)) {
			return fmt.Errorf("invalid file path: %s", f.Name)
		}

		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(path, f.FileInfo().Mode()); err != nil {
				return fmt.Errorf("failed to create directory for extracted file: %w", err)
			}
			continue
		}

		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			return fmt.Errorf("failed to create directory: %w", err)
		}

		rc, err := f.Open()
		if err != nil {
			return fmt.Errorf("failed to open file in zip: %w", err)
		}

		outFile, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, f.FileInfo().Mode())
		if err != nil {
			rc.Close()
			return fmt.Errorf("failed to create file: %w", err)
		}

		_, err = io.Copy(outFile, rc)
		outFile.Close()
		rc.Close()

		if err != nil {
			return fmt.Errorf("failed to extract file: %w", err)
		}
	}

	return nil
}

// DeployLatest checks for a new build and deploys it if available
// Returns the path to the deployed binary, or empty string if no new build
// If runID is provided (non-empty), skips CheckForNewBuild() and uses the provided runID.
// If runID is empty, calls CheckForNewBuild() as before (backward compatibility).
// Note: MarkDeployed() is NOT called here - it should be called after successful deployment.
func (g *GitHubArtifactDeployer) DeployLatest(outputDir string, runID string) (string, error) {
	// If runID is not provided, check for new build
	if runID == "" {
		var err error
		runID, err = g.CheckForNewBuild()
		if err != nil {
			return "", fmt.Errorf("failed to check for new build: %w", err)
		}

		if runID == "" {
			return "", nil // No new build
		}
	}

	// Download artifact
	binaryPath, err := g.DownloadArtifact(runID, outputDir)
	if err != nil {
		return "", fmt.Errorf("failed to download artifact: %w", err)
	}

	// Note: MarkDeployed() is NOT called here - it should be called after successful deployment
	// This prevents marking as deployed if deployment fails later

	g.log.Info().
		Str("run_id", runID).
		Str("binary", binaryPath).
		Msg("Successfully downloaded artifact")

	return binaryPath, nil
}
