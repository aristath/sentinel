// Package embedded provides embedded static assets for the application.
package embedded

import (
	"embed"
)

// Files contains all files embedded in the Go binary:
// - Frontend files (frontend/dist) - served directly via HTTP
// - Display App Lab files (display/) - Arduino App Lab application
//   - app.yaml - App Lab configuration
//   - python/main.py - Python app with Web UI Brick REST API
//   - sketch/ - Arduino sketch files
//
// Note: Files are copied into pkg/embedded/ during GitHub Actions build
// The display app uses Arduino App Lab's Web UI Brick for HTTP API communication
//
//go:embed frontend/dist display
var Files embed.FS
