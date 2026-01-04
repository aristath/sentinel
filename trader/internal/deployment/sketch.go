package deployment

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// SketchDeployer handles Arduino sketch compilation and upload
type SketchDeployer struct {
	log Logger
}

// NewSketchDeployer creates a new sketch deployer
func NewSketchDeployer(log Logger) *SketchDeployer {
	return &SketchDeployer{
		log: log,
	}
}

// DeploySketch compiles and uploads an Arduino sketch
func (d *SketchDeployer) DeploySketch(sketchPath string, repoDir string) error {
	fullSketchPath := filepath.Join(repoDir, sketchPath)

	// Check if sketch exists
	if _, err := os.Stat(fullSketchPath); os.IsNotExist(err) {
		return fmt.Errorf("sketch file does not exist: %s", fullSketchPath)
	}

	sketchDir := filepath.Dir(fullSketchPath)
	fqbn := "arduino:zephyr:unoq" // Arduino Uno Q FQBN

	d.log.Info().
		Str("sketch", sketchPath).
		Str("fqbn", fqbn).
		Msg("Compiling and uploading Arduino sketch")

	// Install arduino-cli if not present
	if err := d.ensureArduinoCLI(); err != nil {
		d.log.Warn().
			Err(err).
			Msg("Arduino CLI may not be installed, compilation may fail")
	}

	// Update core index
	if err := d.updateCoreIndex(); err != nil {
		d.log.Warn().
			Err(err).
			Msg("Failed to update core index")
	}

	// Install board platform
	if err := d.installPlatform(fqbn); err != nil {
		return &SketchCompilationError{
			Message: "failed to install board platform",
			Err:     err,
		}
	}

	// Install required libraries
	if err := d.installLibraries(); err != nil {
		d.log.Warn().
			Err(err).
			Msg("Some libraries may not be installed")
	}

	// Compile sketch
	if err := d.compileSketch(sketchDir, fqbn); err != nil {
		return &SketchCompilationError{
			Message: "sketch compilation failed",
			Err:     err,
		}
	}

	// Detect serial port
	serialPort := d.detectSerialPort()
	if serialPort == "" {
		d.log.Warn().
			Msg("Serial port not detected, skipping upload (compilation succeeded)")
		return nil
	}

	// Upload sketch
	if err := d.uploadSketch(sketchDir, fqbn, serialPort); err != nil {
		return &SketchUploadError{
			Message: "sketch upload failed",
			Err:     err,
		}
	}

	d.log.Info().
		Str("sketch", sketchPath).
		Str("port", serialPort).
		Msg("Successfully deployed Arduino sketch")

	return nil
}

// ensureArduinoCLI checks if arduino-cli is installed
func (d *SketchDeployer) ensureArduinoCLI() error {
	_, err := exec.LookPath("arduino-cli")
	if err == nil {
		return nil // Already installed
	}

	d.log.Info().Msg("Arduino CLI not found, attempting installation...")

	// Try to install arduino-cli
	cmd := exec.Command("sh", "-c", "curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh")
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to install arduino-cli: %w", err)
	}

	// Check if installed to ~/bin
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("failed to get home directory: %w", err)
	}

	cliPath := filepath.Join(homeDir, "bin", "arduino-cli")
	if _, err := os.Stat(cliPath); err == nil {
		// Add to PATH for this session
		os.Setenv("PATH", fmt.Sprintf("%s:%s", filepath.Join(homeDir, "bin"), os.Getenv("PATH")))
	}

	return nil
}

// updateCoreIndex updates the Arduino core index
func (d *SketchDeployer) updateCoreIndex() error {
	cmd := exec.Command("arduino-cli", "core", "update-index")
	cmd.Stdout = nil
	cmd.Stderr = nil
	return cmd.Run()
}

// installPlatform installs a board platform
func (d *SketchDeployer) installPlatform(fqbn string) error {
	parts := strings.Split(fqbn, ":")
	if len(parts) < 3 {
		return fmt.Errorf("invalid FQBN: %s", fqbn)
	}

	platform := fmt.Sprintf("%s:%s", parts[0], parts[1])
	d.log.Debug().
		Str("platform", platform).
		Msg("Installing board platform")

	cmd := exec.Command("arduino-cli", "core", "install", platform)
	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		output := stdout.String() + stderr.String()
		return fmt.Errorf("failed to install platform %s: %w\nOutput: %s", platform, err, output)
	}

	return nil
}

// installLibraries installs required libraries
func (d *SketchDeployer) installLibraries() error {
	libraries := []string{
		"ArduinoGraphics",
		"MsgPack@0.4.2",
		"DebugLog@0.8.4",
		"ArxContainer@0.7.0",
		"ArxTypeTraits@0.3.1",
	}

	for _, lib := range libraries {
		d.log.Debug().
			Str("library", lib).
			Msg("Installing library")

		cmd := exec.Command("arduino-cli", "lib", "install", lib)
		cmd.Stdout = nil
		cmd.Stderr = nil

		if err := cmd.Run(); err != nil {
			d.log.Warn().
				Err(err).
				Str("library", lib).
				Msg("Failed to install library")
		}
	}

	return nil
}

// compileSketch compiles an Arduino sketch
func (d *SketchDeployer) compileSketch(sketchDir string, fqbn string) error {
	d.log.Info().
		Str("sketch_dir", sketchDir).
		Str("fqbn", fqbn).
		Msg("Compiling sketch")

	cmd := exec.Command("arduino-cli", "compile", "--fqbn", fqbn, sketchDir)
	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		output := stdout.String() + stderr.String()
		return fmt.Errorf("compilation failed: %w\nOutput: %s", err, output)
	}

	d.log.Info().
		Str("sketch_dir", sketchDir).
		Msg("Compilation successful")

	return nil
}

// detectSerialPort detects the serial port for Arduino Uno Q
func (d *SketchDeployer) detectSerialPort() string {
	// Try ttyHS1 first (Arduino Uno Q internal), then ttyACM0
	ports := []string{"/dev/ttyHS1", "/dev/ttyACM0"}

	for _, port := range ports {
		if _, err := os.Stat(port); err == nil {
			d.log.Debug().
				Str("port", port).
				Msg("Serial port detected")
			return port
		}
	}

	return ""
}

// uploadSketch uploads a compiled sketch to the MCU
func (d *SketchDeployer) uploadSketch(sketchDir string, fqbn string, serialPort string) error {
	d.log.Info().
		Str("sketch_dir", sketchDir).
		Str("fqbn", fqbn).
		Str("port", serialPort).
		Msg("Uploading sketch to MCU")

	cmd := exec.Command("arduino-cli", "upload", "--fqbn", fqbn, "--port", serialPort, sketchDir)
	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		output := stdout.String() + stderr.String()
		return fmt.Errorf("upload failed: %w\nOutput: %s", err, output)
	}

	d.log.Info().
		Str("sketch_dir", sketchDir).
		Str("port", serialPort).
		Msg("Upload successful")

	return nil
}
