package deployment

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// GoServiceBuilder builds Go service binaries
type GoServiceBuilder struct {
	log Logger
}

// NewGoServiceBuilder creates a new Go service builder
func NewGoServiceBuilder(log Logger) *GoServiceBuilder {
	return &GoServiceBuilder{
		log: log,
	}
}

// BuildService builds a Go service binary
func (b *GoServiceBuilder) BuildService(config GoServiceConfig, repoDir string, outputPath string) error {
	buildPath := filepath.Join(repoDir, config.BuildPath)

	// Verify build path exists
	if _, err := os.Stat(buildPath); os.IsNotExist(err) {
		return &BuildError{
			ServiceName: config.Name,
			Message:     fmt.Sprintf("build path does not exist: %s", buildPath),
			Err:         err,
		}
	}

	b.log.Info().
		Str("service", config.Name).
		Str("build_path", buildPath).
		Str("output", outputPath).
		Msg("Building Go service")

	// Get version info for build flags
	versionInfo, err := b.BuildVersionInfo(repoDir)
	if err != nil {
		b.log.Warn().
			Err(err).
			Msg("Failed to get version info, building without version flags")
		versionInfo = VersionInfo{}
	}

	// Build command
	ldflags := b.buildLDFlags(versionInfo)
	cmd := exec.Command("go", "build", "-ldflags", ldflags, "-o", outputPath, ".")
	cmd.Dir = buildPath

	// Capture build output
	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	// Run build
	startTime := time.Now()
	err = cmd.Run()
	duration := time.Since(startTime)

	if err != nil {
		buildOutput := stdout.String() + stderr.String()
		return &BuildError{
			ServiceName: config.Name,
			Message:     "build failed",
			Err:         err,
			BuildOutput: buildOutput,
		}
	}

	// Verify binary
	if err := b.VerifyBinary(outputPath); err != nil {
		return &BuildError{
			ServiceName: config.Name,
			Message:     "binary verification failed",
			Err:         err,
		}
	}

	b.log.Info().
		Str("service", config.Name).
		Str("output", outputPath).
		Dur("duration", duration).
		Msg("Successfully built Go service")

	return nil
}

// GetServiceBuildPath returns the build path for a service
func (b *GoServiceBuilder) GetServiceBuildPath(serviceName string, repoDir string) (string, error) {
	var buildPath string

	switch serviceName {
	case "trader":
		buildPath = filepath.Join(repoDir, "trader/cmd/server")
	case "display-bridge":
		buildPath = filepath.Join(repoDir, "display/bridge")
	default:
		return "", fmt.Errorf("unknown service: %s", serviceName)
	}

	// Verify path exists
	if _, err := os.Stat(buildPath); os.IsNotExist(err) {
		return "", fmt.Errorf("build path does not exist: %s", buildPath)
	}

	return buildPath, nil
}

// VerifyBinary verifies that a binary exists and is executable
func (b *GoServiceBuilder) VerifyBinary(binaryPath string) error {
	info, err := os.Stat(binaryPath)
	if os.IsNotExist(err) {
		return fmt.Errorf("binary does not exist: %s", binaryPath)
	}
	if err != nil {
		return fmt.Errorf("failed to stat binary: %w", err)
	}

	// Check if executable (on Unix systems)
	mode := info.Mode()
	if mode&0111 == 0 {
		// Try to make it executable
		if err := os.Chmod(binaryPath, mode|0111); err != nil {
			return fmt.Errorf("binary is not executable and could not make it executable: %w", err)
		}
	}

	return nil
}

// VersionInfo contains version information for build
type VersionInfo struct {
	Version   string
	BuildTime string
	GitCommit string
	GitBranch string
}

// BuildVersionInfo gets version information from Git
func (b *GoServiceBuilder) BuildVersionInfo(repoDir string) (VersionInfo, error) {
	info := VersionInfo{
		BuildTime: time.Now().UTC().Format(time.RFC3339),
	}

	// Get Git commit
	commitCmd := exec.Command("git", "rev-parse", "--short", "HEAD")
	commitCmd.Dir = repoDir
	if output, err := commitCmd.Output(); err == nil {
		info.GitCommit = strings.TrimSpace(string(output))
	}

	// Get Git branch
	branchCmd := exec.Command("git", "rev-parse", "--abbrev-ref", "HEAD")
	branchCmd.Dir = repoDir
	if output, err := branchCmd.Output(); err == nil {
		info.GitBranch = strings.TrimSpace(string(output))
	}

	// Version is commit hash or "dev"
	if info.GitCommit != "" {
		info.Version = info.GitCommit
	} else {
		info.Version = "dev"
	}

	return info, nil
}

// buildLDFlags builds ldflags string for go build
func (b *GoServiceBuilder) buildLDFlags(info VersionInfo) string {
	flags := []string{}

	if info.Version != "" {
		flags = append(flags, fmt.Sprintf("-X main.Version=%s", escapeFlagValue(info.Version)))
	}
	if info.BuildTime != "" {
		flags = append(flags, fmt.Sprintf("-X main.BuildTime=%s", escapeFlagValue(info.BuildTime)))
	}
	if info.GitCommit != "" {
		flags = append(flags, fmt.Sprintf("-X main.GitCommit=%s", escapeFlagValue(info.GitCommit)))
	}
	if info.GitBranch != "" {
		flags = append(flags, fmt.Sprintf("-X main.GitBranch=%s", escapeFlagValue(info.GitBranch)))
	}

	return strings.Join(flags, " ")
}

// escapeFlagValue escapes a value for use in ldflags
func escapeFlagValue(value string) string {
	// Escape quotes and spaces
	value = strings.ReplaceAll(value, "\"", "\\\"")
	return value
}
