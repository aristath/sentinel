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

// StateManager handles thread-safe display state management
// Faithful translation from Python: app/modules/display/services/display_service.py
type StateManager struct {
	mu          sync.RWMutex
	currentText string
	led3        LEDColor
	led4        LEDColor
	log         zerolog.Logger
}

// NewStateManager creates a new display state manager
func NewStateManager(log zerolog.Logger) *StateManager {
	return &StateManager{
		currentText: "",
		led3:        LEDColor{R: 0, G: 0, B: 0},
		led4:        LEDColor{R: 0, G: 0, B: 0},
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

// SetLED3 sets RGB LED 3 color (sync indicator)
// Faithful translation of Python: def set_led3(self, r: int, g: int, b: int) -> None
func (sm *StateManager) SetLED3(r, g, b int) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.led3 = LEDColor{
		R: clamp(r, 0, 255),
		G: clamp(g, 0, 255),
		B: clamp(b, 0, 255),
	}

	sm.log.Debug().
		Int("r", sm.led3.R).
		Int("g", sm.led3.G).
		Int("b", sm.led3.B).
		Msg("LED3 color updated")
}

// GetLED3 gets RGB LED 3 color
// Faithful translation of Python: def get_led3(self) -> list[int]
func (sm *StateManager) GetLED3() LEDColor {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return sm.led3
}

// SetLED4 sets RGB LED 4 color (processing indicator)
// Faithful translation of Python: def set_led4(self, r: int, g: int, b: int) -> None
func (sm *StateManager) SetLED4(r, g, b int) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.led4 = LEDColor{
		R: clamp(r, 0, 255),
		G: clamp(g, 0, 255),
		B: clamp(b, 0, 255),
	}

	sm.log.Debug().
		Int("r", sm.led4.R).
		Int("g", sm.led4.G).
		Int("b", sm.led4.B).
		Msg("LED4 color updated")
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
