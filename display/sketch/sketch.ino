// Arduino Trader LED Display
// Controls 8x13 LED matrix and RGB LEDs 3 & 4 on Arduino UNO Q
// Uses simple text-based serial protocol (no RouterBridge dependency)

#include "ArduinoGraphics.h"
#include "Arduino_LED_Matrix.h"
#include "portfolio_mode.h"

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

// Clustering strength: number of candidates to check per swap
// 1 = pure random (no clustering)
// 3-5 = moderate organic clustering
// 10+ = strong clustering
const int CLUSTERING_STRENGTH = 4;

// System stats mode state
bool inStatsMode = false;
uint8_t pixelBrightness[MATRIX_HEIGHT][MATRIX_WIDTH];  // 0-255 per pixel
int targetPixelsOn = 0;          // Target number of lit pixels (0-104)
uint8_t targetBrightness = 100;  // Target brightness for lit pixels (100-220)

// Efficient random pixel selection - smooth animation
uint8_t pixelIndices[TOTAL_PIXELS];  // Array of pixel positions [0, 1, 2, ..., 103]

// LED3 blink state
bool isBlinking3 = false;
uint8_t blinkColor3R = 0;
uint8_t blinkColor3G = 0;
uint8_t blinkColor3B = 0;
unsigned long blinkInterval3 = 1000;  // milliseconds
unsigned long lastBlinkTime3 = 0;
bool currentState3 = false;  // false = OFF, true = ON

// LED4 blink state
bool isBlinking4 = false;
uint8_t blinkColor4R = 0;
uint8_t blinkColor4G = 0;
uint8_t blinkColor4B = 0;
unsigned long blinkInterval4 = 1000;  // milliseconds
unsigned long lastBlinkTime4 = 0;
bool currentState4 = false;  // false = OFF, true = ON

// LED4 alternating color state
bool isAlternating4 = false;
uint8_t altColor4R1 = 0;
uint8_t altColor4G1 = 0;
uint8_t altColor4B1 = 0;
uint8_t altColor4R2 = 0;
uint8_t altColor4G2 = 0;
uint8_t altColor4B2 = 0;
bool currentAltColor4 = false;  // false = color1, true = color2

// LED4 coordinated mode (alternates with LED3)
bool isCoordinated4 = false;

// Serial command buffer
String commandBuffer = "";

// Set RGB LED 4 color (active-low, digital only)
void setRGB4(uint8_t r, uint8_t g, uint8_t b) {
  // Stop blinking when solid color is set
  isBlinking4 = false;
  isAlternating4 = false;
  isCoordinated4 = false;
  digitalWrite(LED_BUILTIN + 3, r > 0 ? LOW : HIGH);
  digitalWrite(LED_BUILTIN + 4, g > 0 ? LOW : HIGH);
  digitalWrite(LED_BUILTIN + 5, b > 0 ? LOW : HIGH);
}

// Set RGB LED 3 color (active-low, digital only) - stops blinking
void setRGB3(uint8_t r, uint8_t g, uint8_t b) {
  // Stop blinking when solid color is set
  isBlinking3 = false;
  digitalWrite(LED_BUILTIN, r > 0 ? LOW : HIGH);
  digitalWrite(LED_BUILTIN + 1, g > 0 ? LOW : HIGH);
  digitalWrite(LED_BUILTIN + 2, b > 0 ? LOW : HIGH);
}

// Start blinking LED3
void setBlink3(uint8_t r, uint8_t g, uint8_t b, unsigned long intervalMs) {
  isBlinking3 = true;
  blinkColor3R = r;
  blinkColor3G = g;
  blinkColor3B = b;
  blinkInterval3 = intervalMs;
  lastBlinkTime3 = millis();
  currentState3 = true;  // Start ON
  setRGB3(r, g, b);
}

// Stop blinking LED3
void stopBlink3() {
  isBlinking3 = false;
  setRGB3(0, 0, 0);
}

// Start blinking LED4 (simple blink)
void setBlink4(uint8_t r, uint8_t g, uint8_t b, unsigned long intervalMs) {
  isBlinking4 = true;
  isAlternating4 = false;
  isCoordinated4 = false;
  blinkColor4R = r;
  blinkColor4G = g;
  blinkColor4B = b;
  blinkInterval4 = intervalMs;
  lastBlinkTime4 = millis();
  currentState4 = true;  // Start ON
  setRGB4(r, g, b);
}

// Start LED4 alternating between two colors
void setBlink4Alternating(uint8_t r1, uint8_t g1, uint8_t b1, uint8_t r2, uint8_t g2, uint8_t b2, unsigned long intervalMs) {
  isBlinking4 = false;
  isAlternating4 = true;
  isCoordinated4 = false;
  altColor4R1 = r1;
  altColor4G1 = g1;
  altColor4B1 = b1;
  altColor4R2 = r2;
  altColor4G2 = g2;
  altColor4B2 = b2;
  blinkInterval4 = intervalMs;
  lastBlinkTime4 = millis();
  currentAltColor4 = false;  // Start with color1
  setRGB4(r1, g1, b1);
}

// Start LED4 coordinated with LED3 (LED4 ON when LED3 OFF)
void setBlink4Coordinated(uint8_t r, uint8_t g, uint8_t b, unsigned long intervalMs, bool led3Phase) {
  isBlinking4 = false;
  isAlternating4 = false;
  isCoordinated4 = true;
  blinkColor4R = r;
  blinkColor4G = g;
  blinkColor4B = b;
  blinkInterval4 = intervalMs;
  lastBlinkTime4 = millis();
  // LED4 state is inverse of LED3 state
  currentState4 = !led3Phase;
  if (currentState4) {
    setRGB4(r, g, b);
  } else {
    setRGB4(0, 0, 0);
  }
}

// Stop blinking LED4
void stopBlink4() {
  isBlinking4 = false;
  isAlternating4 = false;
  isCoordinated4 = false;
  setRGB4(0, 0, 0);
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

// System stats visualization: pixels_on (0-104), brightness (100-220)
// Note: interval_ms parameter kept for backwards compatibility but ignored (renders continuously)
void setSystemStats(int pixels_on, int brightness, int interval_ms) {
  targetPixelsOn = constrain(pixels_on, 0, TOTAL_PIXELS);
  targetBrightness = constrain(brightness, 100, 220);
  // interval_ms ignored - Arduino renders frames continuously without delay
  inStatsMode = true;
}

// Count lit neighbors for a given pixel position (8 surrounding pixels)
int countLitNeighbors(uint8_t x, uint8_t y) {
  int count = 0;
  for (int dy = -1; dy <= 1; dy++) {
    for (int dx = -1; dx <= 1; dx++) {
      if (dx == 0 && dy == 0) continue;  // Skip center pixel
      int nx = x + dx;
      int ny = y + dy;
      if (nx >= 0 && nx < MATRIX_WIDTH && ny >= 0 && ny < MATRIX_HEIGHT) {
        if (pixelBrightness[ny][nx] > 0) count++;
      }
    }
  }
  return count;
}

// Update pixel pattern - organic clustering with gravity
void updatePixelPattern() {
  // Only animate if we have pixels to work with
  if (targetPixelsOn > 0 && targetPixelsOn < TOTAL_PIXELS) {
    // Find most isolated lit pixel (check CLUSTERING_STRENGTH candidates)
    int bestLitIdx = random(targetPixelsOn);  // Fallback
    int minNeighbors = 9;

    for (int i = 0; i < CLUSTERING_STRENGTH; i++) {
      int idx = random(targetPixelsOn);
      uint8_t pos = pixelIndices[idx];
      uint8_t x = pos % MATRIX_WIDTH;
      uint8_t y = pos / MATRIX_WIDTH;
      int neighbors = countLitNeighbors(x, y);
      if (neighbors < minNeighbors) {
        minNeighbors = neighbors;
        bestLitIdx = idx;
      }
    }

    // Find dark pixel closest to clusters (check CLUSTERING_STRENGTH candidates)
    int bestDarkIdx = targetPixelsOn + random(TOTAL_PIXELS - targetPixelsOn);  // Fallback
    int maxNeighbors = -1;

    for (int i = 0; i < CLUSTERING_STRENGTH; i++) {
      int idx = targetPixelsOn + random(TOTAL_PIXELS - targetPixelsOn);
      uint8_t pos = pixelIndices[idx];
      uint8_t x = pos % MATRIX_WIDTH;
      uint8_t y = pos / MATRIX_WIDTH;
      int neighbors = countLitNeighbors(x, y);
      if (neighbors > maxNeighbors) {
        maxNeighbors = neighbors;
        bestDarkIdx = idx;
      }
    }

    // Swap isolated lit pixel with dark pixel near clusters
    uint8_t temp = pixelIndices[bestLitIdx];
    pixelIndices[bestLitIdx] = pixelIndices[bestDarkIdx];
    pixelIndices[bestDarkIdx] = temp;
  }

  // Update brightness array efficiently
  // Clear all pixels
  memset(pixelBrightness, 0, sizeof(pixelBrightness));

  // Set lit pixels based on current indices arrangement
  for (int i = 0; i < targetPixelsOn; i++) {
    uint8_t pos = pixelIndices[i];
    uint8_t x = pos % MATRIX_WIDTH;
    uint8_t y = pos / MATRIX_WIDTH;
    pixelBrightness[y][x] = targetBrightness;
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

  uint32_t frame[4] = {0, 0, 0, 0};  // 4 * 32 = 128 bits for 13x8 = 104 pixels

  // Convert brightness array to binary frame (pixels with brightness > 0 are ON)
  int pixel_idx = 0;
  for (int y = 0; y < MATRIX_HEIGHT; y++) {
    for (int x = 0; x < MATRIX_WIDTH; x++) {
      if (pixel_idx < TOTAL_PIXELS && pixelBrightness[y][x] > 0) {
        frame[pixel_idx / 32] |= (1UL << (pixel_idx % 32));
      }
      pixel_idx++;
    }
  }

  matrix.loadFrame(frame);
}

// Render portfolio mode frame with per-cluster brightness
void renderPortfolioFrame() {
  // Update brightness array based on cluster assignments
  memset(pixelBrightness, 0, sizeof(pixelBrightness));

  // Map each pixel to its cluster's brightness
  for (int y = 0; y < MATRIX_HEIGHT; y++) {
    for (int x = 0; x < MATRIX_WIDTH; x++) {
      uint8_t clusterID = pixelClusterID[y][x];
      if (clusterID > 0) {
        // Find cluster by ID and apply its brightness
        for (int c = 0; c < numClusters; c++) {
          if (clusters[c].clusterID == clusterID) {
            pixelBrightness[y][x] = clusters[c].brightness;
            break;
          }
        }
      }
    }
  }

  // Render the frame
  renderBrightnessFrame();
}

// Parse command from serial
void processCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  // Find command and arguments (format: COMMAND:arg1:arg2:arg3)
  int firstColon = cmd.indexOf(':');
  String command = firstColon > 0 ? cmd.substring(0, firstColon) : cmd;
  command.toUpperCase();

  if (command == "SCROLL") {
    // SCROLL:text:speed
    int secondColon = cmd.indexOf(':', firstColon + 1);
    if (secondColon > 0) {
      String text = cmd.substring(firstColon + 1, secondColon);
      int speed = cmd.substring(secondColon + 1).toInt();
      if (speed == 0) speed = 50;  // Default
      scrollText(text, speed);
      Serial.println("OK");
    } else {
      Serial.println("ERROR:Invalid format");
    }
  }
  else if (command == "RGB3") {
    // RGB3:r:g:b
    int colons[3];
    colons[0] = firstColon;
    for (int i = 1; i < 3; i++) {
      colons[i] = cmd.indexOf(':', colons[i-1] + 1);
    }
    if (colons[2] > 0) {
      uint8_t r = cmd.substring(colons[0] + 1, colons[1]).toInt();
      uint8_t g = cmd.substring(colons[1] + 1, colons[2]).toInt();
      uint8_t b = cmd.substring(colons[2] + 1).toInt();
      setRGB3(r, g, b);
      Serial.println("OK");
    } else {
      Serial.println("ERROR:Invalid format");
    }
  }
  else if (command == "RGB4") {
    // RGB4:r:g:b
    int colons[3];
    colons[0] = firstColon;
    for (int i = 1; i < 3; i++) {
      colons[i] = cmd.indexOf(':', colons[i-1] + 1);
    }
    if (colons[2] > 0) {
      uint8_t r = cmd.substring(colons[0] + 1, colons[1]).toInt();
      uint8_t g = cmd.substring(colons[1] + 1, colons[2]).toInt();
      uint8_t b = cmd.substring(colons[2] + 1).toInt();
      setRGB4(r, g, b);
      Serial.println("OK");
    } else {
      Serial.println("ERROR:Invalid format");
    }
  }
  else if (command == "BLINK3") {
    // BLINK3:r:g:b:interval
    int colons[4];
    colons[0] = firstColon;
    for (int i = 1; i < 4; i++) {
      colons[i] = cmd.indexOf(':', colons[i-1] + 1);
    }
    if (colons[3] > 0) {
      uint8_t r = cmd.substring(colons[0] + 1, colons[1]).toInt();
      uint8_t g = cmd.substring(colons[1] + 1, colons[2]).toInt();
      uint8_t b = cmd.substring(colons[2] + 1, colons[3]).toInt();
      unsigned long interval = cmd.substring(colons[3] + 1).toInt();
      setBlink3(r, g, b, interval);
      Serial.println("OK");
    } else {
      Serial.println("ERROR:Invalid format");
    }
  }
  else if (command == "BLINK4") {
    // BLINK4:r:g:b:interval
    int colons[4];
    colons[0] = firstColon;
    for (int i = 1; i < 4; i++) {
      colons[i] = cmd.indexOf(':', colons[i-1] + 1);
    }
    if (colons[3] > 0) {
      uint8_t r = cmd.substring(colons[0] + 1, colons[1]).toInt();
      uint8_t g = cmd.substring(colons[1] + 1, colons[2]).toInt();
      uint8_t b = cmd.substring(colons[2] + 1, colons[3]).toInt();
      unsigned long interval = cmd.substring(colons[3] + 1).toInt();
      setBlink4(r, g, b, interval);
      Serial.println("OK");
    } else {
      Serial.println("ERROR:Invalid format");
    }
  }
  else if (command == "BLINK4ALT") {
    // BLINK4ALT:r1:g1:b1:r2:g2:b2:interval
    int colons[7];
    colons[0] = firstColon;
    for (int i = 1; i < 7; i++) {
      colons[i] = cmd.indexOf(':', colons[i-1] + 1);
    }
    if (colons[6] > 0) {
      uint8_t r1 = cmd.substring(colons[0] + 1, colons[1]).toInt();
      uint8_t g1 = cmd.substring(colons[1] + 1, colons[2]).toInt();
      uint8_t b1 = cmd.substring(colons[2] + 1, colons[3]).toInt();
      uint8_t r2 = cmd.substring(colons[3] + 1, colons[4]).toInt();
      uint8_t g2 = cmd.substring(colons[4] + 1, colons[5]).toInt();
      uint8_t b2 = cmd.substring(colons[5] + 1, colons[6]).toInt();
      unsigned long interval = cmd.substring(colons[6] + 1).toInt();
      setBlink4Alternating(r1, g1, b1, r2, g2, b2, interval);
      Serial.println("OK");
    } else {
      Serial.println("ERROR:Invalid format");
    }
  }
  else if (command == "BLINK4COORD") {
    // BLINK4COORD:r:g:b:interval:phase
    int colons[5];
    colons[0] = firstColon;
    for (int i = 1; i < 5; i++) {
      colons[i] = cmd.indexOf(':', colons[i-1] + 1);
    }
    if (colons[4] > 0) {
      uint8_t r = cmd.substring(colons[0] + 1, colons[1]).toInt();
      uint8_t g = cmd.substring(colons[1] + 1, colons[2]).toInt();
      uint8_t b = cmd.substring(colons[2] + 1, colons[3]).toInt();
      unsigned long interval = cmd.substring(colons[3] + 1, colons[4]).toInt();
      bool phase = cmd.substring(colons[4] + 1).toInt() != 0;
      setBlink4Coordinated(r, g, b, interval, phase);
      Serial.println("OK");
    } else {
      Serial.println("ERROR:Invalid format");
    }
  }
  else if (command == "STOP3") {
    stopBlink3();
    Serial.println("OK");
  }
  else if (command == "STOP4") {
    stopBlink4();
    Serial.println("OK");
  }
  else if (command == "STATS") {
    // STATS:pixels:brightness:interval
    int colons[3];
    colons[0] = firstColon;
    for (int i = 1; i < 3; i++) {
      colons[i] = cmd.indexOf(':', colons[i-1] + 1);
    }
    if (colons[2] > 0) {
      int pixels = cmd.substring(colons[0] + 1, colons[1]).toInt();
      int brightness = cmd.substring(colons[1] + 1, colons[2]).toInt();
      int interval = cmd.substring(colons[2] + 1).toInt();
      setSystemStats(pixels, brightness, interval);
      Serial.println("OK");
    } else {
      Serial.println("ERROR:Invalid format");
    }
  }
  else if (command == "PORTFOLIO") {
    // PORTFOLIO:json_string
    String json = cmd.substring(firstColon + 1);
    setPortfolioMode(json.c_str());
    Serial.println("OK");
  }
  else {
    Serial.print("ERROR:Unknown command: ");
    Serial.println(command);
  }
}

void setup() {
  // Initialize Serial communication
  Serial.begin(115200);
  while (!Serial && millis() < 3000) {
    // Wait for serial port to connect (max 3 seconds)
  }

  // Initialize LED matrix
  matrix.begin();
  matrix.setGrayscaleBits(8);  // Enable hardware brightness support (0-255 values)
  matrix.clear();

  // Initialize pixel brightness array (all OFF)
  memset(pixelBrightness, 0, sizeof(pixelBrightness));

  // Initialize pixel indices array with sequential positions
  for (int i = 0; i < TOTAL_PIXELS; i++) {
    pixelIndices[i] = i;
  }

  // Seed random number generator for pixel randomization
  randomSeed(analogRead(0));

  // Do initial full shuffle to randomize starting pattern (Fisher-Yates)
  for (int i = 0; i < TOTAL_PIXELS - 1; i++) {
    int j = i + random(TOTAL_PIXELS - i);
    uint8_t temp = pixelIndices[i];
    pixelIndices[i] = pixelIndices[j];
    pixelIndices[j] = temp;
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

  Serial.println("READY");
}

void loop() {
  // Read serial commands
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (commandBuffer.length() > 0) {
        processCommand(commandBuffer);
        commandBuffer = "";
      }
    } else {
      commandBuffer += c;
      // Prevent buffer overflow
      if (commandBuffer.length() > 512) {
        commandBuffer = "";
        Serial.println("ERROR:Command too long");
      }
    }
  }

  // Render in portfolio mode at 40 FPS
  if (inPortfolioMode) {
    updatePortfolioPattern();
    renderPortfolioFrame();
    delay(25);  // 25ms = 40 FPS - fast and visible animation
  }
  // Render in stats mode at 40 FPS - fast and visible
  else if (inStatsMode) {
    updatePixelPattern();
    delay(25);  // 25ms = 40 FPS - faster, more visible animation
  }

  unsigned long currentMillis = millis();

  // Handle LED3 blinking
  if (isBlinking3) {
    if (currentMillis - lastBlinkTime3 >= blinkInterval3) {
      currentState3 = !currentState3;
      lastBlinkTime3 = currentMillis;
      if (currentState3) {
        setRGB3(blinkColor3R, blinkColor3G, blinkColor3B);
      } else {
        setRGB3(0, 0, 0);
      }
    }
  }

  // Handle LED4 blinking modes
  if (isAlternating4) {
    // Alternating color mode
    if (currentMillis - lastBlinkTime4 >= blinkInterval4) {
      currentAltColor4 = !currentAltColor4;
      lastBlinkTime4 = currentMillis;
      if (currentAltColor4) {
        setRGB4(altColor4R2, altColor4G2, altColor4B2);
      } else {
        setRGB4(altColor4R1, altColor4G1, altColor4B1);
      }
    }
  } else if (isCoordinated4) {
    // Coordinated mode: LED4 is inverse of LED3
    if (isBlinking3) {
      // LED4 state should be inverse of LED3 state
      bool desiredState4 = !currentState3;
      if (desiredState4 != currentState4) {
        currentState4 = desiredState4;
        if (currentState4) {
          setRGB4(blinkColor4R, blinkColor4G, blinkColor4B);
        } else {
          setRGB4(0, 0, 0);
        }
      }
    }
  } else if (isBlinking4) {
    // Simple blink mode
    if (currentMillis - lastBlinkTime4 >= blinkInterval4) {
      currentState4 = !currentState4;
      lastBlinkTime4 = currentMillis;
      if (currentState4) {
        setRGB4(blinkColor4R, blinkColor4G, blinkColor4B);
      } else {
        setRGB4(0, 0, 0);
      }
    }
  }

  // Check if scrolling has completed (ticker mode)
  if (isScrolling && (currentMillis - scrollStartTime >= estimatedScrollDuration)) {
    isScrolling = false;
  }

  // Process pending text - exits stats/portfolio mode, enters ticker mode
  if (hasPendingText && !isScrolling) {
    inStatsMode = false;  // Exit stats mode when ticker arrives
    inPortfolioMode = false;  // Exit portfolio mode when ticker arrives

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
}
