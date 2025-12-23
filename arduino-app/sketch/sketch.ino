// Arduino Trader LED Display
// Controls 8x13 LED matrix and RGB LEDs 3 & 4 on Arduino UNO Q

#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <vector>

Arduino_LED_Matrix matrix;

// RGB LED 3 & 4 pins (active-low, driven by STM32U585)
// LED 3: D27401
#define LED3_R PH_10
#define LED3_G PH_11
#define LED3_B PH_12
// LED 4: D27402
#define LED4_R PH_13
#define LED4_G PH_14
#define LED4_B PH_15

// Draw frame to LED matrix
void draw(std::vector<uint8_t> frame) {
  if (frame.empty() || frame.size() != 104) {
    return;
  }
  matrix.draw(frame.data());
}

// Set RGB LED 3 color (active-low)
void setRGB3(uint8_t r, uint8_t g, uint8_t b) {
  analogWrite(LED3_R, 255 - r);
  analogWrite(LED3_G, 255 - g);
  analogWrite(LED3_B, 255 - b);
}

// Set RGB LED 4 color (active-low)
void setRGB4(uint8_t r, uint8_t g, uint8_t b) {
  analogWrite(LED4_R, 255 - r);
  analogWrite(LED4_G, 255 - g);
  analogWrite(LED4_B, 255 - b);
}

void setup() {
  // Initialize LED matrix
  matrix.begin();
  Serial.begin(115200);
  matrix.setGrayscaleBits(8);  // For 0-255 brightness values
  matrix.clear();

  // Initialize RGB LED 3 & 4 pins
  pinMode(LED3_R, OUTPUT);
  pinMode(LED3_G, OUTPUT);
  pinMode(LED3_B, OUTPUT);
  pinMode(LED4_R, OUTPUT);
  pinMode(LED4_G, OUTPUT);
  pinMode(LED4_B, OUTPUT);

  // Start with LEDs off (active-low means 255 = off)
  setRGB3(0, 0, 0);
  setRGB4(0, 0, 0);

  // Setup Router Bridge
  Bridge.begin();
  Bridge.provide("draw", draw);
  Bridge.provide("setRGB3", setRGB3);
  Bridge.provide("setRGB4", setRGB4);
}

void loop() {
  delay(100);
}
