package deployment

import (
	"errors"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// noopLogger implements Logger interface with no-op methods
type noopLogger struct{}

func (n *noopLogger) Debug() LogEvent { return &noopLogEvent{} }
func (n *noopLogger) Info() LogEvent  { return &noopLogEvent{} }
func (n *noopLogger) Warn() LogEvent  { return &noopLogEvent{} }
func (n *noopLogger) Error() LogEvent { return &noopLogEvent{} }

type noopLogEvent struct{}

func (n *noopLogEvent) Str(string, string) LogEvent            { return n }
func (n *noopLogEvent) Int(string, int) LogEvent               { return n }
func (n *noopLogEvent) Err(error) LogEvent                     { return n }
func (n *noopLogEvent) Dur(string, time.Duration) LogEvent     { return n }
func (n *noopLogEvent) Bool(string, bool) LogEvent             { return n }
func (n *noopLogEvent) Interface(string, interface{}) LogEvent { return n }
func (n *noopLogEvent) Msg(string)                             {}

func TestGitChecker_CategorizeChanges(t *testing.T) {
	log := &noopLogger{}
	checker := NewGitChecker("/tmp/test-repo", log)

	tests := []struct {
		name        string
		files       []string
		want        ChangeCategories
		description string
	}{
		{
			name: "trader service code changes",
			files: []string{
				"trader/internal/server/server.go",
				"trader/cmd/server/main.go",
			},
			want:        ChangeCategories{MainApp: true},
			description: "Changes to trader Go code should trigger MainApp deployment",
		},
		{
			name:        "trader go.mod changes",
			files:       []string{"trader/go.mod"},
			want:        ChangeCategories{MainApp: true},
			description: "Changes to go.mod should trigger MainApp deployment",
		},
		{
			name:        "trader go.sum changes",
			files:       []string{"trader/go.sum"},
			want:        ChangeCategories{MainApp: true},
			description: "Changes to go.sum should trigger MainApp deployment",
		},
		{
			name:        "trader static assets excluded from MainApp",
			files:       []string{"trader/static/css/styles.css"},
			want:        ChangeCategories{Static: true},
			description: "Static assets should not trigger MainApp rebuild, only static deployment",
		},
		{
			name: "trader code and static both changed",
			files: []string{
				"trader/internal/server/server.go",
				"trader/static/js/app.js",
			},
			want:        ChangeCategories{MainApp: true, Static: true},
			description: "Both MainApp and Static should be set when both change",
		},
		{
			name: "display bridge changes",
			files: []string{
				"display/bridge/main.go",
				"display/bridge/handlers.go",
			},
			want:        ChangeCategories{DisplayBridge: true},
			description: "Display bridge code changes should be detected",
		},
		{
			name:        "sketch changes in arduino-app",
			files:       []string{"arduino-app/sketch/trader.ino"},
			want:        ChangeCategories{Sketch: true},
			description: "Arduino sketch changes should be detected",
		},
		{
			name:        "sketch changes in display",
			files:       []string{"display/sketch/display.ino"},
			want:        ChangeCategories{Sketch: true},
			description: "Display sketch changes should be detected",
		},
		{
			name:        "pypfopt service code",
			files:       []string{"microservices/pypfopt/app/main.py"},
			want:        ChangeCategories{PyPFOpt: true},
			description: "PyPFOpt service code changes should be detected",
		},
		{
			name:        "pypfopt dependencies",
			files:       []string{"microservices/pypfopt/requirements.txt"},
			want:        ChangeCategories{PyPFOptDeps: true},
			description: "PyPFOpt dependency changes should be detected",
		},
		{
			name:        "tradernet service code",
			files:       []string{"microservices/tradernet/app/main.py"},
			want:        ChangeCategories{Tradernet: true},
			description: "Tradernet service code changes should be detected",
		},
		{
			name:        "tradernet dependencies",
			files:       []string{"microservices/tradernet/requirements.txt"},
			want:        ChangeCategories{TradernetDeps: true},
			description: "Tradernet dependency changes should be detected",
		},
		{
			name:        "config directory changes",
			files:       []string{"config/settings.toml"},
			want:        ChangeCategories{Config: true},
			description: "Config directory changes should be detected",
		},
		{
			name:        ".env file changes",
			files:       []string{".env"},
			want:        ChangeCategories{Config: true},
			description: ".env file changes should be detected",
		},
		{
			name:        ".env file with path",
			files:       []string{"config/.env.production"},
			want:        ChangeCategories{Config: true},
			description: ".env files in subdirectories should be detected",
		},
		{
			name: "multiple categories",
			files: []string{
				"trader/internal/server/server.go",
				"display/bridge/main.go",
				"config/settings.toml",
				"microservices/pypfopt/app/main.py",
			},
			want: ChangeCategories{
				MainApp:       true,
				DisplayBridge: true,
				Config:        true,
				PyPFOpt:       true,
			},
			description: "Multiple change categories should be detected simultaneously",
		},
		{
			name:        "empty files list",
			files:       []string{},
			want:        ChangeCategories{},
			description: "Empty file list should result in no categories",
		},
		{
			name:        "whitespace-only files ignored",
			files:       []string{"   ", "\t", ""},
			want:        ChangeCategories{},
			description: "Whitespace-only file names should be ignored",
		},
		{
			name:        "path normalization with backslashes",
			files:       []string{"trader\\internal\\server.go"},
			want:        ChangeCategories{}, // Backslashes are not path separators on Unix, so this won't match "trader/"
			description: "Windows-style backslashes are not normalized on Unix systems (filepath.ToSlash only converts actual path separators)",
		},
		{
			name:        "trader prefix but static subdirectory",
			files:       []string{"trader/static/components/widget.js"},
			want:        ChangeCategories{Static: true},
			description: "trader/static should not trigger MainApp, only Static",
		},
		{
			name:        "no matching patterns",
			files:       []string{"README.md", "LICENSE", "docs/guide.md"},
			want:        ChangeCategories{},
			description: "Unmatched files should not trigger any categories",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := checker.CategorizeChanges(tt.files)

			assert.Equal(t, tt.want.MainApp, got.MainApp, "MainApp category mismatch: %s", tt.description)
			assert.Equal(t, tt.want.DisplayBridge, got.DisplayBridge, "DisplayBridge category mismatch: %s", tt.description)
			assert.Equal(t, tt.want.Static, got.Static, "Static category mismatch: %s", tt.description)
			assert.Equal(t, tt.want.Sketch, got.Sketch, "Sketch category mismatch: %s", tt.description)
			assert.Equal(t, tt.want.PyPFOpt, got.PyPFOpt, "PyPFOpt category mismatch: %s", tt.description)
			assert.Equal(t, tt.want.PyPFOptDeps, got.PyPFOptDeps, "PyPFOptDeps category mismatch: %s", tt.description)
			assert.Equal(t, tt.want.Tradernet, got.Tradernet, "Tradernet category mismatch: %s", tt.description)
			assert.Equal(t, tt.want.TradernetDeps, got.TradernetDeps, "TradernetDeps category mismatch: %s", tt.description)
			assert.Equal(t, tt.want.Config, got.Config, "Config category mismatch: %s", tt.description)
		})
	}
}

func TestChangeCategories_HasAnyChanges(t *testing.T) {
	tests := []struct {
		name     string
		category ChangeCategories
		want     bool
	}{
		{
			name:     "all false",
			category: ChangeCategories{},
			want:     false,
		},
		{
			name:     "MainApp true",
			category: ChangeCategories{MainApp: true},
			want:     true,
		},
		{
			name:     "DisplayBridge true",
			category: ChangeCategories{DisplayBridge: true},
			want:     true,
		},
		{
			name:     "Static true",
			category: ChangeCategories{Static: true},
			want:     true,
		},
		{
			name:     "Sketch true",
			category: ChangeCategories{Sketch: true},
			want:     true,
		},
		{
			name:     "PyPFOpt true",
			category: ChangeCategories{PyPFOpt: true},
			want:     true,
		},
		{
			name:     "PyPFOptDeps true",
			category: ChangeCategories{PyPFOptDeps: true},
			want:     true,
		},
		{
			name:     "Tradernet true",
			category: ChangeCategories{Tradernet: true},
			want:     true,
		},
		{
			name:     "TradernetDeps true",
			category: ChangeCategories{TradernetDeps: true},
			want:     true,
		},
		{
			name:     "Config true",
			category: ChangeCategories{Config: true},
			want:     true,
		},
		{
			name: "multiple true",
			category: ChangeCategories{
				MainApp:       true,
				DisplayBridge: true,
				Config:        true,
			},
			want: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := tt.category.HasAnyChanges()
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestGitFetchError(t *testing.T) {
	t.Run("error with wrapped error", func(t *testing.T) {
		originalErr := errors.New("network timeout")
		err := &GitFetchError{
			Message: "failed after 3 attempts",
			Err:     originalErr,
		}

		errMsg := err.Error()
		assert.Contains(t, errMsg, "git fetch error")
		assert.Contains(t, errMsg, "failed after 3 attempts")
		assert.Contains(t, errMsg, "network timeout")

		// Test error unwrapping
		unwrapped := errors.Unwrap(err)
		assert.Equal(t, originalErr, unwrapped)
	})

	t.Run("error without wrapped error", func(t *testing.T) {
		err := &GitFetchError{
			Message: "failed after 3 attempts",
			Err:     nil,
		}

		errMsg := err.Error()
		assert.Contains(t, errMsg, "git fetch error")
		assert.Contains(t, errMsg, "failed after 3 attempts")
		assert.NotContains(t, errMsg, "nil")

		// Test error unwrapping
		unwrapped := errors.Unwrap(err)
		assert.Nil(t, unwrapped)
	})
}

func TestGitPullError(t *testing.T) {
	t.Run("error with wrapped error", func(t *testing.T) {
		originalErr := errors.New("merge conflict")
		err := &GitPullError{
			Message: "failed to pull branch main",
			Err:     originalErr,
		}

		errMsg := err.Error()
		assert.Contains(t, errMsg, "git pull error")
		assert.Contains(t, errMsg, "failed to pull branch main")
		assert.Contains(t, errMsg, "merge conflict")

		// Test error unwrapping
		unwrapped := errors.Unwrap(err)
		assert.Equal(t, originalErr, unwrapped)
	})

	t.Run("error without wrapped error", func(t *testing.T) {
		err := &GitPullError{
			Message: "failed to pull branch main",
			Err:     nil,
		}

		errMsg := err.Error()
		assert.Contains(t, errMsg, "git pull error")
		assert.Contains(t, errMsg, "failed to pull branch main")

		// Test error unwrapping
		unwrapped := errors.Unwrap(err)
		assert.Nil(t, unwrapped)
	})
}

func TestBuildError(t *testing.T) {
	t.Run("error with all fields", func(t *testing.T) {
		originalErr := errors.New("compilation failed")
		err := &BuildError{
			ServiceName: "trader",
			Message:     "build failed",
			Err:         originalErr,
			BuildOutput: "error: undefined variable",
		}

		errMsg := err.Error()
		assert.Contains(t, errMsg, "build error for trader")
		assert.Contains(t, errMsg, "build failed")
		assert.Contains(t, errMsg, "compilation failed")
		assert.Contains(t, errMsg, "Build output:")
		assert.Contains(t, errMsg, "error: undefined variable")

		// Test error unwrapping
		unwrapped := errors.Unwrap(err)
		assert.Equal(t, originalErr, unwrapped)
	})

	t.Run("error without build output", func(t *testing.T) {
		err := &BuildError{
			ServiceName: "trader",
			Message:     "build failed",
			Err:         nil,
			BuildOutput: "",
		}

		errMsg := err.Error()
		assert.Contains(t, errMsg, "build error for trader")
		assert.Contains(t, errMsg, "build failed")
		assert.NotContains(t, errMsg, "Build output:")
	})
}

func TestDeploymentError(t *testing.T) {
	t.Run("error with wrapped error", func(t *testing.T) {
		originalErr := errors.New("permission denied")
		err := &DeploymentError{
			Message: "deployment failed",
			Err:     originalErr,
		}

		errMsg := err.Error()
		assert.Contains(t, errMsg, "deployment error")
		assert.Contains(t, errMsg, "deployment failed")
		assert.Contains(t, errMsg, "permission denied")

		unwrapped := errors.Unwrap(err)
		assert.Equal(t, originalErr, unwrapped)
	})
}

func TestServiceRestartError(t *testing.T) {
	t.Run("error with wrapped error", func(t *testing.T) {
		originalErr := errors.New("service not found")
		err := &ServiceRestartError{
			ServiceName: "trader",
			Message:     "failed to restart",
			Err:         originalErr,
		}

		errMsg := err.Error()
		assert.Contains(t, errMsg, "service restart error for trader")
		assert.Contains(t, errMsg, "failed to restart")
		assert.Contains(t, errMsg, "service not found")

		unwrapped := errors.Unwrap(err)
		assert.Equal(t, originalErr, unwrapped)
	})
}

func TestHealthCheckError(t *testing.T) {
	t.Run("error with wrapped error", func(t *testing.T) {
		originalErr := errors.New("connection refused")
		err := &HealthCheckError{
			ServiceName: "pypfopt",
			Message:     "health check failed",
			Err:         originalErr,
		}

		errMsg := err.Error()
		assert.Contains(t, errMsg, "health check error for pypfopt")
		assert.Contains(t, errMsg, "health check failed")
		assert.Contains(t, errMsg, "connection refused")

		unwrapped := errors.Unwrap(err)
		assert.Equal(t, originalErr, unwrapped)
	})
}

func TestSketchCompilationError(t *testing.T) {
	t.Run("error with wrapped error", func(t *testing.T) {
		originalErr := errors.New("compilation error")
		err := &SketchCompilationError{
			Message: "sketch failed to compile",
			Err:     originalErr,
		}

		errMsg := err.Error()
		assert.Contains(t, errMsg, "sketch compilation error")
		assert.Contains(t, errMsg, "sketch failed to compile")
		assert.Contains(t, errMsg, "compilation error")

		unwrapped := errors.Unwrap(err)
		assert.Equal(t, originalErr, unwrapped)
	})
}

func TestSketchUploadError(t *testing.T) {
	t.Run("error with wrapped error", func(t *testing.T) {
		originalErr := errors.New("device not found")
		err := &SketchUploadError{
			Message: "upload failed",
			Err:     originalErr,
		}

		errMsg := err.Error()
		assert.Contains(t, errMsg, "sketch upload error")
		assert.Contains(t, errMsg, "upload failed")
		assert.Contains(t, errMsg, "device not found")

		unwrapped := errors.Unwrap(err)
		assert.Equal(t, originalErr, unwrapped)
	})
}
