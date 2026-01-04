package deployment

import "fmt"

// GitFetchError represents an error during git fetch
type GitFetchError struct {
	Message string
	Err     error
}

func (e *GitFetchError) Error() string {
	if e.Err != nil {
		return fmt.Sprintf("git fetch error: %s: %v", e.Message, e.Err)
	}
	return fmt.Sprintf("git fetch error: %s", e.Message)
}

func (e *GitFetchError) Unwrap() error {
	return e.Err
}

// GitPullError represents an error during git pull
type GitPullError struct {
	Message string
	Err     error
}

func (e *GitPullError) Error() string {
	if e.Err != nil {
		return fmt.Sprintf("git pull error: %s: %v", e.Message, e.Err)
	}
	return fmt.Sprintf("git pull error: %s", e.Message)
}

func (e *GitPullError) Unwrap() error {
	return e.Err
}

// BuildError represents an error during binary build
type BuildError struct {
	ServiceName string
	Message     string
	Err         error
	BuildOutput string
}

func (e *BuildError) Error() string {
	msg := fmt.Sprintf("build error for %s: %s", e.ServiceName, e.Message)
	if e.Err != nil {
		msg += fmt.Sprintf(": %v", e.Err)
	}
	if e.BuildOutput != "" {
		msg += fmt.Sprintf("\nBuild output: %s", e.BuildOutput)
	}
	return msg
}

func (e *BuildError) Unwrap() error {
	return e.Err
}

// DeploymentError represents a general deployment error
type DeploymentError struct {
	Message string
	Err     error
}

func (e *DeploymentError) Error() string {
	if e.Err != nil {
		return fmt.Sprintf("deployment error: %s: %v", e.Message, e.Err)
	}
	return fmt.Sprintf("deployment error: %s", e.Message)
}

func (e *DeploymentError) Unwrap() error {
	return e.Err
}

// ServiceRestartError represents an error during service restart
type ServiceRestartError struct {
	ServiceName string
	Message     string
	Err         error
}

func (e *ServiceRestartError) Error() string {
	msg := fmt.Sprintf("service restart error for %s: %s", e.ServiceName, e.Message)
	if e.Err != nil {
		msg += fmt.Sprintf(": %v", e.Err)
	}
	return msg
}

func (e *ServiceRestartError) Unwrap() error {
	return e.Err
}

// HealthCheckError represents an error during health check
type HealthCheckError struct {
	ServiceName string
	Message     string
	Err         error
}

func (e *HealthCheckError) Error() string {
	msg := fmt.Sprintf("health check error for %s: %s", e.ServiceName, e.Message)
	if e.Err != nil {
		msg += fmt.Sprintf(": %v", e.Err)
	}
	return msg
}

func (e *HealthCheckError) Unwrap() error {
	return e.Err
}

// SketchCompilationError represents an error during sketch compilation
type SketchCompilationError struct {
	Message string
	Err     error
}

func (e *SketchCompilationError) Error() string {
	if e.Err != nil {
		return fmt.Sprintf("sketch compilation error: %s: %v", e.Message, e.Err)
	}
	return fmt.Sprintf("sketch compilation error: %s", e.Message)
}

func (e *SketchCompilationError) Unwrap() error {
	return e.Err
}

// SketchUploadError represents an error during sketch upload
type SketchUploadError struct {
	Message string
	Err     error
}

func (e *SketchUploadError) Error() string {
	if e.Err != nil {
		return fmt.Sprintf("sketch upload error: %s: %v", e.Message, e.Err)
	}
	return fmt.Sprintf("sketch upload error: %s", e.Message)
}

func (e *SketchUploadError) Unwrap() error {
	return e.Err
}
