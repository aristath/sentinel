package deployment

import (
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// GitChecker handles Git repository operations
type GitChecker struct {
	repoDir string
	log     Logger
}

// NewGitChecker creates a new Git checker
func NewGitChecker(repoDir string, log Logger) *GitChecker {
	return &GitChecker{
		repoDir: repoDir,
		log:     log,
	}
}

// FetchUpdates fetches updates from remote with retry logic
func (g *GitChecker) FetchUpdates(maxRetries int) error {
	var lastError error
	for attempt := 1; attempt <= maxRetries; attempt++ {
		g.log.Info().
			Int("attempt", attempt).
			Int("max_retries", maxRetries).
			Msg("Fetching updates from remote")

		cmd := exec.Command("git", "fetch", "origin")
		cmd.Dir = g.repoDir
		cmd.Stdout = nil
		cmd.Stderr = nil

		err := cmd.Run()
		if err == nil {
			g.log.Info().Msg("Successfully fetched updates from remote")
			return nil
		}

		lastError = err
		g.log.Warn().
			Int("attempt", attempt).
			Err(err).
			Msg("Git fetch failed")

		if attempt < maxRetries {
			time.Sleep(2 * time.Second)
		}
	}

	return &GitFetchError{
		Message: fmt.Sprintf("failed after %d attempts", maxRetries),
		Err:     lastError,
	}
}

// HasChanges checks if local differs from remote
// Returns: hasChanges, localCommit, remoteCommit
func (g *GitChecker) HasChanges(branch string) (bool, string, string, error) {
	// Get local commit
	localCommit, err := g.getCommitHash("HEAD")
	if err != nil {
		return false, "", "", fmt.Errorf("failed to get local commit: %w", err)
	}

	// Get remote commit
	remoteCommit, err := g.getCommitHash(fmt.Sprintf("origin/%s", branch))
	if err != nil {
		return false, "", "", fmt.Errorf("failed to get remote commit: %w", err)
	}

	hasChanges := localCommit != remoteCommit
	return hasChanges, localCommit, remoteCommit, nil
}

// GetChangedFiles returns list of changed files between two commits
func (g *GitChecker) GetChangedFiles(localCommit, remoteCommit string) ([]string, error) {
	cmd := exec.Command("git", "diff", "--name-only", localCommit, remoteCommit)
	cmd.Dir = g.repoDir

	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to get changed files: %w", err)
	}

	files := strings.Split(strings.TrimSpace(string(output)), "\n")
	// Filter out empty strings
	result := []string{}
	for _, file := range files {
		file = strings.TrimSpace(file)
		if file != "" {
			result = append(result, file)
		}
	}

	return result, nil
}

// CategorizeChanges categorizes changed files into categories
func (g *GitChecker) CategorizeChanges(files []string) *ChangeCategories {
	categories := &ChangeCategories{}

	for _, file := range files {
		file = strings.TrimSpace(file)
		if file == "" {
			continue
		}

		// Normalize path separators
		file = filepath.ToSlash(file)

		// Trader service changes (exclude static and frontend)
		if strings.HasPrefix(file, "trader/") && !strings.HasPrefix(file, "trader/static/") && !strings.HasPrefix(file, "trader/frontend/") {
			categories.MainApp = true
		}
		if file == "trader/go.mod" || file == "trader/go.sum" {
			categories.MainApp = true
		}

		// Display app changes (Python app files)
		if strings.HasPrefix(file, "display/app/") {
			categories.DisplayApp = true
		}

		// Frontend (React) changes
		if strings.HasPrefix(file, "trader/frontend/") {
			categories.Frontend = true
		}

		// Sketch changes
		if strings.Contains(file, "arduino-app/sketch/") || strings.Contains(file, "display/sketch/") {
			categories.Sketch = true
		}

		// PyPFOpt changes
		if strings.HasPrefix(file, "microservices/pypfopt/app/") {
			categories.PyPFOpt = true
		}
		if file == "microservices/pypfopt/requirements.txt" {
			categories.PyPFOptDeps = true
		}

		// Tradernet changes
		if strings.HasPrefix(file, "microservices/tradernet/app/") {
			categories.Tradernet = true
		}
		if file == "microservices/tradernet/requirements.txt" {
			categories.TradernetDeps = true
		}

		// Config changes
		if strings.HasPrefix(file, "config/") || file == ".env" || strings.HasSuffix(file, ".env") {
			categories.Config = true
		}
	}

	return categories
}

// PullChanges pulls latest changes from remote
// It resets all local changes and cleans untracked files first
func (g *GitChecker) PullChanges(branch string) error {
	g.log.Info().
		Str("branch", branch).
		Msg("Resetting local changes before pulling")

	// Reset all local changes
	cmd := exec.Command("git", "reset", "--hard", "HEAD")
	cmd.Dir = g.repoDir
	cmd.Stdout = nil
	cmd.Stderr = nil

	if err := cmd.Run(); err != nil {
		g.log.Warn().
			Err(err).
			Msg("Failed to reset local changes (may not be necessary)")
		// Continue anyway - reset might fail if already clean
	}

	// Clean untracked files and directories
	g.log.Info().Msg("Cleaning untracked files")
	cmd = exec.Command("git", "clean", "-fd")
	cmd.Dir = g.repoDir
	cmd.Stdout = nil
	cmd.Stderr = nil

	if err := cmd.Run(); err != nil {
		g.log.Warn().
			Err(err).
			Msg("Failed to clean untracked files (may not be necessary)")
		// Continue anyway - clean might fail if nothing to clean
	}

	// Now pull changes
	g.log.Info().
		Str("branch", branch).
		Msg("Pulling changes from remote")

	cmd = exec.Command("git", "pull", "origin", branch)
	cmd.Dir = g.repoDir
	cmd.Stdout = nil
	cmd.Stderr = nil

	err := cmd.Run()
	if err != nil {
		return &GitPullError{
			Message: fmt.Sprintf("failed to pull branch %s", branch),
			Err:     err,
		}
	}

	g.log.Info().
		Str("branch", branch).
		Msg("Successfully pulled changes")

	return nil
}

// GetCurrentBranch returns the current Git branch name
func (g *GitChecker) GetCurrentBranch() (string, error) {
	cmd := exec.Command("git", "rev-parse", "--abbrev-ref", "HEAD")
	cmd.Dir = g.repoDir

	output, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("failed to get current branch: %w", err)
	}

	branch := strings.TrimSpace(string(output))
	return branch, nil
}

// EnsureSafeDirectory ensures Git safe directory is configured
func (g *GitChecker) EnsureSafeDirectory() error {
	absPath, err := filepath.Abs(g.repoDir)
	if err != nil {
		return fmt.Errorf("failed to get absolute path: %w", err)
	}

	// Check if already configured
	cmd := exec.Command("git", "config", "--global", "--get-all", "safe.directory")
	output, _ := cmd.Output()

	if strings.Contains(string(output), absPath) {
		return nil // Already configured
	}

	// Add to safe directories
	cmd = exec.Command("git", "config", "--global", "--add", "safe.directory", absPath)
	err = cmd.Run()
	if err != nil {
		g.log.Warn().
			Err(err).
			Str("path", absPath).
			Msg("Failed to configure git safe directory (may need manual configuration)")
		return err
	}

	g.log.Debug().
		Str("path", absPath).
		Msg("Configured git safe directory")

	return nil
}

// getCommitHash returns the commit hash for a reference
func (g *GitChecker) getCommitHash(ref string) (string, error) {
	cmd := exec.Command("git", "rev-parse", ref)
	cmd.Dir = g.repoDir

	output, err := cmd.Output()
	if err != nil {
		return "", err
	}

	return strings.TrimSpace(string(output)), nil
}
