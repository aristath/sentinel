/**
 * orbital_display.ino - Orbital portfolio visualization for Arduino UNO Q
 *
 * Displays portfolio as orbital system on 8x13 LED matrix:
 * - Sun (center 2x2): Top 4 holdings
 * - Satellites: Remaining holdings orbiting the sun
 * - Animation patterns indicate position health
 *
 * Python sends state updates (~1/min), MCU handles all animation at 60fps.
 */

#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <vector>
#include <math.h>

ArduinoLEDMatrix matrix;

// Matrix dimensions
const uint8_t WIDTH = 13;
const uint8_t HEIGHT = 8;

// Sun center position
const float SUN_X = 6.0f;
const float SUN_Y = 3.5f;

// Orbital radii
const float INNER_RADIUS = 2.5f;
const float OUTER_RADIUS = 3.5f;

// Animation patterns
enum Pattern : uint8_t {
    BREATHE = 0,    // Stable
    FADE_IN = 1,    // Growing
    FADE_OUT = 2,   // Shrinking
    PULSE = 3,      // Concern
    BLINK = 4       // Warning
};

// Body state
struct Body {
    uint8_t id;
    Pattern pattern;
    uint8_t orbit;      // 0=core, 1=inner, 2=outer
    bool active;
    float angle;        // Orbital angle (radians)
    float entry;        // Entry animation progress 0-1
};

// Global state
Body bodies[20];
uint8_t body_count = 0;
uint8_t global_brightness = 200;
uint8_t frame_buffer[104];

// Timing
uint32_t last_frame = 0;
const uint32_t FRAME_INTERVAL = 16;  // ~60fps

/**
 * Get brightness for a pattern at given time.
 */
uint8_t get_pattern_brightness(Pattern p, uint32_t t_ms) {
    float phase;
    float val;

    switch (p) {
        case BREATHE:
            // Sine wave, 2.5s cycle
            phase = fmod(t_ms, 2500) / 2500.0f;
            val = (sin(phase * 2.0f * M_PI) + 1.0f) * 0.5f;
            return (uint8_t)(30 + val * 225);

        case FADE_IN:
            // Ramp up then quick drop, 1.5s cycle
            phase = fmod(t_ms, 1500) / 1500.0f;
            if (phase < 0.8f) {
                val = phase / 0.8f;
            } else {
                val = 1.0f - ((phase - 0.8f) / 0.2f);
            }
            return (uint8_t)(30 + val * 225);

        case FADE_OUT:
            // Ramp down then quick rise, 1.5s cycle
            phase = fmod(t_ms, 1500) / 1500.0f;
            if (phase < 0.8f) {
                val = 1.0f - (phase / 0.8f);
            } else {
                val = (phase - 0.8f) / 0.2f;
            }
            return (uint8_t)(30 + val * 225);

        case PULSE:
            // Soft bump, 1s cycle
            phase = fmod(t_ms, 1000) / 1000.0f;
            if (phase < 0.3f) {
                val = 0.5f + 0.5f * (1.0f - cos(phase / 0.3f * M_PI));
            } else {
                val = 0.5f;
            }
            return (uint8_t)(30 + val * 225);

        case BLINK:
            // Hard on/off, 500ms cycle
            return (fmod(t_ms, 500) < 250) ? 255 : 40;

        default:
            return 128;
    }
}

/**
 * Get orbital position for a body.
 */
void get_position(const Body& b, float& x, float& y) {
    if (b.orbit == 0) {
        // Core body - 2x2 sun grid
        x = SUN_X + (float)(b.id % 2) - 0.5f;
        y = SUN_Y + (float)(b.id / 2) - 0.5f;
    } else {
        // Satellite - orbital position
        float radius = (b.orbit == 1) ? INNER_RADIUS : OUTER_RADIUS;
        radius *= b.entry;  // Entry animation scaling
        x = SUN_X + cos(b.angle) * radius;
        y = SUN_Y + sin(b.angle) * radius;
    }
}

/**
 * Set pixel in frame buffer with bounds checking.
 */
void set_pixel(uint8_t x, uint8_t y, uint8_t brightness) {
    if (x >= WIDTH || y >= HEIGHT) return;
    uint16_t idx = y * WIDTH + x;
    // Additive blending with clamping
    uint16_t sum = frame_buffer[idx] + brightness;
    frame_buffer[idx] = (sum > 255) ? 255 : (uint8_t)sum;
}

/**
 * Update orbital physics.
 */
void update_physics(float dt_ms) {
    for (int i = 0; i < body_count; i++) {
        Body& b = bodies[i];
        if (!b.active) continue;

        // Update entry animation
        if (b.entry < 1.0f) {
            b.entry += 0.002f * dt_ms;
            if (b.entry > 1.0f) b.entry = 1.0f;
        }

        // Update orbital angle (satellites only)
        if (b.orbit > 0) {
            float speed = (b.orbit == 1) ? 0.0015f : 0.001f;
            speed *= (1.0f + (b.id % 5) * 0.1f);  // Slight variation
            b.angle += speed * dt_ms;
            if (b.angle > 2.0f * M_PI) {
                b.angle -= 2.0f * M_PI;
            }
        }
    }
}

/**
 * Render current state to frame buffer.
 */
void render_frame(uint32_t now) {
    // Clear buffer
    memset(frame_buffer, 0, 104);

    for (int i = 0; i < body_count; i++) {
        Body& b = bodies[i];
        if (!b.active) continue;

        // Get position
        float x, y;
        get_position(b, x, y);

        // Round to pixel
        int px = (int)(x + 0.5f);
        int py = (int)(y + 0.5f);

        // Get pattern brightness
        uint8_t brightness = get_pattern_brightness(b.pattern, now);

        // Apply entry fade
        brightness = (uint8_t)(brightness * b.entry);

        // Apply global brightness
        brightness = (uint8_t)((brightness * global_brightness) >> 8);

        // Draw pixel
        if (px >= 0 && px < WIDTH && py >= 0 && py < HEIGHT) {
            set_pixel(px, py, brightness);
        }
    }

    // Send to matrix
    matrix.draw(frame_buffer);
}

/**
 * Bridge RPC: Update state from Python.
 * Format: [count, id0, pattern0, orbit0, id1, pattern1, orbit1, ...]
 */
void updateState(std::vector<uint8_t> data) {
    if (data.empty()) return;

    uint8_t new_count = data[0];
    if (new_count > 20) new_count = 20;

    // Track which bodies to keep
    bool found[20] = {false};

    // Process incoming bodies
    for (int i = 0; i < new_count && (1 + i * 3 + 2) < data.size(); i++) {
        int offset = 1 + i * 3;
        uint8_t id = data[offset];
        Pattern pattern = (Pattern)data[offset + 1];
        uint8_t orbit = data[offset + 2];

        // Find existing or add new
        int slot = -1;
        for (int j = 0; j < body_count; j++) {
            if (bodies[j].id == id && bodies[j].active) {
                slot = j;
                found[j] = true;
                break;
            }
        }

        if (slot >= 0) {
            // Update existing
            bodies[slot].pattern = pattern;
            bodies[slot].orbit = orbit;
        } else if (body_count < 20) {
            // Add new with entry animation
            Body& b = bodies[body_count];
            b.id = id;
            b.pattern = pattern;
            b.orbit = orbit;
            b.active = true;
            b.angle = (float)(id * 37) * 0.1f;  // Stagger angles
            b.entry = 0.0f;  // Start entry animation
            found[body_count] = true;
            body_count++;
        }
    }

    // Deactivate removed bodies
    for (int i = 0; i < body_count; i++) {
        if (!found[i]) {
            bodies[i].active = false;
        }
    }

    // Compact array
    int write = 0;
    for (int i = 0; i < body_count; i++) {
        if (bodies[i].active) {
            if (write != i) bodies[write] = bodies[i];
            write++;
        }
    }
    body_count = write;
}

/**
 * Bridge RPC: Set global brightness.
 */
void setBrightness(uint8_t level) {
    global_brightness = level;
}

/**
 * Bridge RPC: Clear display.
 */
void clearDisplay() {
    body_count = 0;
    memset(frame_buffer, 0, 104);
    matrix.draw(frame_buffer);
}

void setup() {
    // Initialize matrix
    matrix.begin();
    Serial.begin(115200);
    matrix.setGrayscaleBits(8);
    matrix.clear();

    // Setup Bridge RPC
    Bridge.begin();
    Bridge.provide("updateState", updateState);
    Bridge.provide("setBrightness", setBrightness);
    Bridge.provide("clear", clearDisplay);

    last_frame = millis();
}

void loop() {
    uint32_t now = millis();
    float dt = (float)(now - last_frame);

    // Limit to ~60fps
    if (dt < FRAME_INTERVAL) {
        delay(1);
        return;
    }

    last_frame = now;

    // Update physics
    update_physics(dt);

    // Render frame
    render_frame(now);
}
