// Arduino Display Bridge (Go)
// Polls the trader API and sends display updates to Arduino MCU via arduino-router MessagePack RPC

package main

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"net"
	"net/http"
	"os"
	"time"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/vmihailenco/msgpack/v5"
)

const (
	// API endpoint for display data
	APIURL = "http://localhost:8080/api/system/led/display"

	// Router socket path
	RouterSocket = "/var/run/arduino-router.sock"

	// Poll interval
	PollInterval = 2 * time.Second

	// RPC call timeout
	RPCTimeout = 5 * time.Second
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

// Bridge wraps the connection to arduino-router for MessagePack RPC communication
type Bridge struct {
	conn   net.Conn
	log    zerolog.Logger
	msgID  int64
	random *rand.Rand
}

// NewBridge creates a connection to arduino-router via Unix socket
func NewBridge(socketPath string) (*Bridge, error) {
	log.Info().Str("socket", socketPath).Msg("Connecting to arduino-router")

	conn, err := net.DialTimeout("unix", socketPath, 5*time.Second)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to arduino-router: %w", err)
	}

	return &Bridge{
		conn:   conn,
		log:    log.With().Str("component", "bridge").Logger(),
		msgID:  0,
		random: rand.New(rand.NewSource(time.Now().UnixNano())),
	}, nil
}

// Call makes an RPC call to the Arduino sketch using RPClite protocol format
// Request format: [1, msgid, method, params]
// Response format: [2, msgid, error, result]
func (br *Bridge) Call(method string, args interface{}, reply interface{}) error {
	// Generate random message ID to avoid conflicts
	msgID := br.random.Int63n(999999) + 1

	// Convert args to array format
	// args should already be []interface{} as passed from calling code
	params, ok := args.([]interface{})
	if !ok {
		return fmt.Errorf("args must be []interface{}, got %T", args)
	}

	// Build request message: [type, id, method, params]
	// type=1 for request
	request := []interface{}{
		int64(1), // type: 1 = request
		msgID,    // message ID
		method,   // method name
		params,   // parameters array
	}

	// Encode request to MessagePack
	encoder := msgpack.NewEncoder(br.conn)
	if err := encoder.Encode(request); err != nil {
		return fmt.Errorf("failed to encode request: %w", err)
	}

	// Set read timeout
	deadline := time.Now().Add(RPCTimeout)
	if err := br.conn.SetReadDeadline(deadline); err != nil {
		return fmt.Errorf("failed to set read deadline: %w", err)
	}

	// Read response using Unpacker for proper streaming
	unpacker := msgpack.NewDecoder(br.conn)
	var response []interface{}
	if err := unpacker.Decode(&response); err != nil {
		return fmt.Errorf("failed to decode response: %w", err)
	}

	// Validate response format: [type, id, error, result]
	if len(response) != 4 {
		return fmt.Errorf("invalid response format: expected 4 elements, got %d: %v", len(response), response)
	}

	respType, ok := response[0].(int64)
	if !ok {
		return fmt.Errorf("invalid response type: expected int64, got %T", response[0])
	}
	if respType != 2 {
		return fmt.Errorf("invalid response type: expected 2 (response), got %d", respType)
	}

	respID, ok := response[1].(int64)
	if !ok {
		return fmt.Errorf("invalid response ID type: expected int64, got %T", response[1])
	}
	if respID != msgID {
		return fmt.Errorf("response ID mismatch: expected %d, got %d", msgID, respID)
	}

	// Check for error
	if response[2] != nil {
		return fmt.Errorf("RPC error: %v", response[2])
	}

	// Decode result
	if reply != nil && response[3] != nil {
		// Use msgpack to decode the result into the reply type
		data, err := msgpack.Marshal(response[3])
		if err != nil {
			return fmt.Errorf("failed to marshal result: %w", err)
		}
		if err := msgpack.Unmarshal(data, reply); err != nil {
			return fmt.Errorf("failed to unmarshal result: %w", err)
		}
	}

	return nil
}

// ScrollText sends text to scroll on LED matrix
func (br *Bridge) ScrollText(text string, speed int) error {
	var reply interface{}
	// RPClite format: params should be array [text, speed]
	params := []interface{}{text, speed}
	return br.Call("scrollText", params, &reply)
}

// SetRGB3 sets RGB LED 3 color
func (br *Bridge) SetRGB3(r, g, b int) error {
	var reply interface{}
	// RPClite format: params should be array [r, g, b]
	params := []interface{}{r, g, b}
	return br.Call("setRGB3", params, &reply)
}

// SetRGB4 sets RGB LED 4 color
func (br *Bridge) SetRGB4(r, g, b int) error {
	var reply interface{}
	// RPClite format: params should be array [r, g, b]
	params := []interface{}{r, g, b}
	return br.Call("setRGB4", params, &reply)
}

// SetBlink3 sets LED3 to blink mode
func (br *Bridge) SetBlink3(r, g, b, intervalMs int) error {
	type Args struct {
		R          uint8
		G          uint8
		B          uint8
		IntervalMs uint32
	}
	var reply interface{}
	args := Args{R: uint8(r), G: uint8(g), B: uint8(b), IntervalMs: uint32(intervalMs)}
	return br.Call("setBlink3", args, &reply)
}

// SetBlink4 sets LED4 to simple blink mode
func (br *Bridge) SetBlink4(r, g, b, intervalMs int) error {
	type Args struct {
		R          uint8
		G          uint8
		B          uint8
		IntervalMs uint32
	}
	var reply interface{}
	args := Args{R: uint8(r), G: uint8(g), B: uint8(b), IntervalMs: uint32(intervalMs)}
	return br.Call("setBlink4", args, &reply)
}

// SetBlink4Alternating sets LED4 to alternating color mode
func (br *Bridge) SetBlink4Alternating(r1, g1, b1, r2, g2, b2, intervalMs int) error {
	type Args struct {
		R1         uint8
		G1         uint8
		B1         uint8
		R2         uint8
		G2         uint8
		B2         uint8
		IntervalMs uint32
	}
	var reply interface{}
	args := Args{
		R1: uint8(r1), G1: uint8(g1), B1: uint8(b1),
		R2: uint8(r2), G2: uint8(g2), B2: uint8(b2),
		IntervalMs: uint32(intervalMs),
	}
	return br.Call("setBlink4Alternating", args, &reply)
}

// SetBlink4Coordinated sets LED4 to coordinated mode with LED3
func (br *Bridge) SetBlink4Coordinated(r, g, b, intervalMs int, led3Phase bool) error {
	type Args struct {
		R          uint8
		G          uint8
		B          uint8
		IntervalMs uint32
		Led3Phase  bool
	}
	var reply interface{}
	args := Args{R: uint8(r), G: uint8(g), B: uint8(b), IntervalMs: uint32(intervalMs), Led3Phase: led3Phase}
	return br.Call("setBlink4Coordinated", args, &reply)
}

// StopBlink3 stops LED3 blinking
func (br *Bridge) StopBlink3() error {
	var reply interface{}
	return br.Call("stopBlink3", struct{}{}, &reply)
}

// StopBlink4 stops LED4 blinking
func (br *Bridge) StopBlink4() error {
	var reply interface{}
	return br.Call("stopBlink4", struct{}{}, &reply)
}

// SetSystemStats sets system stats visualization
func (br *Bridge) SetSystemStats(pixelsOn, brightness, intervalMs int) error {
	var reply interface{}
	// RPClite format: params should be array [pixelsOn, brightness, intervalMs]
	params := []interface{}{pixelsOn, brightness, intervalMs}
	return br.Call("setSystemStats", params, &reply)
}

// SetPortfolioMode sets portfolio visualization mode
func (br *Bridge) SetPortfolioMode(clustersJSON string) error {
	var reply interface{}
	// RPClite format: params should be array [clustersJSON]
	params := []interface{}{clustersJSON}
	return br.Call("setPortfolioMode", params, &reply)
}

// Close closes the RPC connection
func (br *Bridge) Close() error {
	if br.conn != nil {
		return br.conn.Close()
	}
	return nil
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

	var state DisplayState
	if err := json.NewDecoder(resp.Body).Decode(&state); err != nil {
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

	// Get router socket from environment or use default
	routerSocket := os.Getenv("ROUTER_SOCKET")
	if routerSocket == "" {
		routerSocket = RouterSocket
	}

	// Connect to arduino-router via Unix socket
	bridge, err := NewBridge(routerSocket)
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to connect to arduino-router")
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
