/**
 * Sentinel LED Display - Arduino Uno Q
 * 
 * Controls the 8x13 LED matrix and RGB LEDs 3 & 4 on Arduino UNO Q.
 * Uses Arduino_RouterBridge for communication with the Linux MPU.
 * 
 * Following Arduino Uno Q documentation:
 * https://docs.arduino.cc/tutorials/uno-q/user-manual/
 * 
 * Hardware:
 * - LED Matrix: 8 rows x 13 columns (104 LEDs)
 * - RGB LED 3: LED3_R (PH10), LED3_G (PH11), LED3_B (PH12) - Active LOW
 * - RGB LED 4: LED4_R (PH13), LED4_G (PH14), LED4_B (PH15) - Active LOW
 * 
 * Bridge Functions Exposed:
 * - scrollText(text, speed) - Scroll text across LED matrix
 * - setRGB3(r, g, b) - Set RGB LED 3 color (sync indicator)
 * - setRGB4(r, g, b) - Set RGB LED 4 color (processing indicator)
 * - clearMatrix() - Clear the LED matrix
 * - setMatrixBrightness(level) - Set matrix brightness (0-255)
 * - displayChar(ch) - Display a single character
 * - setPixelCount(count) - Light up specific number of pixels
 */

#include <Arduino_RouterBridge.h>
#include <ArduinoGraphics.h>
#include <Arduino_LED_Matrix.h>

// LED Matrix instance
ArduinoLEDMatrix matrix;

// Matrix dimensions
const uint8_t MATRIX_ROWS = 8;
const uint8_t MATRIX_COLS = 13;

// Current scroll speed (ms per step)
int currentScrollSpeed = 50;

// Current brightness level (0-255)
int currentBrightness = 128;

/**
 * Set RGB LED 3 color (sync indicator)
 * RGB LEDs are active-low: LOW = ON, HIGH = OFF
 * Uses predefined Arduino constants: LED3_R, LED3_G, LED3_B
 * 
 * @param r Red value (0-255, where 0=OFF, >0=ON due to active-low)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 */
void setRGB3(int r, int g, int b) {
    // Active-low: write LOW to turn ON, HIGH to turn OFF
    digitalWrite(LED3_R, r > 0 ? LOW : HIGH);
    digitalWrite(LED3_G, g > 0 ? LOW : HIGH);
    digitalWrite(LED3_B, b > 0 ? LOW : HIGH);
}

/**
 * Set RGB LED 4 color (processing indicator)
 * RGB LEDs are active-low: LOW = ON, HIGH = OFF
 * Uses predefined Arduino constants: LED4_R, LED4_G, LED4_B
 * 
 * @param r Red value (0-255, where 0=OFF, >0=ON due to active-low)
 * @param g Green value (0-255)
 * @param b Blue value (0-255)
 */
void setRGB4(int r, int g, int b) {
    // Active-low: write LOW to turn ON, HIGH to turn OFF
    digitalWrite(LED4_R, r > 0 ? LOW : HIGH);
    digitalWrite(LED4_G, g > 0 ? LOW : HIGH);
    digitalWrite(LED4_B, b > 0 ? LOW : HIGH);
}

/**
 * Scroll text across the LED matrix
 * 
 * @param text The text to scroll
 * @param speed Milliseconds per scroll step (lower = faster)
 */
void scrollText(String text, int speed) {
    // Store scroll speed
    currentScrollSpeed = speed;
    
    // Configure text scrolling
    matrix.textScrollSpeed(speed);
    matrix.textFont(Font_5x7);
    
    // Start scrolling from right edge (column 13)
    // Position: x=MATRIX_COLS (start off-screen right), y=1 (vertical position)
    matrix.beginText(MATRIX_COLS, 1, 0xFFFFFF);
    matrix.print(text);
    matrix.endText(SCROLL_LEFT);
}

/**
 * Clear the LED matrix
 */
void clearMatrix() {
    matrix.clear();
}

/**
 * Set matrix brightness level
 * Note: Arduino LED Matrix library uses grayscale bits for brightness control
 * 
 * @param level Brightness level (0-255)
 */
void setMatrixBrightness(int level) {
    currentBrightness = constrain(level, 0, 255);
    
    // The Arduino_LED_Matrix library supports grayscale via setGrayscaleBits
    // Higher bits = more grayscale levels but slower refresh
    // Map level to grayscale bits (1-8)
    int bits = map(currentBrightness, 0, 255, 1, 8);
    matrix.setGrayscaleBits(bits);
}

/**
 * Display a static character on the matrix
 * 
 * @param ch Single character to display
 */
void displayChar(String ch) {
    matrix.clear();
    matrix.textFont(Font_5x7);
    // Center the character (approximately)
    matrix.beginText(4, 1, 0xFFFFFF);
    matrix.print(ch.substring(0, 1)); // Take first char only
    matrix.endText();
}

/**
 * Set specific number of pixels to light up (for system stats visualization)
 * Fills pixels from left-to-right, top-to-bottom
 * 
 * @param pixelsOn Number of pixels to light (0-104)
 */
void setPixelCount(int pixelsOn) {
    // Constrain to valid range
    pixelsOn = constrain(pixelsOn, 0, MATRIX_ROWS * MATRIX_COLS);
    
    // Create a 2D bitmap for the matrix
    uint8_t bitmap[MATRIX_ROWS][MATRIX_COLS];
    
    // Clear the bitmap
    memset(bitmap, 0, sizeof(bitmap));
    
    // Fill pixels from left-to-right, top-to-bottom
    int count = 0;
    for (int row = 0; row < MATRIX_ROWS && count < pixelsOn; row++) {
        for (int col = 0; col < MATRIX_COLS && count < pixelsOn; col++) {
            bitmap[row][col] = 1;
            count++;
        }
    }
    
    // Render the bitmap
    matrix.renderBitmap(bitmap, MATRIX_ROWS, MATRIX_COLS);
}

void setup() {
    // Initialize LED matrix
    matrix.begin();
    matrix.clear();
    
    // Initialize RGB LED 3 pins (sync indicator)
    // Using predefined constants from Arduino Uno Q board package
    pinMode(LED3_R, OUTPUT);
    pinMode(LED3_G, OUTPUT);
    pinMode(LED3_B, OUTPUT);
    
    // Initialize RGB LED 4 pins (processing indicator)
    pinMode(LED4_R, OUTPUT);
    pinMode(LED4_G, OUTPUT);
    pinMode(LED4_B, OUTPUT);
    
    // Start with all LEDs off (active-low: HIGH = OFF)
    setRGB3(0, 0, 0);
    setRGB4(0, 0, 0);
    
    // Initialize Bridge for communication with Linux MPU
    Bridge.begin();
    
    // Expose functions to Python via Bridge
    Bridge.provide("scrollText", scrollText);
    Bridge.provide("setRGB3", setRGB3);
    Bridge.provide("setRGB4", setRGB4);
    Bridge.provide("clearMatrix", clearMatrix);
    Bridge.provide("setMatrixBrightness", setMatrixBrightness);
    Bridge.provide("displayChar", displayChar);
    Bridge.provide("setPixelCount", setPixelCount);
}

void loop() {
    // Bridge handles RPC communication in background thread
    // via __loopHook() - no need to call Bridge.loop()
    
    // Small delay to prevent busy-waiting
    delay(10);
}
