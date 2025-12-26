// Arduino Trader LED Display
// Simple text scroller for 8x13 LED matrix on Arduino UNO Q
// Uses serial communication instead of Router Bridge

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
  // Initialize serial communication
  Serial.begin(115200);
  
  // Initialize LED matrix
  matrix.begin();
  matrix.textFont(Font_5x7);
}

void loop() {
  // Check for serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command.startsWith("TEXT:")) {
      String text = command.substring(5);
      setText(text);
    } else if (command.startsWith("SPEED:")) {
      int speed = command.substring(6).toInt();
      if (speed > 0) {
        setSpeed(speed);
      }
    } else if (command.startsWith("BRIGHTNESS:")) {
      int b = command.substring(11).toInt();
      if (b >= 0 && b <= 255) {
        setBrightness(b);
      }
    }
  }
  
  // Display text if available
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
