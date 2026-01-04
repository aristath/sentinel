package display

import (
	"sync"

	"github.com/rs/zerolog"
)

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
// Faithful translation from Python: app/modules/display/services/display_service.py
type StateManager struct {
	log         zerolog.Logger
	currentText string
	led3        LEDColor
	led4        LEDColor
	led3Blink   LED3BlinkState
	led4State   LED4State
	mu          sync.RWMutex
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
	}
}

// SetText sets display text (latest message wins)
// Faithful translation of Python: def set_text(self, text: str) -> None
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
	}
}

// GetCurrentText gets current display text
// Faithful translation of Python: def get_current_text(self) -> str
func (sm *StateManager) GetCurrentText() string {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return sm.currentText
}

// SetLED3 sets RGB LED 3 color (sync indicator) - stops blinking
// Faithful translation of Python: def set_led3(self, r: int, g: int, b: int) -> None
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
}

// SetLED3Color is an alias for SetLED3
func (sm *StateManager) SetLED3Color(r, g, b int) {
	sm.SetLED3(r, g, b)
}

// SetLED3Blink enables blink mode for LED3
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
// Faithful translation of Python: def get_led3(self) -> list[int]
func (sm *StateManager) GetLED3() LEDColor {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return sm.led3
}

// SetLED4 sets RGB LED 4 color (processing indicator) - stops blinking
// Faithful translation of Python: def set_led4(self, r: int, g: int, b: int) -> None
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
}

// SetLED4Color is an alias for SetLED4
func (sm *StateManager) SetLED4Color(r, g, b int) {
	sm.SetLED4(r, g, b)
}

// SetLED4Blink enables simple blink mode for LED4
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
}

// SetLED4Alternating enables alternating color mode for LED4
func (sm *StateManager) SetLED4Alternating(r1, g1, b1, r2, g2, b2 int, intervalMs int) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.led4State = LED4State{
		Mode:       LEDModeAlternating,
		AltColor1:  LEDColor{R: clamp(r1, 0, 255), G: clamp(g1, 0, 255), B: clamp(b1, 0, 255)},
		AltColor2:  LEDColor{R: clamp(r2, 0, 255), G: clamp(g2, 0, 255), B: clamp(b2, 0, 255)},
		IntervalMs: intervalMs,
	}

	sm.log.Debug().
		Int("r1", r1).Int("g1", g1).Int("b1", b1).
		Int("r2", r2).Int("g2", g2).Int("b2", b2).
		Int("interval_ms", intervalMs).
		Msg("LED4 alternating mode enabled")
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
}

// GetLED4 gets RGB LED 4 color
// Faithful translation of Python: def get_led4(self) -> list[int]
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

// GetLED3BlinkState returns LED3 blink state info for display bridge
func (sm *StateManager) GetLED3BlinkStateInfo() (isBlinking bool, color LEDColor, intervalMs int, isOn bool) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	return sm.led3Blink.IsBlinking, sm.led3Blink.Color, sm.led3Blink.IntervalMs, sm.led3Blink.IsOn
}

// GetLED4State returns LED4 state info for display bridge
func (sm *StateManager) GetLED4StateInfo() (mode LEDMode, color LEDColor, altColor1 LEDColor, altColor2 LEDColor, intervalMs int, coordinatedWith bool) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	return sm.led4State.Mode, sm.led4State.Color, sm.led4State.AltColor1, sm.led4State.AltColor2, sm.led4State.IntervalMs, sm.led4State.CoordinatedWith
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
