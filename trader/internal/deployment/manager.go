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
	RepoDir                string
	DeployDir              string
	APIPort                int
	APIHost                string
	Enabled                bool
	TraderConfig           GoServiceConfig
	DockerComposePath      string
	MicroservicesEnabled   bool
	LockTimeout            time.Duration
	HealthCheckTimeout     time.Duration
	HealthCheckMaxAttempts int
	GitBranch              string
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
	lock               *DeploymentLock
	gitChecker         *GitChecker
	goBuilder          *GoServiceBuilder
	binaryDeployer     *BinaryDeployer
	frontendDeployer   *FrontendDeployer
	displayAppDeployer *DisplayAppDeployer
	serviceManager     *ServiceManager
	dockerManager      *DockerManager
	microDeployer      *MicroserviceDeployer
	sketchDeployer     *SketchDeployer
}

// NewManager creates a new deployment manager
func NewManager(config *DeploymentConfig, version string, log zerolog.Logger) *Manager {
	// Resolve paths to absolute (required for reliable path operations)
	absRepoDir, err := filepath.Abs(config.RepoDir)
	if err != nil {
		log.Warn().Err(err).Str("repo_dir", config.RepoDir).Msg("Failed to resolve RepoDir to absolute path, using as-is")
		absRepoDir = config.RepoDir
	}

	absDeployDir, err := filepath.Abs(config.DeployDir)
	if err != nil {
		log.Warn().Err(err).Str("deploy_dir", config.DeployDir).Msg("Failed to resolve DeployDir to absolute path, using as-is")
		absDeployDir = config.DeployDir
	}

	// Update config with absolute paths
	config.RepoDir = absRepoDir
	config.DeployDir = absDeployDir

	// Create components
	lock := NewDeploymentLock(
		filepath.Join(config.DeployDir, ".deploy.lock"),
		&logAdapter{log: log.With().Str("component", "lock").Logger()},
	)

	gitChecker := NewGitChecker(
		config.RepoDir,
		&logAdapter{log: log.With().Str("component", "git").Logger()},
	)

	goBuilder := NewGoServiceBuilder(
		&logAdapter{log: log.With().Str("component", "builder").Logger()},
	)

	binaryDeployer := NewBinaryDeployer(
		&logAdapter{log: log.With().Str("component", "binary").Logger()},
	)

	frontendDeployer := NewFrontendDeployer(
		&logAdapter{log: log.With().Str("component", "frontend").Logger()},
	)

	serviceManager := NewServiceManager(
		&logAdapter{log: log.With().Str("component", "service").Logger()},
	)

	dockerManager := NewDockerManager(
		config.DockerComposePath,
		&logAdapter{log: log.With().Str("component", "docker").Logger()},
	)

	microDeployer := NewMicroserviceDeployer(
		dockerManager,
		serviceManager,
		&logAdapter{log: log.With().Str("component", "microservices").Logger()},
	)

	sketchDeployer := NewSketchDeployer(
		&logAdapter{log: log.With().Str("component", "sketch").Logger()},
	)

	return &Manager{
		config:           config,
		log:              log.With().Str("component", "deployment").Logger(),
		statusFile:       filepath.Join(config.DeployDir, "deployment_status.json"),
		version:          version,
		gitCommit:        getEnv("GIT_COMMIT", "unknown"),
		gitBranch:        config.GitBranch,
		lock:             lock,
		gitChecker:       gitChecker,
		goBuilder:        goBuilder,
		binaryDeployer:   binaryDeployer,
		frontendDeployer: frontendDeployer,
		displayAppDeployer: NewDisplayAppDeployer(
			&logAdapter{log: log.With().Str("component", "display-app").Logger()},
		),
		serviceManager: serviceManager,
		dockerManager:  dockerManager,
		microDeployer:  microDeployer,
		sketchDeployer: sketchDeployer,
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

	// Ensure safe directory
	if err := m.gitChecker.EnsureSafeDirectory(); err != nil {
		m.log.Warn().Err(err).Msg("Failed to ensure git safe directory")
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

	// Get current commit
	currentBranch := m.config.GitBranch
	if currentBranch == "" {
		var err error
		currentBranch, err = m.gitChecker.GetCurrentBranch()
		if err != nil {
			currentBranch = "main"
		}
	}

	result.CommitBefore = m.gitCommit

	// Fetch updates
	if err := m.gitChecker.FetchUpdates(3); err != nil {
		result.Error = fmt.Sprintf("failed to fetch updates: %v", err)
		result.Duration = time.Since(startTime)
		return result, err
	}

	// Check for changes
	hasChanges, localCommit, remoteCommit, err := m.gitChecker.HasChanges(currentBranch)
	if err != nil {
		result.Error = fmt.Sprintf("failed to check for changes: %v", err)
		result.Duration = time.Since(startTime)
		return result, err
	}

	result.CommitBefore = localCommit

	if !hasChanges {
		m.log.Info().Msg("No changes detected, skipping deployment")
		result.Success = true
		result.Deployed = false
		result.Duration = time.Since(startTime)
		return result, nil
	}

	// Get changed files
	changedFiles, err := m.gitChecker.GetChangedFiles(localCommit, remoteCommit)
	if err != nil {
		result.Error = fmt.Sprintf("failed to get changed files: %v", err)
		result.Duration = time.Since(startTime)
		return result, err
	}

	// Categorize changes
	categories := m.gitChecker.CategorizeChanges(changedFiles)
	if !categories.HasAnyChanges() {
		m.log.Info().Msg("No relevant changes detected, skipping deployment")
		result.Success = true
		result.Deployed = false
		result.Duration = time.Since(startTime)
		return result, nil
	}

	m.log.Info().
		Interface("categories", categories).
		Msg("Changes detected, starting deployment")

	// Pull changes
	if err := m.gitChecker.PullChanges(currentBranch); err != nil {
		result.Error = fmt.Sprintf("failed to pull changes: %v", err)
		result.Duration = time.Since(startTime)
		return result, err
	}

	result.CommitAfter = remoteCommit

	// Deploy based on categories
	deploymentErrors := m.deployServices(categories, result)

	// Deploy frontend (pre-built, committed to git)
	if categories.Frontend {
		if err := m.frontendDeployer.DeployFrontend(m.config.RepoDir, m.config.DeployDir); err != nil {
			m.log.Error().Err(err).Msg("Failed to deploy frontend")
		}
	}

	// Deploy display app (Python files for Arduino App Framework)
	if categories.DisplayApp {
		if err := m.displayAppDeployer.DeployDisplayApp(m.config.RepoDir); err != nil {
			m.log.Error().Err(err).Msg("Failed to deploy display app")
		}
	}

	// Deploy sketch (non-fatal)
	if categories.Sketch {
		sketchPaths := []string{"display/sketch/sketch.ino", "arduino-app/sketch/sketch.ino"}
		for _, sketchPath := range sketchPaths {
			if err := m.sketchDeployer.DeploySketch(sketchPath, m.config.RepoDir); err != nil {
				m.log.Warn().Err(err).Str("sketch", sketchPath).Msg("Failed to deploy sketch (non-fatal)")
			} else {
				result.SketchDeployed = true
				break // Only deploy first found sketch
			}
		}
	}

	// Check if any deployment succeeded
	successCount := 0
	for _, svc := range result.ServicesDeployed {
		if svc.Success {
			successCount++
		}
	}

	if successCount > 0 || categories.Frontend {
		result.Deployed = true
		if err := m.MarkDeployed(); err != nil {
			m.log.Warn().Err(err).Msg("Failed to mark deployment")
		}
	}

	// Determine overall success
	if len(deploymentErrors) > 0 {
		errorMsgs := []string{}
		for svc, err := range deploymentErrors {
			errorMsgs = append(errorMsgs, fmt.Sprintf("%s: %v", svc, err))
		}
		result.Error = fmt.Sprintf("deployment completed with errors: %v", errorMsgs)
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
		Msg("Deployment completed")

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

	// Ensure safe directory
	if err := m.gitChecker.EnsureSafeDirectory(); err != nil {
		m.log.Warn().Err(err).Msg("Failed to ensure git safe directory")
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

	// Get current commit
	currentBranch := m.config.GitBranch
	if currentBranch == "" {
		var err error
		currentBranch, err = m.gitChecker.GetCurrentBranch()
		if err != nil {
			currentBranch = "main"
		}
	}

	// Get current commit before update
	_, localCommit, remoteCommit, err := m.gitChecker.HasChanges(currentBranch)
	if err != nil {
		m.log.Warn().Err(err).Msg("Failed to get current commits")
		localCommit = "unknown"
		remoteCommit = "unknown"
	}
	result.CommitBefore = localCommit

	// Fetch updates
	if err := m.gitChecker.FetchUpdates(3); err != nil {
		result.Error = fmt.Sprintf("failed to fetch updates: %v", err)
		result.Duration = time.Since(startTime)
		return result, err
	}

	// Pull changes (skip change detection - always pull)
	if err := m.gitChecker.PullChanges(currentBranch); err != nil {
		result.Error = fmt.Sprintf("failed to pull changes: %v", err)
		result.Duration = time.Since(startTime)
		return result, err
	}

	// Get commit after update (should be same as remote now)
	_, _, newRemoteCommit, err := m.gitChecker.HasChanges(currentBranch)
	if err != nil {
		m.log.Warn().Err(err).Msg("Failed to get commit after pull")
		result.CommitAfter = remoteCommit // Use the remote commit we got earlier
	} else {
		result.CommitAfter = newRemoteCommit
	}

	deploymentErrors := make(map[string]error)
	var wg sync.WaitGroup
	var mu sync.Mutex

	// Deploy trader service (always)
	wg.Add(1)
	go func() {
		defer wg.Done()
		deployment := m.deployGoService(m.config.TraderConfig, "trader")
		mu.Lock()
		result.ServicesDeployed = append(result.ServicesDeployed, deployment)
		if !deployment.Success {
			deploymentErrors[deployment.ServiceName] = fmt.Errorf(deployment.Error)
		}
		mu.Unlock()
	}()

	// Display bridge service is deprecated (replaced by Python app managed by Arduino App Framework)
	// No longer deploying Go display-bridge binary

	wg.Wait()

	// Deploy microservices (always, with rebuild)
	if m.config.MicroservicesEnabled {
		servicesToDeploy := map[string]bool{
			"pypfopt":   true, // Always rebuild
			"tradernet": true, // Always rebuild
		}

		for serviceName, rebuildImage := range servicesToDeploy {
			deployment := ServiceDeployment{
				ServiceName: serviceName,
				ServiceType: "docker", // Default, will be updated for native services
				Success:     true,
			}

			// Set correct service type
			if m.microDeployer.IsNativeService(serviceName) {
				deployment.ServiceType = "systemd"
			}

			if err := m.microDeployer.DeployMicroservice(serviceName, m.config.RepoDir, rebuildImage); err != nil {
				deployment.Success = false
				deployment.Error = err.Error()
				deploymentErrors[serviceName] = err
				m.log.Error().Err(err).Str("service", serviceName).Msg("Failed to deploy microservice")
			} else {
				// Health check
				healthURL := m.microDeployer.GetMicroserviceHealthURL(serviceName)
				if err := m.microDeployer.CheckMicroserviceHealth(serviceName, m.config.RepoDir, healthURL); err != nil {
					m.log.Warn().Err(err).Str("service", serviceName).Msg("Health check failed")
				}
			}

			result.ServicesDeployed = append(result.ServicesDeployed, deployment)
		}
	}

	// Deploy frontend (always)
	if err := m.frontendDeployer.DeployFrontend(m.config.RepoDir, m.config.DeployDir); err != nil {
		m.log.Error().Err(err).Msg("Failed to deploy frontend")
		deploymentErrors["frontend"] = err
	}

	// Deploy display app (always, Python files for Arduino App Framework)
	if err := m.displayAppDeployer.DeployDisplayApp(m.config.RepoDir); err != nil {
		m.log.Error().Err(err).Msg("Failed to deploy display app")
		deploymentErrors["display-app"] = err
	}

	// Deploy sketch (always, non-fatal)
	sketchPaths := []string{"display/sketch/sketch.ino", "arduino-app/sketch/sketch.ino"}
	for _, sketchPath := range sketchPaths {
		if err := m.sketchDeployer.DeploySketch(sketchPath, m.config.RepoDir); err != nil {
			m.log.Warn().Err(err).Str("sketch", sketchPath).Msg("Failed to deploy sketch (non-fatal)")
		} else {
			result.SketchDeployed = true
			break // Only deploy first found sketch
		}
	}

	// Restart all services
	servicesToRestart := []string{
		m.config.TraderConfig.ServiceName,
	}

	// Restart Go services via systemd
	restartErrors := m.serviceManager.RestartServices(servicesToRestart)
	for serviceName, err := range restartErrors {
		m.log.Error().Err(err).Str("service", serviceName).Msg("Failed to restart service")
		deploymentErrors[serviceName+"_restart"] = err
	}

	// Note: Python microservices are already restarted by DeployMicroservice above,
	// so no explicit restart needed here

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

// deployServices deploys services based on change categories
func (m *Manager) deployServices(categories *ChangeCategories, result *DeploymentResult) map[string]error {
	errors := make(map[string]error)
	var wg sync.WaitGroup
	var mu sync.Mutex

	// Deploy trader service
	if categories.MainApp {
		wg.Add(1)
		go func() {
			defer wg.Done()
			deployment := m.deployGoService(m.config.TraderConfig, "trader")
			mu.Lock()
			result.ServicesDeployed = append(result.ServicesDeployed, deployment)
			if !deployment.Success {
				errors[deployment.ServiceName] = fmt.Errorf(deployment.Error)
			}
			mu.Unlock()
		}()
	}

	// Display bridge service is deprecated (replaced by Python app managed by Arduino App Framework)
	// No longer deploying Go display-bridge binary

	wg.Wait()

	// Deploy microservices (sequential to avoid resource conflicts)
	if m.config.MicroservicesEnabled {
		servicesToDeploy := make(map[string]bool)

		if categories.PyPFOpt || categories.PyPFOptDeps {
			servicesToDeploy["pypfopt"] = categories.PyPFOptDeps
		}

		if categories.Tradernet || categories.TradernetDeps {
			servicesToDeploy["tradernet"] = categories.TradernetDeps
		}

		for serviceName, rebuildImage := range servicesToDeploy {
			deployment := ServiceDeployment{
				ServiceName: serviceName,
				ServiceType: "docker", // Default, will be updated for native services
				Success:     true,
			}

			// Set correct service type
			if m.microDeployer.IsNativeService(serviceName) {
				deployment.ServiceType = "systemd"
			}

			if err := m.microDeployer.DeployMicroservice(serviceName, m.config.RepoDir, rebuildImage); err != nil {
				deployment.Success = false
				deployment.Error = err.Error()
				errors[serviceName] = err
			} else {
				// Health check
				healthURL := m.microDeployer.GetMicroserviceHealthURL(serviceName)
				if err := m.microDeployer.CheckMicroserviceHealth(serviceName, m.config.RepoDir, healthURL); err != nil {
					m.log.Warn().Err(err).Str("service", serviceName).Msg("Health check failed")
				}
			}

			result.ServicesDeployed = append(result.ServicesDeployed, deployment)
		}
	}

	return errors
}

// deployGoService deploys a single Go service
func (m *Manager) deployGoService(config GoServiceConfig, serviceName string) ServiceDeployment {
	deployment := ServiceDeployment{
		ServiceName: serviceName,
		ServiceType: "go",
		Success:     false,
	}

	// Build to temp location
	tempDir := filepath.Join(m.config.DeployDir, ".tmp")
	if err := os.MkdirAll(tempDir, 0755); err != nil {
		deployment.Error = fmt.Sprintf("failed to create temp directory: %v", err)
		return deployment
	}

	tempBinary := filepath.Join(tempDir, fmt.Sprintf("%s.tmp", config.BinaryName))

	// Build service
	if err := m.goBuilder.BuildService(config, m.config.RepoDir, tempBinary); err != nil {
		deployment.Error = fmt.Sprintf("build failed: %v", err)
		return deployment
	}

	// Deploy binary (atomic swap)
	if err := m.binaryDeployer.DeployBinary(tempBinary, m.config.DeployDir, config.BinaryName, true); err != nil {
		deployment.Error = fmt.Sprintf("deployment failed: %v", err)
		return deployment
	}

	// Restart service
	if err := m.serviceManager.RestartService(config.ServiceName); err != nil {
		deployment.Error = fmt.Sprintf("service restart failed: %v", err)
		return deployment
	}

	// Health check (only for trader, bridge may not have health endpoint)
	if serviceName == "trader" {
		healthURL := fmt.Sprintf("http://%s:%d/health", m.config.APIHost, m.config.APIPort)
		if err := m.serviceManager.CheckHealth(healthURL, m.config.HealthCheckMaxAttempts, m.config.HealthCheckTimeout); err != nil {
			deployment.Error = fmt.Sprintf("health check failed: %v", err)
			return deployment
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
