package deployment

import (
	"fmt"
	"os"
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

// runGitCommand runs a git command and returns the error
func (g *GitChecker) runGitCommand(args ...string) error {
	cmd := exec.Command("git", args...)
	cmd.Dir = g.repoDir
	cmd.Stdout = nil
	cmd.Stderr = nil
	return cmd.Run()
}

// FetchUpdates fetches updates from remote with retry logic
// Uses depth=1 to keep the clone shallow
func (g *GitChecker) FetchUpdates(maxRetries int) error {
	var lastError error
	for attempt := 1; attempt <= maxRetries; attempt++ {
		g.log.Info().
			Int("attempt", attempt).
			Int("max_retries", maxRetries).
			Msg("Fetching updates from remote (depth 1)")

		err := g.runGitCommand("fetch", "--depth", "1", "origin")
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
	localCommit, err := g.getCommitHash("HEAD")
	if err != nil {
		return false, "", "", fmt.Errorf("failed to get local commit: %w", err)
	}

	remoteCommit, err := g.getCommitHash(fmt.Sprintf("origin/%s", branch))
	if err != nil {
		return false, "", "", fmt.Errorf("failed to get remote commit: %w", err)
	}

	return localCommit != remoteCommit, localCommit, remoteCommit, nil
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

		file = filepath.ToSlash(file)

		// Trader service changes (exclude static and frontend)
		if strings.HasPrefix(file, "trader/") && !strings.HasPrefix(file, "trader/static/") && !strings.HasPrefix(file, "trader/frontend/") {
			categories.MainApp = true
		}
		if file == "trader/go.mod" || file == "trader/go.sum" {
			categories.MainApp = true
		}

		// Display app changes
		if strings.HasPrefix(file, "display/app/") {
			categories.DisplayApp = true
		}

		// Frontend changes
		if strings.HasPrefix(file, "trader/frontend/") {
			categories.Frontend = true
		}

		// Sketch changes
		if strings.Contains(file, "arduino-app/sketch/") || strings.Contains(file, "display/sketch/") {
			categories.Sketch = true
		}

		// Microservice changes
		// Unified microservice combines pypfopt, tradernet, and yfinance
		if strings.HasPrefix(file, "microservices/unified/app/") {
			categories.PyPFOpt = true
			categories.Tradernet = true
			categories.YahooFinance = true
		}
		if file == "microservices/unified/requirements.txt" {
			categories.PyPFOptDeps = true
			categories.TradernetDeps = true
			categories.YahooFinanceDeps = true
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
// Uses depth=1 fetch to keep the clone shallow and save disk space
func (g *GitChecker) PullChanges(branch string) error {
	g.log.Info().Str("branch", branch).Msg("Resetting local changes before pulling")

	// Reset and clean
	_ = g.runGitCommand("reset", "--hard", "HEAD")
	_ = g.runGitCommand("clean", "-fd")

	// Convert full clone to shallow if needed
	if !g.IsShallow() {
		g.log.Info().Msg("Detected full clone, converting to shallow to save disk space")
		if err := g.ConvertToShallow(branch); err != nil {
			g.log.Warn().Err(err).Msg("Failed to convert to shallow clone, continuing")
		}
	}

	// Fetch with depth 1 to prevent accumulating history
	g.log.Info().Str("branch", branch).Msg("Fetching changes from remote (depth 1)")
	if err := g.runGitCommand("fetch", "--depth", "1", "origin", branch); err != nil {
		return &GitPullError{
			Message: fmt.Sprintf("failed to fetch branch %s", branch),
			Err:     err,
		}
	}

	// Reset to remote branch
	g.log.Info().Str("branch", branch).Msg("Resetting to remote branch")
	if err := g.runGitCommand("reset", "--hard", fmt.Sprintf("origin/%s", branch)); err != nil {
		return &GitPullError{
			Message: fmt.Sprintf("failed to reset to origin/%s", branch),
			Err:     err,
		}
	}

	g.log.Info().Str("branch", branch).Msg("Successfully updated to latest commit")

	// Clean up any accumulated objects
	g.log.Debug().Msg("Pruning unreachable objects")
	_ = g.runGitCommand("gc", "--prune=now", "--aggressive")

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

	return strings.TrimSpace(string(output)), nil
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
		return nil
	}

	// Add to safe directories
	cmd = exec.Command("git", "config", "--global", "--add", "safe.directory", absPath)
	if err := cmd.Run(); err != nil {
		g.log.Warn().Err(err).Str("path", absPath).Msg("Failed to configure git safe directory")
		return err
	}

	g.log.Debug().Str("path", absPath).Msg("Configured git safe directory")
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

// IsShallow checks if the repository is a shallow clone
func (g *GitChecker) IsShallow() bool {
	shallowFile := filepath.Join(g.repoDir, ".git", "shallow")
	_, err := os.Stat(shallowFile)
	return err == nil
}

// ConvertToShallow converts a full clone to a shallow clone
// This is called automatically when a full clone is detected
func (g *GitChecker) ConvertToShallow(branch string) error {
	if g.IsShallow() {
		return nil
	}

	g.log.Info().Msg("Converting full clone to shallow clone to save disk space")

	// Get remote URL and current commit
	cmd := exec.Command("git", "config", "--get", "remote.origin.url")
	cmd.Dir = g.repoDir
	remoteURLBytes, err := cmd.Output()
	if err != nil {
		return fmt.Errorf("failed to get remote URL: %w", err)
	}
	remoteURL := strings.TrimSpace(string(remoteURLBytes))

	currentCommit, err := g.getCommitHash("HEAD")
	if err != nil {
		return fmt.Errorf("failed to get current commit: %w", err)
	}

	// Backup .git directory
	gitDir := filepath.Join(g.repoDir, ".git")
	backupDir := gitDir + ".backup." + fmt.Sprintf("%d", time.Now().Unix())
	_ = exec.Command("cp", "-r", gitDir, backupDir).Run()

	// Remove .git and re-initialize as shallow clone
	if err := os.RemoveAll(gitDir); err != nil {
		return fmt.Errorf("failed to remove .git directory: %w", err)
	}

	if err := g.runGitCommand("init"); err != nil {
		return fmt.Errorf("failed to re-initialize git: %w", err)
	}

	// Set up remote and fetch shallow
	if err := g.runGitCommand("remote", "add", "origin", remoteURL); err != nil {
		if err := g.runGitCommand("remote", "set-url", "origin", remoteURL); err != nil {
			return fmt.Errorf("failed to set remote URL: %w", err)
		}
	}

	if err := g.runGitCommand("fetch", "--depth", "1", "origin", branch); err != nil {
		return fmt.Errorf("failed to fetch shallow: %w", err)
	}

	// Checkout branch (simplified - just reset to remote)
	if err := g.runGitCommand("reset", "--hard", fmt.Sprintf("origin/%s", branch)); err != nil {
		return fmt.Errorf("failed to checkout branch: %w", err)
	}

	// Verify we're on the same commit
	if newCommit, err := g.getCommitHash("HEAD"); err == nil && newCommit != currentCommit {
		g.log.Warn().
			Str("old_commit", currentCommit).
			Str("new_commit", newCommit).
			Msg("Commit changed during conversion - remote may have moved")
	}

	// Clean up backup
	_ = os.RemoveAll(backupDir)

	g.log.Info().Msg("Successfully converted to shallow clone")
	return nil
}
