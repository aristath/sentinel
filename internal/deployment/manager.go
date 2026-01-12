package deployment

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/rs/zerolog"
)

// DeploymentConfig holds deployment configuration
type DeploymentConfig struct {
	DeployDir              string
	APIPort                int
	APIHost                string
	Enabled                bool
	TraderConfig           GoServiceConfig
	DockerComposePath      string
	LockTimeout            time.Duration
	HealthCheckTimeout     time.Duration
	HealthCheckMaxAttempts int
	GitBranch              string
	// GitHub artifact deployment settings
	UseGitHubArtifacts bool
	GitHubWorkflowName string
	GitHubArtifactName string
	GitHubBranch       string
	GitHubRepo         string // GitHub repository in format "owner/repo" (e.g., "aristath/sentinel")
	GitHubToken        string // GitHub personal access token for artifact downloads
}

// Manager handles deployment orchestration
type Manager struct {
	config     *DeploymentConfig
	log        zerolog.Logger
	statusFile string
	version    string
	gitCommit  string
	gitBranch  string

	// Components
	lock                   *DeploymentLock
	binaryDeployer         *BinaryDeployer
	serviceManager         *ServiceManager
	dockerManager          *DockerManager
	sketchDeployer         *SketchDeployer
	githubArtifactDeployer *GitHubArtifactDeployer
	artifactTracker        *ArtifactTracker
}

// NewManager creates a new deployment manager
func NewManager(config *DeploymentConfig, version string, log zerolog.Logger) *Manager {
	// Resolve deploy directory to absolute (required for reliable path operations)
	absDeployDir, err := filepath.Abs(config.DeployDir)
	if err != nil {
		log.Warn().Err(err).Str("deploy_dir", config.DeployDir).Msg("Failed to resolve DeployDir to absolute path, using as-is")
		absDeployDir = config.DeployDir
	}

	// Update config with absolute path
	config.DeployDir = absDeployDir

	// Create components
	lock := NewDeploymentLock(
		filepath.Join(config.DeployDir, ".deploy.lock"),
		&logAdapter{log: log.With().Str("component", "lock").Logger()},
	)

	binaryDeployer := NewBinaryDeployer(
		&logAdapter{log: log.With().Str("component", "binary").Logger()},
	)

	serviceManager := NewServiceManager(
		&logAdapter{log: log.With().Str("component", "service").Logger()},
	)

	dockerManager := NewDockerManager(
		config.DockerComposePath,
		&logAdapter{log: log.With().Str("component", "docker").Logger()},
	)

	sketchDeployer := NewSketchDeployer(
		&logAdapter{log: log.With().Str("component", "sketch").Logger()},
	)

	// GitHub artifact deployment is REQUIRED (no fallback to on-device building)
	// This saves 1GB+ disk space by not requiring Go toolchain on device
	var githubArtifactDeployer *GitHubArtifactDeployer
	var artifactTracker *ArtifactTracker

	if config.GitHubWorkflowName == "" || config.GitHubArtifactName == "" {
		log.Fatal().
			Str("workflow", config.GitHubWorkflowName).
			Str("artifact", config.GitHubArtifactName).
			Msg("GitHub artifact deployment is REQUIRED but configuration is missing. Set GITHUB_WORKFLOW_NAME and GITHUB_ARTIFACT_NAME")
	}

	if config.GitHubRepo == "" {
		log.Fatal().
			Msg("GitHub repository is REQUIRED but configuration is missing. Set GITHUB_REPO (e.g., 'aristath/sentinel')")
	}

	trackerFile := filepath.Join(config.DeployDir, "github-artifact-id.txt")
	artifactTracker = NewArtifactTracker(
		trackerFile,
		&logAdapter{log: log.With().Str("component", "artifact-tracker").Logger()},
	)

	githubBranch := config.GitHubBranch
	if githubBranch == "" {
		githubBranch = config.GitBranch
		if githubBranch == "" {
			githubBranch = "main" // Default fallback
		}
	}

	githubArtifactDeployer = NewGitHubArtifactDeployer(
		config.GitHubWorkflowName,
		config.GitHubArtifactName,
		githubBranch,
		config.GitHubRepo,
		config.GitHubToken,
		artifactTracker,
		&logAdapter{log: log.With().Str("component", "github-artifact").Logger()},
	)

	log.Info().
		Str("workflow", config.GitHubWorkflowName).
		Str("artifact", config.GitHubArtifactName).
		Str("branch", githubBranch).
		Str("repo", config.GitHubRepo).
		Msg("GitHub artifact deployment enabled (REQUIRED - no on-device building)")

	return &Manager{
		config:                 config,
		log:                    log.With().Str("component", "deployment").Logger(),
		statusFile:             filepath.Join(config.DeployDir, "deployment_status.json"),
		version:                version,
		gitCommit:              getEnv("GIT_COMMIT", "unknown"),
		gitBranch:              config.GitBranch,
		lock:                   lock,
		binaryDeployer:         binaryDeployer,
		serviceManager:         serviceManager,
		dockerManager:          dockerManager,
		sketchDeployer:         sketchDeployer,
		githubArtifactDeployer: githubArtifactDeployer,
		artifactTracker:        artifactTracker,
	}
}

// Deploy performs the complete deployment workflow
func (m *Manager) Deploy() (*DeploymentResult, error) {
	startTime := time.Now()
	result := &DeploymentResult{
		Success:          false,
		Deployed:         false,
		ServicesDeployed: []ServiceDeployment{},
	}

	// Acquire lock
	if err := m.lock.AcquireLock(m.config.LockTimeout); err != nil {
		result.Error = fmt.Sprintf("failed to acquire lock: %v", err)
		result.Duration = time.Since(startTime)
		return result, fmt.Errorf("deployment locked: %w", err)
	}
	defer func() {
		if err := m.lock.ReleaseLock(); err != nil {
			m.log.Error().Err(err).Msg("Failed to release deployment lock")
		}
	}()

	result.CommitBefore = m.gitCommit

	// Check for new GitHub artifact (Go binary)
	var hasNewArtifact bool
	var artifactRunID string
	if m.githubArtifactDeployer != nil {
		runID, err := m.githubArtifactDeployer.CheckForNewBuild()
		if err != nil {
			m.log.Warn().Err(err).Msg("Failed to check for GitHub artifacts")
		} else if runID != "" {
			hasNewArtifact = true
			artifactRunID = runID
			m.log.Info().
				Str("run_id", runID).
				Msg("New GitHub artifact available")
		}
	}

	// If no new artifact, skip deployment
	if !hasNewArtifact {
		m.log.Info().Msg("No new artifacts detected, skipping deployment")
		result.Success = true
		result.Deployed = false
		result.Duration = time.Since(startTime)
		return result, nil
	}

	// Deploy Go binary (only artifact needed - frontend and sketch are embedded)
	// Note: Display app uses App Lab (Python + sketch) - deployed via AppLabDeployer
	deploymentErrors := m.deployServices(result, artifactRunID)

	// Extract and deploy embedded sketch files to ArduinoApps directory
	// The Arduino App Framework will automatically rebuild and upload on app restart
	sketchPaths := []string{"display/sketch/sketch.ino"}
	sketchDeployed := false
	for _, sketchPath := range sketchPaths {
		if err := m.sketchDeployer.DeploySketch(sketchPath); err != nil {
			m.log.Warn().Err(err).Str("sketch", sketchPath).Msg("Failed to deploy sketch (non-fatal)")
		} else {
			sketchDeployed = true
			result.SketchDeployed = true
			break // Only deploy first found sketch
		}
	}

	// Restart App Lab app if sketch files were deployed
	// App Lab framework handles compilation and upload automatically
	if sketchDeployed {
		m.log.Info().Msg("Restarting App Lab app (will auto-compile and upload sketch)")
		if err := m.sketchDeployer.RestartApp(); err != nil {
			m.log.Warn().Err(err).Msg("Failed to restart App Lab app (sketch files deployed, manual restart may be needed)")
		}
	}

	// Check if any deployment succeeded
	successCount := 0
	for _, svc := range result.ServicesDeployed {
		if svc.Success {
			successCount++
		}
	}

	if successCount > 0 {
		result.Deployed = true
		if err := m.MarkDeployed(); err != nil {
			m.log.Warn().Err(err).Msg("Failed to mark deployment")
		}
		// Mark artifact as deployed in tracker to prevent redeployment loops
		if artifactRunID != "" && m.artifactTracker != nil {
			if err := m.artifactTracker.MarkDeployed(artifactRunID); err != nil {
				m.log.Warn().Err(err).Str("run_id", artifactRunID).Msg("Failed to mark artifact as deployed in tracker")
			}
		}
	}

	// Determine overall success
	if len(deploymentErrors) > 0 {
		errorMsgs := []string{}
		for svc, err := range deploymentErrors {
			errorMsgs = append(errorMsgs, fmt.Sprintf("%s: %v", svc, err))
			// Log each service error individually for visibility
			m.log.Error().
				Err(err).
				Str("service", svc).
				Msg("Service deployment failed")
		}
		result.Error = fmt.Sprintf("deployment completed with errors: %v", errorMsgs)
		result.Success = successCount > 0 // Partial success is still success
	} else {
		result.Success = true
	}

	result.Duration = time.Since(startTime)

	logEvent := m.log.Info().
		Bool("success", result.Success).
		Bool("deployed", result.Deployed).
		Dur("duration", result.Duration).
		Int("services", len(result.ServicesDeployed))

	// Include error in log if present
	if result.Error != "" {
		logEvent = logEvent.Str("error", result.Error)
	}

	logEvent.Msg("Deployment completed")

	return result, nil
}

// HardUpdate performs a complete deployment without change detection
// It forces all components to be rebuilt, deployed, and restarted
func (m *Manager) HardUpdate() (*DeploymentResult, error) {
	startTime := time.Now()
	result := &DeploymentResult{
		Success:          false,
		Deployed:         true, // Hard update always deploys
		ServicesDeployed: []ServiceDeployment{},
	}

	m.log.Info().Msg("Starting hard update - forcing all deployments")

	// Acquire lock
	if err := m.lock.AcquireLock(m.config.LockTimeout); err != nil {
		result.Error = fmt.Sprintf("failed to acquire lock: %v", err)
		result.Duration = time.Since(startTime)
		return result, fmt.Errorf("deployment locked: %w", err)
	}
	defer func() {
		if err := m.lock.ReleaseLock(); err != nil {
			m.log.Error().Err(err).Msg("Failed to release deployment lock")
		}
	}()

	result.CommitBefore = m.gitCommit

	// Force download of latest Go binary artifact (empty runID will trigger CheckForNewBuild)
	deploymentErrors := make(map[string]error)
	var wg sync.WaitGroup
	var mu sync.Mutex

	// Deploy Sentinel service (always - force download latest)
	wg.Add(1)
	go func() {
		defer wg.Done()
		deployment := m.deployGoService(m.config.TraderConfig, "sentinel", "")
		mu.Lock()
		result.ServicesDeployed = append(result.ServicesDeployed, deployment)
		if !deployment.Success {
			deploymentErrors[deployment.ServiceName] = fmt.Errorf(deployment.Error)
		}
		mu.Unlock()
	}()

	wg.Wait()

	// Note: Python display app has been removed - MCU communication is now direct via Go

	// Extract and deploy embedded sketch files (always, non-fatal)
	sketchPaths := []string{"display/sketch/sketch.ino"}
	sketchDeployed := false
	for _, sketchPath := range sketchPaths {
		if err := m.sketchDeployer.DeploySketch(sketchPath); err != nil {
			m.log.Warn().Err(err).Str("sketch", sketchPath).Msg("Failed to deploy sketch (non-fatal)")
		} else {
			sketchDeployed = true
			result.SketchDeployed = true
			break // Only deploy first found sketch
		}
	}

	// Restart App Lab app if sketch files were deployed
	// App Lab framework handles compilation and upload automatically
	if sketchDeployed {
		m.log.Info().Msg("Restarting App Lab app (will auto-compile and upload sketch)")
		if err := m.sketchDeployer.RestartApp(); err != nil {
			m.log.Warn().Err(err).Msg("Failed to restart App Lab app (sketch files deployed, manual restart may be needed)")
		}
	}

	// Note: Go services (Sentinel) are already restarted by deployGoService above
	// No additional restart needed here

	// Mark as deployed
	if err := m.MarkDeployed(); err != nil {
		m.log.Warn().Err(err).Msg("Failed to mark deployment")
	}

	// Determine overall success
	successCount := 0
	for _, svc := range result.ServicesDeployed {
		if svc.Success {
			successCount++
		}
	}

	if len(deploymentErrors) > 0 {
		errorMsgs := []string{}
		for svc, err := range deploymentErrors {
			errorMsgs = append(errorMsgs, fmt.Sprintf("%s: %v", svc, err))
		}
		result.Error = fmt.Sprintf("hard update completed with errors: %v", errorMsgs)
		result.Success = successCount > 0 // Partial success is still success
	} else {
		result.Success = true
	}

	result.Duration = time.Since(startTime)

	m.log.Info().
		Bool("success", result.Success).
		Bool("deployed", result.Deployed).
		Dur("duration", result.Duration).
		Int("services", len(result.ServicesDeployed)).
		Msg("Hard update completed")

	return result, nil
}

// deployServices deploys the Go binary service
// runID is the GitHub Actions run ID to deploy. If empty, deployGoService will check for new builds.
func (m *Manager) deployServices(result *DeploymentResult, runID string) map[string]error {
	errors := make(map[string]error)
	var wg sync.WaitGroup
	var mu sync.Mutex

	// Deploy Sentinel service (always deploy if artifact is available)
	wg.Add(1)
	go func() {
		defer wg.Done()
		deployment := m.deployGoService(m.config.TraderConfig, "sentinel", runID)
		mu.Lock()
		result.ServicesDeployed = append(result.ServicesDeployed, deployment)
		if !deployment.Success {
			errors[deployment.ServiceName] = fmt.Errorf(deployment.Error)
		}
		mu.Unlock()
	}()

	wg.Wait()

	return errors
}

// deployGoService deploys a single Go service
// runID is the GitHub Actions run ID to deploy. If empty, DeployLatest will check for new builds.
func (m *Manager) deployGoService(config GoServiceConfig, serviceName string, runID string) ServiceDeployment {
	deployment := ServiceDeployment{
		ServiceName: serviceName,
		ServiceType: "go",
		Success:     false,
	}

	// Prepare temp directory
	tempDir := filepath.Join(m.config.DeployDir, ".tmp")
	if err := os.MkdirAll(tempDir, 0755); err != nil {
		deployment.Error = fmt.Sprintf("failed to create temp directory: %v", err)
		return deployment
	}

	// BOOTSTRAP: Check if a binary already exists in .tmp from a previous failed deployment
	// This handles the chicken-and-egg problem where old code downloaded new binary but couldn't deploy it
	isSelfDeployment := serviceName == "sentinel"
	if isSelfDeployment {
		existingBinary := filepath.Join(tempDir, m.githubArtifactDeployer.artifactName)
		if info, err := os.Stat(existingBinary); err == nil && !info.IsDir() {
			m.log.Info().
				Str("service", serviceName).
				Str("existing_binary", existingBinary).
				Msg("Found existing downloaded binary - using self-deployment mechanism for bootstrap")

			// Verify architecture before deploying
			if err := m.githubArtifactDeployer.VerifyBinaryArchitecture(existingBinary); err != nil {
				m.log.Warn().
					Err(err).
					Str("binary", existingBinary).
					Msg("Existing binary failed architecture verification - will download fresh")
				os.Remove(existingBinary)
			} else {
				// Use self-deployment mechanism to deploy this binary
				m.log.Info().
					Str("service", serviceName).
					Str("binary_path", existingBinary).
					Msg("Deploying existing binary using self-deployment mechanism")

				// Deploy binary (atomic swap) while service is still running
				if err := m.binaryDeployer.DeployBinary(existingBinary, m.config.DeployDir, config.BinaryName, true); err != nil {
					deployment.Error = fmt.Sprintf("bootstrap deployment failed: %v", err)
					m.log.Error().
						Err(err).
						Str("service", serviceName).
						Msg("Failed to deploy existing binary")
					return deployment
				}

				m.log.Info().
					Str("service", serviceName).
					Str("binary_path", filepath.Join(m.config.DeployDir, config.BinaryName)).
					Msg("Bootstrap: Binary replaced successfully - will now exit for systemd restart")

				// Clean up temp binary
				os.Remove(existingBinary)

				// Exit gracefully to trigger systemd restart with new binary
				m.log.Info().
					Str("service", serviceName).
					Msg("Bootstrap: Exiting process to allow systemd restart with new binary (Restart=always)")

				// Give logs time to flush
				time.Sleep(100 * time.Millisecond)

				// Exit with success code - systemd will restart us
				os.Exit(0)

				// Unreachable
				deployment.Success = true
				return deployment
			}
		}
	}

	// GitHub artifact deployment is REQUIRED - no fallback to on-device building
	// This ensures we always use pre-built linux/arm64 binaries from GitHub Actions
	if m.githubArtifactDeployer == nil {
		deployment.Error = "GitHub artifact deployment is required but not configured. Cannot build on-device."
		return deployment
	}

	m.log.Info().
		Str("service", serviceName).
		Msg("Checking for GitHub artifact (REQUIRED - no on-device building)")

	// Download latest artifact (will verify linux/arm64 architecture)
	// Pass runID to DeployLatest - if provided, it will skip CheckForNewBuild()
	downloadedPath, err := m.githubArtifactDeployer.DeployLatest(tempDir, runID)
	if err != nil {
		deployment.Error = fmt.Sprintf("failed to download artifact: %v", err)
		m.log.Error().
			Err(err).
			Str("service", serviceName).
			Str("run_id", runID).
			Str("temp_dir", tempDir).
			Msg("Failed to download artifact from GitHub")
		return deployment
	}

	if downloadedPath == "" {
		m.log.Debug().
			Str("service", serviceName).
			Msg("No new artifact available")
		deployment.Error = "no new artifact available"
		deployment.Success = true // Not an error, just nothing to deploy
		return deployment
	}

	tempBinary := downloadedPath
	m.log.Info().
		Str("service", serviceName).
		Str("binary", tempBinary).
		Msg("Downloaded and verified linux/arm64 artifact from GitHub Actions")

	// SELF-DEPLOYMENT: Special handling when Sentinel updates itself
	// We can't use systemctl/dbus from within a NoNewPrivileges service
	// Instead: replace binary, mark deployed, exit gracefully → systemd restarts us (Restart=always)
	// (isSelfDeployment already declared in bootstrap section above)

	if isSelfDeployment {
		m.log.Info().
			Str("service", serviceName).
			Msg("Self-deployment detected - using systemd-native restart mechanism")

		// Deploy binary (atomic swap) while service is still running
		if err := m.binaryDeployer.DeployBinary(tempBinary, m.config.DeployDir, config.BinaryName, true); err != nil {
			deployment.Error = fmt.Sprintf("deployment failed: %v", err)
			m.log.Error().
				Err(err).
				Str("service", serviceName).
				Msg("Failed to deploy binary for self-update")
			return deployment
		}

		m.log.Info().
			Str("service", serviceName).
			Str("binary_path", filepath.Join(m.config.DeployDir, config.BinaryName)).
			Msg("Binary replaced successfully - will now exit for systemd restart")

		// Mark artifact as deployed before exiting
		if runID != "" && m.githubArtifactDeployer != nil && m.githubArtifactDeployer.tracker != nil {
			if err := m.githubArtifactDeployer.tracker.MarkDeployed(runID); err != nil {
				m.log.Warn().Err(err).Str("run_id", runID).Msg("Failed to mark artifact as deployed before restart")
			} else {
				m.log.Info().Str("run_id", runID).Msg("Marked artifact as deployed - ready for restart")
			}
		}

		// Exit gracefully to trigger systemd restart with new binary
		// systemd's Restart=always will start the new binary
		m.log.Info().
			Str("service", serviceName).
			Msg("Exiting process to allow systemd restart with new binary (Restart=always)")

		// Give logs time to flush
		time.Sleep(100 * time.Millisecond)

		// Exit with success code - systemd will restart us
		os.Exit(0)

		// This code is unreachable, but needed for compilation
		deployment.Success = true
		return deployment
	}

	// EXTERNAL SERVICE DEPLOYMENT: Normal flow for other services
	// These don't have NoNewPrivileges restrictions from our perspective

	// Stop service before binary replacement
	if err := m.serviceManager.StopService(config.ServiceName); err != nil {
		deployment.Error = fmt.Sprintf("service stop failed: %v", err)
		return deployment
	}

	// Deploy binary (atomic swap)
	if err := m.binaryDeployer.DeployBinary(tempBinary, m.config.DeployDir, config.BinaryName, true); err != nil {
		deployment.Error = fmt.Sprintf("deployment failed: %v", err)
		// Try to start service even if deployment failed
		if startErr := m.serviceManager.StartService(config.ServiceName); startErr != nil {
			m.log.Error().Err(startErr).Str("service", config.ServiceName).Msg("Failed to start service after deployment failure")
		}
		return deployment
	}

	// Start service after binary replacement
	if err := m.serviceManager.StartService(config.ServiceName); err != nil {
		deployment.Error = fmt.Sprintf("service start failed: %v", err)
		return deployment
	}

	// Health check (only for Sentinel, bridge may not have health endpoint)
	if serviceName == "sentinel" {
		healthURL := fmt.Sprintf("http://%s:%d/health", m.config.APIHost, m.config.APIPort)
		if err := m.serviceManager.CheckHealth(healthURL, m.config.HealthCheckMaxAttempts, m.config.HealthCheckTimeout); err != nil {
			deployment.Error = fmt.Sprintf("health check failed: %v", err)
			return deployment
		}
	}

	// Mark artifact as deployed ONLY after successful deployment (binary deploy, restart, health check)
	// This ensures we don't mark as deployed if any step fails
	if runID != "" && m.githubArtifactDeployer != nil && m.githubArtifactDeployer.tracker != nil {
		if err := m.githubArtifactDeployer.tracker.MarkDeployed(runID); err != nil {
			m.log.Warn().Err(err).Str("run_id", runID).Msg("Failed to mark artifact as deployed after successful deployment")
		} else {
			m.log.Info().Str("run_id", runID).Msg("Marked artifact as deployed after successful deployment")
		}
	}

	deployment.Success = true
	return deployment
}

// Status represents deployment status (for compatibility)
type Status struct {
	Version         string    `json:"version"`
	DeployedAt      time.Time `json:"deployed_at"`
	GitCommit       string    `json:"git_commit,omitempty"`
	GitBranch       string    `json:"git_branch,omitempty"`
	LastChecked     time.Time `json:"last_checked"`
	UpdateAvailable bool      `json:"update_available"`
}

// GetStatus returns the current deployment status (for compatibility)
func (m *Manager) GetStatus() (*Status, error) {
	data, err := os.ReadFile(m.statusFile)
	if err != nil {
		if os.IsNotExist(err) {
			status := &Status{
				Version:         m.version,
				DeployedAt:      time.Now(),
				GitCommit:       m.gitCommit,
				GitBranch:       m.gitBranch,
				LastChecked:     time.Now(),
				UpdateAvailable: false,
			}
			return status, nil
		}
		return nil, fmt.Errorf("failed to load status: %w", err)
	}

	var status Status
	if err := json.Unmarshal(data, &status); err != nil {
		return nil, fmt.Errorf("failed to parse status: %w", err)
	}

	status.LastChecked = time.Now()
	return &status, nil
}

// MarkDeployed marks a new deployment
func (m *Manager) MarkDeployed() error {
	status := &Status{
		Version:         m.version,
		DeployedAt:      time.Now(),
		GitCommit:       m.gitCommit,
		GitBranch:       m.gitBranch,
		LastChecked:     time.Now(),
		UpdateAvailable: false,
	}

	data, err := json.MarshalIndent(status, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal status: %w", err)
	}

	if err := os.WriteFile(m.statusFile, data, 0644); err != nil {
		return fmt.Errorf("failed to write status file: %w", err)
	}

	return nil
}

// GetUptime returns the time since deployment
func (m *Manager) GetUptime() (time.Duration, error) {
	status, err := m.GetStatus()
	if err != nil {
		return 0, err
	}

	return time.Since(status.DeployedAt), nil
}

// logAdapter adapts zerolog.Logger to our Logger interface
type logAdapter struct {
	log zerolog.Logger
}

func (l *logAdapter) Debug() LogEvent {
	return &logEventAdapter{event: l.log.Debug()}
}

func (l *logAdapter) Info() LogEvent {
	return &logEventAdapter{event: l.log.Info()}
}

func (l *logAdapter) Warn() LogEvent {
	return &logEventAdapter{event: l.log.Warn()}
}

func (l *logAdapter) Error() LogEvent {
	return &logEventAdapter{event: l.log.Error()}
}

type logEventAdapter struct {
	event *zerolog.Event
}

func (e *logEventAdapter) Str(key, value string) LogEvent {
	e.event = e.event.Str(key, value)
	return e
}

func (e *logEventAdapter) Int(key string, value int) LogEvent {
	e.event = e.event.Int(key, value)
	return e
}

func (e *logEventAdapter) Err(err error) LogEvent {
	e.event = e.event.Err(err)
	return e
}

func (e *logEventAdapter) Msg(msg string) {
	e.event.Msg(msg)
}

func (e *logEventAdapter) Dur(key string, value time.Duration) LogEvent {
	e.event = e.event.Dur(key, value)
	return e
}

func (e *logEventAdapter) Bool(key string, value bool) LogEvent {
	e.event = e.event.Bool(key, value)
	return e
}

func (e *logEventAdapter) Interface(key string, value interface{}) LogEvent {
	e.event = e.event.Interface(key, value)
	return e
}

// getEnv gets environment variable with fallback
func getEnv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
