// Arduino Trader LED Display
// Controls 8x13 LED matrix and RGB LEDs 3 & 4 on Arduino UNO Q
// Uses Router Bridge for communication with Linux MPU

#include <Arduino_RouterBridge.h>
#include "ArduinoGraphics.h"
#include "Arduino_LED_Matrix.h"

ArduinoLEDMatrix matrix;

// RGB LED pins use LED_BUILTIN offsets (from official unoq-pin-toggle example)
// LED3: LED_BUILTIN (R), LED_BUILTIN+1 (G), LED_BUILTIN+2 (B)
// LED4: LED_BUILTIN+3 (R), LED_BUILTIN+4 (G), LED_BUILTIN+5 (B)
// Active-low: HIGH = OFF, LOW = ON

// Latest-wins buffer (no queue needed - we only care about the latest message)
String pendingText = "";
int pendingSpeed = 50;
bool hasPendingText = false;

// Track scrolling state manually (library doesn't have isScrolling())
bool isScrolling = false;
unsigned long scrollStartTime = 0;
unsigned long estimatedScrollDuration = 0;

// LED Matrix dimensions
const int MATRIX_WIDTH = 13;
const int MATRIX_HEIGHT = 8;
const int TOTAL_PIXELS = MATRIX_WIDTH * MATRIX_HEIGHT;  // 104 pixels

// System stats mode state
bool inStatsMode = false;
uint8_t pixelBrightness[MATRIX_HEIGHT][MATRIX_WIDTH];  // 0-255 per pixel
int targetPixelsOn = 0;          // Target number of lit pixels (0-104)
uint8_t targetBrightness = 100;  // Target brightness for lit pixels (100-220)

// Animation timing
int pixelUpdateInterval = 2000;         // Dynamic 10ms-2000ms
unsigned long lastPixelUpdate = 0;

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

// Scroll text across LED matrix using native ArduinoGraphics
// text: String to scroll, speed: ms per scroll step (lower = faster)
void scrollText(String text, int speed) {
  // Latest-wins: always store the most recent message
  // Old messages are automatically discarded
  pendingText = text;
  pendingSpeed = speed;
  hasPendingText = true;
}

// System stats visualization: pixels_on (0-104), brightness (100-220), interval (10-2000)
void setSystemStats(int pixels_on, int brightness, int interval_ms) {
  targetPixelsOn = constrain(pixels_on, 0, TOTAL_PIXELS);
  targetBrightness = constrain(brightness, 100, 220);
  pixelUpdateInterval = constrain(interval_ms, 10, 2000);
  inStatsMode = true;
}

// Update pixel pattern - add or remove pixels to match target
void updatePixelPattern() {
  // Count currently lit pixels
  int currentLit = 0;
  for (int y = 0; y < MATRIX_HEIGHT; y++) {
    for (int x = 0; x < MATRIX_WIDTH; x++) {
      if (pixelBrightness[y][x] > 0) currentLit++;
    }
  }

  // Add or remove pixels to match target
  if (currentLit < targetPixelsOn) {
    // Add pixels with targetBrightness
    int attempts = 0;
    while (currentLit < targetPixelsOn && attempts < targetPixelsOn * 10) {
      int x = random(MATRIX_WIDTH);
      int y = random(MATRIX_HEIGHT);
      if (pixelBrightness[y][x] == 0) {
        pixelBrightness[y][x] = targetBrightness;
        currentLit++;
      }
      attempts++;
    }
  } else if (currentLit > targetPixelsOn) {
    // Remove pixels
    int attempts = 0;
    while (currentLit > targetPixelsOn && attempts < currentLit * 10) {
      int x = random(MATRIX_WIDTH);
      int y = random(MATRIX_HEIGHT);
      if (pixelBrightness[y][x] > 0) {
        pixelBrightness[y][x] = 0;
        currentLit--;
      }
      attempts++;
    }
  }

  // Render updated pattern
  renderBrightnessFrame();
}

// Render brightness frame to LED matrix
void renderBrightnessFrame() {
  // After setGrayscaleBits(8), we can load brightness values directly
  // TODO: Test which method works for loading brightness values
  //
  // For now, using binary on/off as fallback until brightness method is found
  // This will at least show pixel count correctly

  uint32_t frame[3] = {0, 0, 0};

  // Convert brightness array to binary frame (pixels with brightness > 0 are ON)
  int pixel_idx = 0;
  for (int y = 0; y < MATRIX_HEIGHT; y++) {
    for (int x = 0; x < MATRIX_WIDTH && x < 12; x++) {  // Matrix is 12 wide
      if (pixel_idx < 96 && pixelBrightness[y][x] > 0) {
        frame[pixel_idx / 32] |= (1UL << (pixel_idx % 32));
      }
      pixel_idx++;
    }
  }

  matrix.loadFrame(frame);
}

void setup() {
  // Initialize LED matrix
  matrix.begin();
  // Note: Serial.begin() removed - Router Bridge uses its own serial communication
  // and Serial can conflict with Bridge message processing
  matrix.setGrayscaleBits(8);  // Enable hardware brightness support (0-255 values)
  matrix.clear();

  // Initialize pixel brightness array (all OFF)
  memset(pixelBrightness, 0, sizeof(pixelBrightness));

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
  Bridge.provide("scrollText", scrollText);
  Bridge.provide("setSystemStats", setSystemStats);  // NEW: System stats mode

  // Seed random number generator for pixel randomization
  randomSeed(analogRead(0));
}

void loop() {
  // Bridge handles RPC messages automatically in background thread
  // No need to call Bridge.loop() - it's handled by __loopHook()

  unsigned long currentMillis = millis();

  // Pixel pattern updates at dynamic rate (stats mode only)
  if (inStatsMode && currentMillis - lastPixelUpdate >= pixelUpdateInterval) {
    lastPixelUpdate = currentMillis;
    updatePixelPattern();
  }

  // Check if scrolling has completed (ticker mode)
  if (isScrolling && (currentMillis - scrollStartTime >= estimatedScrollDuration)) {
    isScrolling = false;
  }

  // Process pending text - exits stats mode, enters ticker mode
  if (hasPendingText && !isScrolling) {
    inStatsMode = false;  // Exit stats mode when ticker arrives

    // Start scrolling with the latest message
    matrix.textScrollSpeed(pendingSpeed);
    matrix.textFont(Font_5x7);
    matrix.beginText(13, 1, 0xFFFFFF);
    matrix.print(pendingText);
    matrix.endText(SCROLL_LEFT);

    // Track scrolling state manually
    isScrolling = true;
    scrollStartTime = currentMillis;
    // Estimate duration: matrix width (13) + text width (5 pixels per char) + buffer
    estimatedScrollDuration = (13 + (pendingText.length() * 5) + 10) * pendingSpeed;

    // Clear pending flag
    hasPendingText = false;
  }

  // Small delay to allow Bridge background thread to process
  delay(10);
}
