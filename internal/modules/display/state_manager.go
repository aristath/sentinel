package display

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/rs/zerolog"
)

// Default display URL (App Lab Web UI Brick - default port 7000)
const DefaultDisplayURL = "http://localhost:7000"

// LEDColor represents RGB color values (0-255)
type LEDColor struct {
	R int `json:"r"`
	G int `json:"g"`
	B int `json:"b"`
}

// DisplayState represents the current display state
type DisplayState struct {
	CurrentText string   `json:"current_text"`
	LED3        LEDColor `json:"led3"`
	LED4        LEDColor `json:"led4"`
}

// LEDMode represents the mode of an LED
type LEDMode int

const (
	LEDModeSolid LEDMode = iota
	LEDModeBlink
	LEDModeAlternating
	LEDModeCoordinated
)

// LED3BlinkState tracks LED3 blink state for coordination
type LED3BlinkState struct {
	IsBlinking bool
	Color      LEDColor
	IntervalMs int
	IsOn       bool // Current ON/OFF state
}

// LED4State tracks LED4 state including blink modes
type LED4State struct {
	Mode            LEDMode
	Color           LEDColor
	AltColor1       LEDColor
	AltColor2       LEDColor
	IntervalMs      int
	CoordinatedWith bool // LED3 state when coordinated
}

// StateManager handles thread-safe display state management
// Communicates with Arduino App Lab via HTTP REST API
type StateManager struct {
	log         zerolog.Logger
	currentText string
	led3        LEDColor
	led4        LEDColor
	led3Blink   LED3BlinkState
	led4State   LED4State
	mu          sync.RWMutex

	// HTTP client for App Lab REST API
	httpClient *http.Client
	displayURL string
	enabled    bool // Whether display communication is enabled
}

// NewStateManager creates a new display state manager
func NewStateManager(log zerolog.Logger) *StateManager {
	return &StateManager{
		currentText: "",
		led3:        LEDColor{R: 0, G: 0, B: 0},
		led4:        LEDColor{R: 0, G: 0, B: 0},
		led3Blink:   LED3BlinkState{IsBlinking: false},
		led4State:   LED4State{Mode: LEDModeSolid},
		log:         log.With().Str("component", "display_state_manager").Logger(),
		httpClient: &http.Client{
			Timeout: 5 * time.Second,
		},
		displayURL: DefaultDisplayURL,
		enabled:    false, // Disabled by default until explicitly enabled
	}
}

// SetDisplayURL sets the URL for the App Lab display service
func (sm *StateManager) SetDisplayURL(url string) {
	sm.mu.Lock()
	defer sm.mu.Unlock()
	sm.displayURL = url
	sm.log.Info().Str("url", url).Msg("Display URL configured")
}

// Enable enables display communication
func (sm *StateManager) Enable() {
	sm.mu.Lock()
	defer sm.mu.Unlock()
	sm.enabled = true
	sm.log.Info().Msg("Display communication enabled")
}

// Disable disables display communication
func (sm *StateManager) Disable() {
	sm.mu.Lock()
	defer sm.mu.Unlock()
	sm.enabled = false
	sm.log.Info().Msg("Display communication disabled")
}

// IsEnabled returns whether display communication is enabled
func (sm *StateManager) IsEnabled() bool {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return sm.enabled
}

// postJSON sends a JSON POST request to the display service
func (sm *StateManager) postJSON(endpoint string, data interface{}) error {
	if !sm.enabled {
		return nil // Silently skip if disabled
	}

	url := fmt.Sprintf("%s%s", sm.displayURL, endpoint)

	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal JSON: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := sm.httpClient.Do(req)
	if err != nil {
		sm.log.Debug().Err(err).Str("url", url).Msg("Display request failed (display may be offline)")
		return fmt.Errorf("display request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("display returned error status: %d", resp.StatusCode)
	}

	return nil
}

// SetText sets display text (latest message wins)
func (sm *StateManager) SetText(text string) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	oldText := sm.currentText
	sm.currentText = text

	if oldText != text {
		sm.log.Debug().
			Str("old_text", oldText).
			Str("new_text", text).
			Msg("Display text updated")

		// Push to display via HTTP
		go func() {
			if err := sm.postJSON("/text", map[string]interface{}{
				"text":  text,
				"speed": 50, // Default scroll speed
			}); err != nil {
				sm.log.Debug().Err(err).Msg("Failed to push text to display")
			}
		}()
	}
}

// GetCurrentText gets current display text
func (sm *StateManager) GetCurrentText() string {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return sm.currentText
}

// SetLED3 sets RGB LED 3 color (sync indicator) - stops blinking
func (sm *StateManager) SetLED3(r, g, b int) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.led3 = LEDColor{
		R: clamp(r, 0, 255),
		G: clamp(g, 0, 255),
		B: clamp(b, 0, 255),
	}
	sm.led3Blink.IsBlinking = false

	sm.log.Debug().
		Int("r", sm.led3.R).
		Int("g", sm.led3.G).
		Int("b", sm.led3.B).
		Msg("LED3 color updated (solid)")

	// Push to display via HTTP
	led3 := sm.led3
	go func() {
		if err := sm.postJSON("/led3", map[string]int{
			"r": led3.R,
			"g": led3.G,
			"b": led3.B,
		}); err != nil {
			sm.log.Debug().Err(err).Msg("Failed to push LED3 to display")
		}
	}()
}

// SetLED3Color is an alias for SetLED3
func (sm *StateManager) SetLED3Color(r, g, b int) {
	sm.SetLED3(r, g, b)
}

// SetLED3Blink enables blink mode for LED3
// Note: Blink is handled client-side since App Lab doesn't support hardware blink
func (sm *StateManager) SetLED3Blink(r, g, b int, intervalMs int) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	color := LEDColor{
		R: clamp(r, 0, 255),
		G: clamp(g, 0, 255),
		B: clamp(b, 0, 255),
	}
	sm.led3 = color
	sm.led3Blink = LED3BlinkState{
		IsBlinking: true,
		Color:      color,
		IntervalMs: intervalMs,
		IsOn:       true, // Start ON
	}

	sm.log.Debug().
		Int("r", sm.led3.R).
		Int("g", sm.led3.G).
		Int("b", sm.led3.B).
		Int("interval_ms", intervalMs).
		Msg("LED3 blink mode enabled")

	// For simplicity, just set the color (blink would need client-side timing)
	go func() {
		if err := sm.postJSON("/led3", map[string]int{
			"r": color.R,
			"g": color.G,
			"b": color.B,
		}); err != nil {
			sm.log.Debug().Err(err).Msg("Failed to push LED3 blink to display")
		}
	}()
}

// UpdateLED3BlinkState updates LED3 blink state (called periodically to track ON/OFF)
func (sm *StateManager) UpdateLED3BlinkState(isOn bool) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	if sm.led3Blink.IsBlinking {
		sm.led3Blink.IsOn = isOn
	}
}

// GetLED3BlinkState returns LED3 current blink state for coordination
func (sm *StateManager) GetLED3BlinkState() bool {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	if !sm.led3Blink.IsBlinking {
		return false // Not blinking, consider as OFF
	}
	return sm.led3Blink.IsOn
}

// GetLED3 gets RGB LED 3 color
func (sm *StateManager) GetLED3() LEDColor {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return sm.led3
}

// SetLED4 sets RGB LED 4 color (processing indicator) - stops blinking
func (sm *StateManager) SetLED4(r, g, b int) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.led4 = LEDColor{
		R: clamp(r, 0, 255),
		G: clamp(g, 0, 255),
		B: clamp(b, 0, 255),
	}
	sm.led4State.Mode = LEDModeSolid

	sm.log.Debug().
		Int("r", sm.led4.R).
		Int("g", sm.led4.G).
		Int("b", sm.led4.B).
		Msg("LED4 color updated (solid)")

	// Push to display via HTTP
	led4 := sm.led4
	go func() {
		if err := sm.postJSON("/led4", map[string]int{
			"r": led4.R,
			"g": led4.G,
			"b": led4.B,
		}); err != nil {
			sm.log.Debug().Err(err).Msg("Failed to push LED4 to display")
		}
	}()
}

// SetLED4Color is an alias for SetLED4
func (sm *StateManager) SetLED4Color(r, g, b int) {
	sm.SetLED4(r, g, b)
}

// SetLED4Blink enables simple blink mode for LED4
// Note: Blink is handled client-side since App Lab doesn't support hardware blink
func (sm *StateManager) SetLED4Blink(r, g, b int, intervalMs int) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.led4 = LEDColor{
		R: clamp(r, 0, 255),
		G: clamp(g, 0, 255),
		B: clamp(b, 0, 255),
	}
	sm.led4State = LED4State{
		Mode:       LEDModeBlink,
		Color:      sm.led4,
		IntervalMs: intervalMs,
	}

	sm.log.Debug().
		Int("r", sm.led4.R).
		Int("g", sm.led4.G).
		Int("b", sm.led4.B).
		Int("interval_ms", intervalMs).
		Msg("LED4 blink mode enabled")

	// For simplicity, just set the color
	led4 := sm.led4
	go func() {
		if err := sm.postJSON("/led4", map[string]int{
			"r": led4.R,
			"g": led4.G,
			"b": led4.B,
		}); err != nil {
			sm.log.Debug().Err(err).Msg("Failed to push LED4 blink to display")
		}
	}()
}

// SetLED4Alternating enables alternating color mode for LED4
func (sm *StateManager) SetLED4Alternating(r1, g1, b1, r2, g2, b2 int, intervalMs int) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	color1 := LEDColor{R: clamp(r1, 0, 255), G: clamp(g1, 0, 255), B: clamp(b1, 0, 255)}
	color2 := LEDColor{R: clamp(r2, 0, 255), G: clamp(g2, 0, 255), B: clamp(b2, 0, 255)}

	sm.led4State = LED4State{
		Mode:       LEDModeAlternating,
		AltColor1:  color1,
		AltColor2:  color2,
		IntervalMs: intervalMs,
	}

	sm.log.Debug().
		Int("r1", r1).Int("g1", g1).Int("b1", b1).
		Int("r2", r2).Int("g2", g2).Int("b2", b2).
		Int("interval_ms", intervalMs).
		Msg("LED4 alternating mode enabled")

	// Set first color
	go func() {
		if err := sm.postJSON("/led4", map[string]int{
			"r": color1.R,
			"g": color1.G,
			"b": color1.B,
		}); err != nil {
			sm.log.Debug().Err(err).Msg("Failed to push LED4 alternating to display")
		}
	}()
}

// SetLED4Coordinated enables coordinated mode for LED4 (alternates with LED3)
func (sm *StateManager) SetLED4Coordinated(r, g, b int, intervalMs int, led3Phase bool) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.led4 = LEDColor{
		R: clamp(r, 0, 255),
		G: clamp(g, 0, 255),
		B: clamp(b, 0, 255),
	}
	sm.led4State = LED4State{
		Mode:            LEDModeCoordinated,
		Color:           sm.led4,
		IntervalMs:      intervalMs,
		CoordinatedWith: !led3Phase, // LED4 ON when LED3 OFF
	}

	sm.log.Debug().
		Int("r", sm.led4.R).
		Int("g", sm.led4.G).
		Int("b", sm.led4.B).
		Int("interval_ms", intervalMs).
		Bool("led3_phase", led3Phase).
		Msg("LED4 coordinated mode enabled")

	// Set color based on current phase
	led4 := sm.led4
	go func() {
		color := map[string]int{"r": 0, "g": 0, "b": 0}
		if !led3Phase { // LED4 ON when LED3 OFF
			color = map[string]int{
				"r": led4.R,
				"g": led4.G,
				"b": led4.B,
			}
		}
		if err := sm.postJSON("/led4", color); err != nil {
			sm.log.Debug().Err(err).Msg("Failed to push LED4 coordinated to display")
		}
	}()
}

// GetLED4 gets RGB LED 4 color
func (sm *StateManager) GetLED4() LEDColor {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return sm.led4
}

// GetState gets the complete display state (thread-safe snapshot)
func (sm *StateManager) GetState() DisplayState {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	return DisplayState{
		CurrentText: sm.currentText,
		LED3:        sm.led3,
		LED4:        sm.led4,
	}
}

// GetLED3BlinkStateInfo returns LED3 blink state info for display bridge
func (sm *StateManager) GetLED3BlinkStateInfo() (isBlinking bool, color LEDColor, intervalMs int, isOn bool) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	return sm.led3Blink.IsBlinking, sm.led3Blink.Color, sm.led3Blink.IntervalMs, sm.led3Blink.IsOn
}

// GetLED4StateInfo returns LED4 state info for display bridge
func (sm *StateManager) GetLED4StateInfo() (mode LEDMode, color LEDColor, altColor1 LEDColor, altColor2 LEDColor, intervalMs int, coordinatedWith bool) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	return sm.led4State.Mode, sm.led4State.Color, sm.led4State.AltColor1, sm.led4State.AltColor2, sm.led4State.IntervalMs, sm.led4State.CoordinatedWith
}

// ClearMatrix clears the LED matrix
func (sm *StateManager) ClearMatrix() {
	go func() {
		if err := sm.postJSON("/clear", map[string]string{}); err != nil {
			sm.log.Debug().Err(err).Msg("Failed to clear matrix on display")
		}
	}()
}

// SetPixelCount sets the number of lit pixels (for system stats mode)
func (sm *StateManager) SetPixelCount(count int) {
	go func() {
		if err := sm.postJSON("/pixels", map[string]int{
			"count": clamp(count, 0, 104),
		}); err != nil {
			sm.log.Debug().Err(err).Msg("Failed to set pixel count on display")
		}
	}()
}

// CheckHealth checks if the display service is healthy
func (sm *StateManager) CheckHealth() bool {
	if !sm.enabled {
		return false
	}

	url := fmt.Sprintf("%s/health", sm.displayURL)
	resp, err := sm.httpClient.Get(url)
	if err != nil {
		return false
	}
	defer resp.Body.Close()

	return resp.StatusCode == http.StatusOK
}

// clamp restricts a value to be within a given range
func clamp(value, minVal, maxVal int) int {
	if value < minVal {
		return minVal
	}
	if value > maxVal {
		return maxVal
	}
	return value
}
