// Arduino Trader LED Display
// System stats visualization with random pixel density and microservice health
// Controls 8x13 LED matrix and RGB LEDs 3 & 4 on Arduino UNO Q
// Uses Router Bridge for communication with Linux MPU

#include <Arduino_RouterBridge.h>
#include "Arduino_LED_Matrix.h"

ArduinoLEDMatrix matrix;

// RGB LED pins use LED_BUILTIN offsets (from official unoq-pin-toggle example)
// LED3: LED_BUILTIN (R), LED_BUILTIN+1 (G), LED_BUILTIN+2 (B)
// LED4: LED_BUILTIN+3 (R), LED_BUILTIN+4 (G), LED_BUILTIN+5 (B)
// Active-low: HIGH = OFF, LOW = ON

// LED Matrix state
const int MATRIX_WIDTH = 13;
const int MATRIX_HEIGHT = 8;
const int TOTAL_PIXELS = MATRIX_WIDTH * MATRIX_HEIGHT;  // 104 pixels

bool pixels[MATRIX_HEIGHT][MATRIX_WIDTH];
float targetFillPercentage = 0.0;  // 0.0-100.0
unsigned long lastRefresh = 0;
const int REFRESH_INTERVAL = 10;  // ms (100 FPS)

// Set RGB LED 3 color (active-low, digital only)
void setRGB3(uint8_t r, uint8_t g, uint8_t b) {
  digitalWrite(LED_BUILTIN, r > 0 ? LOW : HIGH);
  digitalWrite(LED_BUILTIN + 1, g > 0 ? LOW : HIGH);
  digitalWrite(LED_BUILTIN + 2, b > 0 ? LOW : HIGH);
}

// Set RGB LED 4 color (active-low, digital only)
void setRGB4(uint8_t r, uint8_t g, uint8_t b) {
  digitalWrite(LED_BUILTIN + 3, r > 0 ? LOW : HIGH);
  digitalWrite(LED_BUILTIN + 4, g > 0 ? LOW : HIGH);
  digitalWrite(LED_BUILTIN + 5, b > 0 ? LOW : HIGH);
}

// Set fill percentage for LED matrix (0.0-100.0)
void setFillPercentage(float percentage) {
  targetFillPercentage = constrain(percentage, 0.0, 100.0);
}

// Count number of pixels that are currently ON
int countOnPixels() {
  int count = 0;
  for (int row = 0; row < MATRIX_HEIGHT; row++) {
    for (int col = 0; col < MATRIX_WIDTH; col++) {
      if (pixels[row][col]) {
        count++;
      }
    }
  }
  return count;
}

// Toggle a random pixel with given current state to new state
// Returns true if successful, false if no pixel found after max attempts
bool toggleRandomPixel(bool currentState, bool newState) {
  int attempts = 0;
  while (attempts < 200) {
    int row = random(MATRIX_HEIGHT);
    int col = random(MATRIX_WIDTH);
    if (pixels[row][col] == currentState) {
      pixels[row][col] = newState;
      return true;
    }
    attempts++;
  }
  return false;
}

// Render pixel array to LED matrix
void renderPixels() {
  uint8_t frame[8][12];  // LED matrix uses 8x12 byte array

  // Clear frame
  for (int i = 0; i < 8; i++) {
    for (int j = 0; j < 12; j++) {
      frame[i][j] = 0;
    }
  }

  // Convert pixels to frame format
  // Each pixel is a single bit in the frame
  for (int row = 0; row < MATRIX_HEIGHT; row++) {
    for (int col = 0; col < MATRIX_WIDTH; col++) {
      if (pixels[row][col]) {
        int byteIndex = col / 8;
        int bitIndex = 7 - (col % 8);
        if (byteIndex < 12) {  // Safety check
          frame[row][byteIndex] |= (1 << bitIndex);
        }
      }
    }
  }

  matrix.renderBitmap(frame, 8, 12);
}

// Update random pixel display based on target fill percentage
void updateRandomPixels() {
  unsigned long now = millis();
  if (now - lastRefresh < REFRESH_INTERVAL) {
    return;
  }
  lastRefresh = now;

  int targetOn = (int)(TOTAL_PIXELS * targetFillPercentage / 100.0);
  int currentOn = countOnPixels();

  if (currentOn < targetOn) {
    // Turn on random OFF pixel
    toggleRandomPixel(false, true);
  } else if (currentOn > targetOn) {
    // Turn off random ON pixel
    toggleRandomPixel(true, false);
  } else if (targetFillPercentage > 0.0) {
    // At equilibrium and not at 0% - swap 5% of pixels (minimum 1) for visual effect
    int swapCount = max(1, (int)(TOTAL_PIXELS * 0.05));
    for (int i = 0; i < swapCount; i++) {
      toggleRandomPixel(true, false);   // Turn one OFF
      toggleRandomPixel(false, true);   // Turn one ON
    }
  }
  // If usage is 0%, don't swap any pixels (all OFF, no visual effect needed)

  renderPixels();
}

void setup() {
  // Initialize LED matrix
  matrix.begin();

  // Initialize pixel array (all OFF)
  for (int row = 0; row < MATRIX_HEIGHT; row++) {
    for (int col = 0; col < MATRIX_WIDTH; col++) {
      pixels[row][col] = false;
    }
  }

  // Initialize RGB LED 3 & 4 pins
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(LED_BUILTIN + 1, OUTPUT);
  pinMode(LED_BUILTIN + 2, OUTPUT);
  pinMode(LED_BUILTIN + 3, OUTPUT);
  pinMode(LED_BUILTIN + 4, OUTPUT);
  pinMode(LED_BUILTIN + 5, OUTPUT);

  // Start with LEDs off (active-low: HIGH = OFF)
  setRGB3(0, 0, 0);
  setRGB4(0, 0, 0);

  // Setup Router Bridge
  Bridge.begin();
  Bridge.provide("setRGB3", setRGB3);
  Bridge.provide("setRGB4", setRGB4);
  Bridge.provide("setFillPercentage", setFillPercentage);

  // Seed random number generator
  randomSeed(analogRead(0));

  // Initial render
  renderPixels();
}

void loop() {
  // Bridge handles RPC messages automatically in background thread
  // No need to call Bridge.loop() - it's handled by __loopHook()

  // Update pixel display at 100 FPS (10ms refresh)
  updateRandomPixels();

  // Small delay to allow Bridge background thread to process
  delay(1);
}
