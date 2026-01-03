// Arduino Display Bridge (Go)
// Polls the trader-go API and sends display updates to Arduino MCU via Router Bridge

package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/rpc"
	"os"
	"time"

	msgpackrpc "github.com/hashicorp/net-rpc-msgpackrpc"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

const (
	// API endpoint for display data
	APIURL = "http://localhost:8000/api/status/led/display"

	// Router Bridge connection (arduino-router service)
	// Default port for arduino-router is typically 5555
	RouterAddr = "localhost:5555"

	// Poll interval
	PollInterval = 2 * time.Second
)

// DisplayState represents the API response
type DisplayState struct {
	Mode        string        `json:"mode"`
	DisplayText string        `json:"display_text"`
	TickerSpeed int           `json:"ticker_speed"`
	Stats       *StatsData    `json:"stats"`
	Clusters    []ClusterData `json:"clusters"`
	LED3        [3]int        `json:"led3"`
	LED4        [3]int        `json:"led4"`
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

// Bridge wraps the RPC client for Arduino communication
type Bridge struct {
	client *rpc.Client
	log    zerolog.Logger
}

// NewBridge creates a connection to arduino-router
func NewBridge(addr string) (*Bridge, error) {
	log.Info().Str("addr", addr).Msg("Connecting to arduino-router")

	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to router: %w", err)
	}

	client := rpc.NewClientWithCodec(msgpackrpc.NewClientCodec(conn))

	log.Info().Msg("Connected to arduino-router")

	return &Bridge{
		client: client,
		log:    log.With().Str("component", "bridge").Logger(),
	}, nil
}

// Call invokes an RPC method on the Arduino
func (b *Bridge) Call(method string, args interface{}, reply interface{}) error {
	err := b.client.Call(method, args, reply)
	if err != nil {
		b.log.Debug().
			Err(err).
			Str("method", method).
			Msg("RPC call failed")
	}
	return err
}

// ScrollText sends text to scroll on LED matrix
func (b *Bridge) ScrollText(text string, speed int) error {
	var reply interface{}
	return b.Call("scrollText", []interface{}{text, speed}, &reply)
}

// SetRGB3 sets RGB LED 3 color
func (br *Bridge) SetRGB3(r, g, b int) error {
	var reply interface{}
	return br.Call("setRGB3", []interface{}{r, g, b}, &reply)
}

// SetRGB4 sets RGB LED 4 color
func (br *Bridge) SetRGB4(r, g, b int) error {
	var reply interface{}
	return br.Call("setRGB4", []interface{}{r, g, b}, &reply)
}

// SetSystemStats sets system stats visualization
func (b *Bridge) SetSystemStats(pixelsOn, brightness, intervalMs int) error {
	var reply interface{}
	return b.Call("setSystemStats", []interface{}{pixelsOn, brightness, intervalMs}, &reply)
}

// SetPortfolioMode sets portfolio visualization mode
func (b *Bridge) SetPortfolioMode(clustersJSON string) error {
	var reply interface{}
	return b.Call("setPortfolioMode", []interface{}{clustersJSON}, &reply)
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

	// Update RGB LEDs
	d.bridge.SetRGB3(state.LED3[0], state.LED3[1], state.LED3[2])
	d.bridge.SetRGB4(state.LED4[0], state.LED4[1], state.LED4[2])

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

	// Connect to arduino-router
	bridge, err := NewBridge(RouterAddr)
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to connect to arduino-router")
	}

	// Create display client
	client := NewDisplayClient(APIURL, bridge)

	// Run polling loop
	client.Run()
}
