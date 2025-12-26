// Arduino Trader LED Display
// Simple text scroller for 8x13 LED matrix on Arduino UNO Q

#include <Arduino_RouterBridge.h>
#include "ArduinoGraphics.h"
#include "Arduino_LED_Matrix.h"

ArduinoLEDMatrix matrix;
String currentText = "";
int scrollSpeed = 50;
int brightness = 150;

void setText(String text) {
  currentText = text;
}

void setSpeed(int speed) {
  scrollSpeed = speed;
}

void setBrightness(int b) {
  brightness = b;
}

void setup() {
  matrix.begin();
  matrix.textFont(Font_5x7);

  Bridge.begin();
  Bridge.provide("setText", setText);
  Bridge.provide("setSpeed", setSpeed);
  Bridge.provide("setBrightness", setBrightness);
}

void loop() {
  if (currentText.length() > 0) {
    matrix.textScrollSpeed(scrollSpeed);
    // Convert brightness (0-255) to grayscale color
    uint32_t color = (brightness << 16) | (brightness << 8) | brightness;
    matrix.beginText(13, 1, color);
    matrix.print(currentText);
    matrix.endText(SCROLL_LEFT);
  } else {
    delay(100);
  }
}
