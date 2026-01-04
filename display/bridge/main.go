// Arduino Display Bridge (Go)
// Polls the trader API and sends display updates to Arduino MCU via raw serial communication

package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"go.bug.st/serial"
)

const (
	// API endpoint for display data
	APIURL = "http://localhost:8080/api/system/led/display"

	// Serial port for Arduino MCU communication
	SerialPort = "/dev/ttyHS1"
	SerialBaud = 115200

	// Poll interval
	PollInterval = 2 * time.Second

	// Serial read timeout
	SerialReadTimeout = 500 * time.Millisecond
)

// DisplayState represents the API response
type DisplayState struct {
	Mode        string         `json:"mode"`
	DisplayText string         `json:"display_text"`
	TickerSpeed int            `json:"ticker_speed"`
	Stats       *StatsData     `json:"stats"`
	Clusters    []ClusterData  `json:"clusters"`
	LED3        [3]int         `json:"led3"`
	LED4        [3]int         `json:"led4"`
	LED3Mode    string         `json:"led3_mode,omitempty"`
	LED4Mode    string         `json:"led4_mode,omitempty"`
	LED3Blink   *LED3BlinkInfo `json:"led3_blink,omitempty"`
	LED4Blink   *LED4BlinkInfo `json:"led4_blink,omitempty"`
}

// LED3BlinkInfo contains LED3 blink state information
type LED3BlinkInfo struct {
	Color      [3]int `json:"color"`
	IntervalMs int    `json:"interval_ms"`
	IsOn       bool   `json:"is_on"`
}

// LED4BlinkInfo contains LED4 blink state information
type LED4BlinkInfo struct {
	Mode            string `json:"mode"`
	Color           [3]int `json:"color,omitempty"`
	AltColor1       [3]int `json:"alt_color1,omitempty"`
	AltColor2       [3]int `json:"alt_color2,omitempty"`
	IntervalMs      int    `json:"interval_ms"`
	CoordinatedWith bool   `json:"coordinated_with,omitempty"`
}

// StatsData for system stats mode
type StatsData struct {
	CPUPercent float64 `json:"cpu_percent"`
	RAMPercent float64 `json:"ram_percent"`
	PixelsOn   int     `json:"pixels_on"`
	Brightness int     `json:"brightness"`
}

// ClusterData for portfolio mode
type ClusterData struct {
	ClusterID    int     `json:"cluster_id"`
	Symbol       string  `json:"symbol"`
	Pixels       int     `json:"pixels"`
	Brightness   int     `json:"brightness"`
	Clustering   int     `json:"clustering"`
	Speed        int     `json:"speed"`
	CAGR         float64 `json:"cagr"`
	PortfolioPct float64 `json:"portfolio_pct"`
}

// Bridge wraps the serial connection for Arduino communication
type Bridge struct {
	port   serial.Port
	reader *bufio.Reader
	writer *bufio.Writer
	log    zerolog.Logger
}

// NewBridge creates a connection to the Arduino MCU via serial
func NewBridge(portPath string, baudRate int) (*Bridge, error) {
	log.Info().Str("port", portPath).Int("baud", baudRate).Msg("Opening serial port")

	mode := &serial.Mode{
		BaudRate: baudRate,
		DataBits: 8,
		Parity:   serial.NoParity,
		StopBits: serial.OneStopBit,
	}

	port, err := serial.Open(portPath, mode)
	if err != nil {
		return nil, fmt.Errorf("failed to open serial port: %w", err)
	}

	// Set read timeout
	if err := port.SetReadTimeout(SerialReadTimeout); err != nil {
		port.Close()
		return nil, fmt.Errorf("failed to set read timeout: %w", err)
	}

	reader := bufio.NewReader(port)
	writer := bufio.NewWriter(port)

	// Wait for Arduino to be ready (it sends "READY" on startup)
	log.Info().Msg("Waiting for Arduino to be ready...")
	deadline := time.Now().Add(5 * time.Second)
	arduinoReady := false
	for time.Now().Before(deadline) {
		line, err := reader.ReadString('\n')
		if err != nil {
			if err == io.EOF {
				time.Sleep(100 * time.Millisecond)
				continue
			}
			// If we get a read error but we're close to the deadline, just continue
			// The Arduino might not be sending "READY" but we can still try to communicate
			if time.Until(deadline) < 1*time.Second {
				log.Warn().Err(err).Msg("Read error while waiting for READY, continuing anyway")
				break
			}
			time.Sleep(100 * time.Millisecond)
			continue
		}
		line = strings.TrimSpace(line)
		if line == "READY" {
			log.Info().Msg("Arduino is ready")
			arduinoReady = true
			break
		}
	}
	if !arduinoReady {
		log.Warn().Msg("Arduino did not send READY within timeout, continuing anyway")
	}

	return &Bridge{
		port:   port,
		reader: reader,
		writer: writer,
		log:    log.With().Str("component", "bridge").Logger(),
	}, nil
}

// SendCommand sends a command to the Arduino and waits for response
func (br *Bridge) SendCommand(cmd string) error {
	// Send command
	if _, err := br.writer.WriteString(cmd + "\n"); err != nil {
		return fmt.Errorf("failed to write command: %w", err)
	}
	if err := br.writer.Flush(); err != nil {
		return fmt.Errorf("failed to flush command: %w", err)
	}

	// Read response (with timeout)
	response, err := br.reader.ReadString('\n')
	if err != nil {
		if err == io.EOF {
			// No response, but command might have been sent
			br.log.Debug().Str("cmd", cmd).Msg("No response from Arduino")
			return nil
		}
		return fmt.Errorf("failed to read response: %w", err)
	}

	response = strings.TrimSpace(response)
	if !strings.HasPrefix(response, "OK") {
		return fmt.Errorf("Arduino returned error: %s", response)
	}

	return nil
}

// ScrollText sends text to scroll on LED matrix
func (br *Bridge) ScrollText(text string, speed int) error {
	// Replace colons in text with semicolons to avoid command parsing issues
	escapedText := strings.ReplaceAll(text, ":", ";")
	cmd := fmt.Sprintf("SCROLL:%s:%d", escapedText, speed)
	return br.SendCommand(cmd)
}

// SetRGB3 sets RGB LED 3 color
func (br *Bridge) SetRGB3(r, g, b int) error {
	cmd := fmt.Sprintf("RGB3:%d:%d:%d", r, g, b)
	return br.SendCommand(cmd)
}

// SetRGB4 sets RGB LED 4 color
func (br *Bridge) SetRGB4(r, g, b int) error {
	cmd := fmt.Sprintf("RGB4:%d:%d:%d", r, g, b)
	return br.SendCommand(cmd)
}

// SetBlink3 sets LED3 to blink mode
func (br *Bridge) SetBlink3(r, g, b, intervalMs int) error {
	cmd := fmt.Sprintf("BLINK3:%d:%d:%d:%d", r, g, b, intervalMs)
	return br.SendCommand(cmd)
}

// SetBlink4 sets LED4 to simple blink mode
func (br *Bridge) SetBlink4(r, g, b, intervalMs int) error {
	cmd := fmt.Sprintf("BLINK4:%d:%d:%d:%d", r, g, b, intervalMs)
	return br.SendCommand(cmd)
}

// SetBlink4Alternating sets LED4 to alternating color mode
func (br *Bridge) SetBlink4Alternating(r1, g1, b1, r2, g2, b2, intervalMs int) error {
	cmd := fmt.Sprintf("BLINK4ALT:%d:%d:%d:%d:%d:%d:%d", r1, g1, b1, r2, g2, b2, intervalMs)
	return br.SendCommand(cmd)
}

// SetBlink4Coordinated sets LED4 to coordinated mode with LED3
func (br *Bridge) SetBlink4Coordinated(r, g, b, intervalMs int, led3Phase bool) error {
	phase := 0
	if led3Phase {
		phase = 1
	}
	cmd := fmt.Sprintf("BLINK4COORD:%d:%d:%d:%d:%d", r, g, b, intervalMs, phase)
	return br.SendCommand(cmd)
}

// StopBlink3 stops LED3 blinking
func (br *Bridge) StopBlink3() error {
	return br.SendCommand("STOP3")
}

// StopBlink4 stops LED4 blinking
func (br *Bridge) StopBlink4() error {
	return br.SendCommand("STOP4")
}

// SetSystemStats sets system stats visualization
func (br *Bridge) SetSystemStats(pixelsOn, brightness, intervalMs int) error {
	cmd := fmt.Sprintf("STATS:%d:%d:%d", pixelsOn, brightness, intervalMs)
	return br.SendCommand(cmd)
}

// SetPortfolioMode sets portfolio visualization mode
func (br *Bridge) SetPortfolioMode(clustersJSON string) error {
	// JSON can contain colons (inside quoted strings), but our Arduino parser
	// takes everything after "PORTFOLIO:" as the JSON, so it should work fine
	cmd := fmt.Sprintf("PORTFOLIO:%s", clustersJSON)
	return br.SendCommand(cmd)
}

// Close closes the serial connection
func (br *Bridge) Close() error {
	return br.port.Close()
}

// DisplayClient polls the API and updates the display
type DisplayClient struct {
	apiURL string
	bridge *Bridge
	client *http.Client
	log    zerolog.Logger
}

// NewDisplayClient creates a new display client
func NewDisplayClient(apiURL string, bridge *Bridge) *DisplayClient {
	return &DisplayClient{
		apiURL: apiURL,
		bridge: bridge,
		client: &http.Client{Timeout: 2 * time.Second},
		log:    log.With().Str("component", "display_client").Logger(),
	}
}

// FetchDisplayState gets the current display state from API
func (d *DisplayClient) FetchDisplayState() (*DisplayState, error) {
	resp, err := d.client.Get(d.apiURL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var state DisplayState
	if err := json.Unmarshal(body, &state); err != nil {
		return nil, err
	}

	return &state, nil
}

// HandlePortfolioMode processes portfolio mode
func (d *DisplayClient) HandlePortfolioMode(clusters []ClusterData) error {
	if len(clusters) == 0 {
		d.log.Debug().Msg("Portfolio mode but no clusters data")
		return nil
	}

	// Convert clusters to JSON
	clustersJSON, err := json.Marshal(clusters)
	if err != nil {
		return fmt.Errorf("failed to marshal clusters: %w", err)
	}

	err = d.bridge.SetPortfolioMode(string(clustersJSON))
	if err != nil {
		d.log.Warn().Err(err).Msg("Failed to send portfolio mode")
		return err
	}

	d.log.Debug().Int("num_clusters", len(clusters)).Msg("Sent portfolio mode")
	return nil
}

// HandleStatsMode processes system stats mode
func (d *DisplayClient) HandleStatsMode(stats *StatsData) error {
	if stats == nil {
		d.log.Debug().Msg("Stats mode but no stats data")
		return nil
	}

	// Calculate animation interval: faster when load is high
	// 500ms at 0% load, 5ms at 100% load
	loadPercent := (stats.CPUPercent + stats.RAMPercent) / 2
	intervalMs := int(500 - (loadPercent * 4.95))
	// Clamp to reasonable range
	if intervalMs < 5 {
		intervalMs = 5
	}
	if intervalMs > 500 {
		intervalMs = 500
	}

	err := d.bridge.SetSystemStats(stats.PixelsOn, stats.Brightness, intervalMs)
	if err != nil {
		d.log.Warn().Err(err).Msg("Failed to send stats mode")
		return err
	}

	d.log.Debug().
		Int("pixels", stats.PixelsOn).
		Int("brightness", stats.Brightness).
		Int("interval_ms", intervalMs).
		Msg("Sent stats mode")
	return nil
}

// HandleTickerMode processes ticker mode
func (d *DisplayClient) HandleTickerMode(text string, speed int) error {
	if text == "" {
		d.log.Debug().Msg("Ticker mode but no display text")
		return nil
	}

	err := d.bridge.ScrollText(text, speed)
	if err != nil {
		d.log.Warn().Err(err).Str("text", text).Msg("Failed to send ticker")
		return err
	}

	d.log.Debug().Str("text", text).Int("speed", speed).Msg("Sent ticker")
	return nil
}

// UpdateDisplay fetches state and updates display
func (d *DisplayClient) UpdateDisplay() error {
	state, err := d.FetchDisplayState()
	if err != nil {
		return err
	}

	// Update LED3 based on mode
	if state.LED3Mode == "blink" && state.LED3Blink != nil {
		d.bridge.SetBlink3(
			state.LED3Blink.Color[0],
			state.LED3Blink.Color[1],
			state.LED3Blink.Color[2],
			state.LED3Blink.IntervalMs,
		)
	} else {
		// Solid color or unknown mode
		d.bridge.SetRGB3(state.LED3[0], state.LED3[1], state.LED3[2])
	}

	// Update LED4 based on mode
	if state.LED4Mode == "blink" && state.LED4Blink != nil {
		d.bridge.SetBlink4(
			state.LED4Blink.Color[0],
			state.LED4Blink.Color[1],
			state.LED4Blink.Color[2],
			state.LED4Blink.IntervalMs,
		)
	} else if state.LED4Mode == "alternating" && state.LED4Blink != nil {
		d.bridge.SetBlink4Alternating(
			state.LED4Blink.AltColor1[0],
			state.LED4Blink.AltColor1[1],
			state.LED4Blink.AltColor1[2],
			state.LED4Blink.AltColor2[0],
			state.LED4Blink.AltColor2[1],
			state.LED4Blink.AltColor2[2],
			state.LED4Blink.IntervalMs,
		)
	} else if state.LED4Mode == "coordinated" && state.LED4Blink != nil {
		// Get LED3 current state for coordination
		led3Phase := false
		if state.LED3Blink != nil {
			led3Phase = state.LED3Blink.IsOn
		}
		d.bridge.SetBlink4Coordinated(
			state.LED4Blink.Color[0],
			state.LED4Blink.Color[1],
			state.LED4Blink.Color[2],
			state.LED4Blink.IntervalMs,
			led3Phase,
		)
	} else {
		// Solid color or unknown mode
		d.bridge.SetRGB4(state.LED4[0], state.LED4[1], state.LED4[2])
	}

	// Handle display mode
	switch state.Mode {
	case "PORTFOLIO":
		return d.HandlePortfolioMode(state.Clusters)
	case "STATS":
		return d.HandleStatsMode(state.Stats)
	case "TICKER":
		return d.HandleTickerMode(state.DisplayText, state.TickerSpeed)
	default:
		d.log.Warn().Str("mode", state.Mode).Msg("Unknown display mode")
	}

	return nil
}

// Run starts the polling loop
func (d *DisplayClient) Run() {
	d.log.Info().
		Str("api_url", d.apiURL).
		Dur("poll_interval", PollInterval).
		Msg("Starting display client")

	ticker := time.NewTicker(PollInterval)
	defer ticker.Stop()

	for {
		if err := d.UpdateDisplay(); err != nil {
			d.log.Debug().Err(err).Msg("Failed to update display")
		}
		<-ticker.C
	}
}

func main() {
	// Configure logging
	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix
	log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr})

	log.Info().Msg("Arduino Display Bridge (Go) starting...")

	// Get serial port from environment or use default
	serialPort := os.Getenv("SERIAL_PORT")
	if serialPort == "" {
		serialPort = SerialPort
	}

	// Connect to Arduino MCU via serial
	bridge, err := NewBridge(serialPort, SerialBaud)
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to connect to Arduino MCU")
	}
	defer bridge.Close()

	// Get API URL from environment or use default
	apiURL := os.Getenv("API_URL")
	if apiURL == "" {
		apiURL = APIURL
	}

	// Create display client
	client := NewDisplayClient(apiURL, bridge)

	// Run polling loop
	client.Run()
}
