// Arduino Trader LED Display
// Controls 8x13 LED matrix and RGB LEDs 3 & 4 on Arduino UNO Q
// Uses Router Bridge for communication with Linux MPU

#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <vector>

ArduinoLEDMatrix matrix;

// RGB LED pins use LED_BUILTIN offsets (from official unoq-pin-toggle example)
// LED3: LED_BUILTIN (R), LED_BUILTIN+1 (G), LED_BUILTIN+2 (B)
// LED4: LED_BUILTIN+3 (R), LED_BUILTIN+4 (G), LED_BUILTIN+5 (B)
// Active-low: HIGH = OFF, LOW = ON

// Draw frame to LED matrix (104 bytes = 8 rows x 13 cols grayscale)
void draw(std::vector<uint8_t> frame) {
  if (frame.empty() || frame.size() != 104) {
    return;
  }
  matrix.draw(frame.data());
}

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

#ifdef MATRIX_WITH_ARDUINOGRAPHICS
// Scroll text across LED matrix using ArduinoGraphics
// text: String to scroll, speed: ms per scroll step (lower = faster)
// NOTE: This is BLOCKING - will not return until text finishes scrolling
void scrollText(String text, int speed) {
  matrix.textScrollSpeed(speed);
  matrix.textFont(Font_5x7);
  matrix.beginText(13, 1, 0xFFFFFF);  // Start at right edge
  matrix.print(text);
  matrix.endText(SCROLL_LEFT);
}

// Display static text at position
void printText(String text, int x, int y) {
  matrix.textFont(Font_5x7);
  matrix.beginText(x, y, 0xFFFFFF);
  matrix.print(text);
  matrix.endText();
}
#else
// Fallback when ArduinoGraphics is not available
void scrollText(String text, int speed) {
  // Simple placeholder - just clear the display
  matrix.clear();
}

void printText(String text, int x, int y) {
  matrix.clear();
}
#endif

void setup() {
  // Initialize Router Bridge FIRST (before anything else)
  if (!Bridge.begin()) {
    // Bridge failed - halt
    while (true) { delay(1000); }
  }

  // Initialize Monitor for debug output
  if (!Monitor.begin()) {
    // Monitor failed - continue anyway
  }

  Monitor.println("Bridge initialized");

  // Initialize LED matrix
  matrix.begin();
  matrix.clear();
  Monitor.println("Matrix initialized");

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
  Monitor.println("LEDs initialized");

  // Register RPC methods with Router Bridge
  if (!Bridge.provide("draw", draw)) {
    Monitor.println("Error: failed to provide draw");
  }
  if (!Bridge.provide("setRGB3", setRGB3)) {
    Monitor.println("Error: failed to provide setRGB3");
  }
  if (!Bridge.provide("setRGB4", setRGB4)) {
    Monitor.println("Error: failed to provide setRGB4");
  }
  if (!Bridge.provide("scrollText", scrollText)) {
    Monitor.println("Error: failed to provide scrollText");
  }
  if (!Bridge.provide("printText", printText)) {
    Monitor.println("Error: failed to provide printText");
  }

  Monitor.println("RPC methods registered");
  Monitor.println("Setup complete - ready for commands");
}

void loop() {
  // Main loop - Router Bridge handles RPC in background thread
  delay(100);
}
