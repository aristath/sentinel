// Arduino Trader LED Display
// Controls 8x13 LED matrix and RGB LEDs 3 & 4 on Arduino UNO Q
// Uses Router Bridge for communication with Linux MPU

#include <Arduino_RouterBridge.h>
#include "ArduinoGraphics.h"
#include "Arduino_LED_Matrix.h"
#include <queue>

ArduinoLEDMatrix matrix;

// RGB LED pins use LED_BUILTIN offsets (from official unoq-pin-toggle example)
// LED3: LED_BUILTIN (R), LED_BUILTIN+1 (G), LED_BUILTIN+2 (B)
// LED4: LED_BUILTIN+3 (R), LED_BUILTIN+4 (G), LED_BUILTIN+5 (B)
// Active-low: HIGH = OFF, LOW = ON

// Command queue for scrollText (max 10 commands, latest-wins strategy)
std::queue<String> textQueue;
std::queue<int> speedQueue;
const int MAX_QUEUE_SIZE = 10;

// Track scrolling state manually (library doesn't have isScrolling())
bool isScrolling = false;
unsigned long scrollStartTime = 0;
unsigned long estimatedScrollDuration = 0;

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
  // If queue is full (10 messages), empty it completely
  // We only care about the latest message, not historical ones
  if (textQueue.size() >= MAX_QUEUE_SIZE) {
    // Empty entire queue - discard all old messages
    while (!textQueue.empty()) {
      textQueue.pop();
      speedQueue.pop();
    }
  }

  // Add the latest message
  textQueue.push(text);
  speedQueue.push(speed);
}

void setup() {
  // Initialize LED matrix
  matrix.begin();
  // Note: Serial.begin() removed - Router Bridge uses its own serial communication
  // and Serial can conflict with Bridge message processing
  matrix.setGrayscaleBits(8);  // For 0-255 brightness values
  matrix.clear();

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
}

void loop() {
  // Bridge handles RPC messages automatically in background thread
  // No need to call Bridge.loop() - it's handled by __loopHook()
  
  // Check if scrolling has completed
  if (isScrolling && (millis() - scrollStartTime >= estimatedScrollDuration)) {
    isScrolling = false;
  }

  // Process queue - always show the latest message
  // If multiple messages queued, process them in order until we get to the last one
  // This ensures we always show the most recent state
  if (!textQueue.empty() && !isScrolling) {
    // Process all queued messages until we get to the last one
    String text;
    int speed;

    while (!textQueue.empty()) {
      text = textQueue.front();
      speed = speedQueue.front();
      textQueue.pop();
      speedQueue.pop();
    }

    // Start scrolling with the latest message
    matrix.textScrollSpeed(speed);
    matrix.textFont(Font_5x7);
    matrix.beginText(13, 1, 0xFFFFFF);
    matrix.print(text);
    matrix.endText(SCROLL_LEFT);

    // Track scrolling state manually
    isScrolling = true;
    scrollStartTime = millis();
    // Estimate duration: matrix width (13) + text width (5 pixels per char) + buffer
    estimatedScrollDuration = (13 + (text.length() * 5) + 10) * speed;
  }

  // Small delay to allow Bridge background thread to process
  delay(10);
}
