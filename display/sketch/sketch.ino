/**
 * Sentinel LED Display - Arduino Sketch
 * 
 * Controls the LED matrix and RGB LEDs on Arduino Uno Q.
 * Communicates with Python via Arduino Router Bridge.
 * 
 * Following Arduino Uno Q documentation:
 * https://docs.arduino.cc/tutorials/uno-q/user-manual/
 * 
 * Hardware:
 * - LED Matrix: 8 rows x 13 columns (104 LEDs)
 * - RGB LED 3: LED3_R, LED3_G, LED3_B - Active LOW
 * - RGB LED 4: LED4_R, LED4_G, LED4_B - Active LOW
 * 
 * Bridge Functions Exposed:
 * - setText(text) - Set scrolling text
 * - setRGB3(r, g, b) - Set RGB LED 3 color (sync indicator)
 * - setRGB4(r, g, b) - Set RGB LED 4 color (processing indicator)
 * - clearMatrix() - Clear the LED matrix
 * - setPixelCount(count) - Light up specific number of pixels
 */

#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>

// LED Matrix instance
ArduinoLEDMatrix matrix;

// Matrix dimensions
const uint8_t MATRIX_ROWS = 8;
const uint8_t MATRIX_COLS = 13;

// Scrolling text state
String currentText = "";
int scrollOffset = 0;
unsigned long lastScrollTime = 0;
int scrollSpeed = 80;  // ms per pixel

// 5x7 bitmap font - each character is 5 columns, stored as column bytes (LSB = top row)
// Only uppercase letters, numbers, and common symbols
const uint8_t FONT_WIDTH = 5;
const uint8_t FONT_HEIGHT = 7;

// Font data stored in PROGMEM to save RAM
const uint8_t PROGMEM font_data[][5] = {
    {0x00, 0x00, 0x00, 0x00, 0x00}, // ' ' (space) - index 0
    {0x00, 0x00, 0x5F, 0x00, 0x00}, // '!' - index 1
    {0x24, 0x2A, 0x7F, 0x2A, 0x12}, // '$' - index 2
    {0x23, 0x13, 0x08, 0x64, 0x62}, // '%' - index 3
    {0x00, 0x1C, 0x22, 0x41, 0x00}, // '(' - index 4
    {0x00, 0x41, 0x22, 0x1C, 0x00}, // ')' - index 5
    {0x14, 0x08, 0x3E, 0x08, 0x14}, // '*' - index 6
    {0x08, 0x08, 0x3E, 0x08, 0x08}, // '+' - index 7
    {0x00, 0x80, 0x60, 0x00, 0x00}, // ',' - index 8
    {0x08, 0x08, 0x08, 0x08, 0x08}, // '-' - index 9
    {0x00, 0x60, 0x60, 0x00, 0x00}, // '.' - index 10
    {0x20, 0x10, 0x08, 0x04, 0x02}, // '/' - index 11
    {0x3E, 0x51, 0x49, 0x45, 0x3E}, // '0' - index 12
    {0x00, 0x42, 0x7F, 0x40, 0x00}, // '1' - index 13
    {0x42, 0x61, 0x51, 0x49, 0x46}, // '2' - index 14
    {0x21, 0x41, 0x45, 0x4B, 0x31}, // '3' - index 15
    {0x18, 0x14, 0x12, 0x7F, 0x10}, // '4' - index 16
    {0x27, 0x45, 0x45, 0x45, 0x39}, // '5' - index 17
    {0x3C, 0x4A, 0x49, 0x49, 0x30}, // '6' - index 18
    {0x01, 0x71, 0x09, 0x05, 0x03}, // '7' - index 19
    {0x36, 0x49, 0x49, 0x49, 0x36}, // '8' - index 20
    {0x06, 0x49, 0x49, 0x29, 0x1E}, // '9' - index 21
    {0x00, 0x36, 0x36, 0x00, 0x00}, // ':' - index 22
    {0x14, 0x14, 0x14, 0x14, 0x14}, // '=' - index 23
    {0x02, 0x01, 0x51, 0x09, 0x06}, // '?' - index 24
    {0x7E, 0x09, 0x09, 0x09, 0x7E}, // 'A' - index 25
    {0x7F, 0x49, 0x49, 0x49, 0x36}, // 'B' - index 26
    {0x3E, 0x41, 0x41, 0x41, 0x22}, // 'C' - index 27
    {0x7F, 0x41, 0x41, 0x41, 0x3E}, // 'D' - index 28
    {0x7F, 0x49, 0x49, 0x49, 0x41}, // 'E' - index 29
    {0x7F, 0x09, 0x09, 0x09, 0x01}, // 'F' - index 30
    {0x3E, 0x41, 0x49, 0x49, 0x7A}, // 'G' - index 31
    {0x7F, 0x08, 0x08, 0x08, 0x7F}, // 'H' - index 32
    {0x00, 0x41, 0x7F, 0x41, 0x00}, // 'I' - index 33
    {0x20, 0x40, 0x41, 0x3F, 0x01}, // 'J' - index 34
    {0x7F, 0x08, 0x14, 0x22, 0x41}, // 'K' - index 35
    {0x7F, 0x40, 0x40, 0x40, 0x40}, // 'L' - index 36
    {0x7F, 0x02, 0x0C, 0x02, 0x7F}, // 'M' - index 37
    {0x7F, 0x04, 0x08, 0x10, 0x7F}, // 'N' - index 38
    {0x3E, 0x41, 0x41, 0x41, 0x3E}, // 'O' - index 39
    {0x7F, 0x09, 0x09, 0x09, 0x06}, // 'P' - index 40
    {0x3E, 0x41, 0x51, 0x21, 0x5E}, // 'Q' - index 41
    {0x7F, 0x09, 0x19, 0x29, 0x46}, // 'R' - index 42
    {0x46, 0x49, 0x49, 0x49, 0x31}, // 'S' - index 43
    {0x01, 0x01, 0x7F, 0x01, 0x01}, // 'T' - index 44
    {0x3F, 0x40, 0x40, 0x40, 0x3F}, // 'U' - index 45
    {0x1F, 0x20, 0x40, 0x20, 0x1F}, // 'V' - index 46
    {0x3F, 0x40, 0x38, 0x40, 0x3F}, // 'W' - index 47
    {0x63, 0x14, 0x08, 0x14, 0x63}, // 'X' - index 48
    {0x07, 0x08, 0x70, 0x08, 0x07}, // 'Y' - index 49
    {0x61, 0x51, 0x49, 0x45, 0x43}, // 'Z' - index 50
    {0x40, 0x40, 0x40, 0x40, 0x40}, // '_' - index 51
};

// Character to font index mapping
int getCharIndex(char c) {
    if (c == ' ') return 0;
    if (c == '!') return 1;
    if (c == '$') return 2;
    if (c == '%') return 3;
    if (c == '(') return 4;
    if (c == ')') return 5;
    if (c == '*') return 6;
    if (c == '+') return 7;
    if (c == ',') return 8;
    if (c == '-') return 9;
    if (c == '.') return 10;
    if (c == '/') return 11;
    if (c >= '0' && c <= '9') return 12 + (c - '0');
    if (c == ':') return 22;
    if (c == '=') return 23;
    if (c == '?') return 24;
    if (c >= 'A' && c <= 'Z') return 25 + (c - 'A');
    if (c >= 'a' && c <= 'z') return 25 + (c - 'a');  // lowercase -> uppercase
    if (c == '_') return 51;
    return 0;  // Unknown char -> space
}

// Get column data for a character
uint8_t getCharColumn(char c, int col) {
    if (col < 0 || col >= FONT_WIDTH) return 0;
    int idx = getCharIndex(c);
    return pgm_read_byte(&font_data[idx][col]);
}

// Calculate total width of text in columns (including gaps)
int getTextWidth(const String& text) {
    return text.length() * (FONT_WIDTH + 1);  // +1 for gap between chars
}

// Get column byte at position in rendered text
uint8_t getTextColumn(const String& text, int col) {
    if (col < 0 || text.length() == 0) return 0;
    
    int charWidth = FONT_WIDTH + 1;  // char width + gap
    int charIndex = col / charWidth;
    int charCol = col % charWidth;
    
    if (charIndex >= (int)text.length()) return 0;
    if (charCol >= FONT_WIDTH) return 0;  // Gap column
    
    return getCharColumn(text.charAt(charIndex), charCol);
}

// Render current frame to matrix
void renderFrame() {
    if (currentText.length() == 0) {
        matrix.clear();
        return;
    }
    
    uint8_t frame[MATRIX_ROWS * MATRIX_COLS];
    int textWidth = getTextWidth(currentText);
    int totalWidth = MATRIX_COLS + textWidth + MATRIX_COLS;  // padding + text + padding
    
    // Render each pixel
    for (int row = 0; row < MATRIX_ROWS; row++) {
        for (int col = 0; col < MATRIX_COLS; col++) {
            int textCol = scrollOffset + col - MATRIX_COLS;  // Subtract left padding
            uint8_t colData = 0;
            
            if (textCol >= 0 && textCol < textWidth) {
                colData = getTextColumn(currentText, textCol);
            }
            
            // Check if this row's bit is set in the column
            // Font uses LSB = row 0 (top)
            uint8_t pixel = (colData & (1 << row)) ? 7 : 0;
            frame[row * MATRIX_COLS + col] = pixel;
        }
    }
    
    matrix.draw(frame);
}

/**
 * Set scrolling text
 * Text will scroll continuously until changed
 */
void setText(String text) {
    currentText = text;
    scrollOffset = 0;
    lastScrollTime = millis();
    renderFrame();
}

/**
 * Set RGB LED 3 color (sync indicator)
 * RGB LEDs are active-low: LOW = ON, HIGH = OFF
 */
void setRGB3(int r, int g, int b) {
    digitalWrite(LED3_R, r > 0 ? LOW : HIGH);
    digitalWrite(LED3_G, g > 0 ? LOW : HIGH);
    digitalWrite(LED3_B, b > 0 ? LOW : HIGH);
}

/**
 * Set RGB LED 4 color (processing indicator)
 * RGB LEDs are active-low: LOW = ON, HIGH = OFF
 */
void setRGB4(int r, int g, int b) {
    digitalWrite(LED4_R, r > 0 ? LOW : HIGH);
    digitalWrite(LED4_G, g > 0 ? LOW : HIGH);
    digitalWrite(LED4_B, b > 0 ? LOW : HIGH);
}

/**
 * Clear the LED matrix and stop scrolling
 */
void clearMatrix() {
    currentText = "";
    scrollOffset = 0;
    matrix.clear();
}

/**
 * Set specific number of pixels to light up (for system stats visualization)
 * Fills pixels from left-to-right, top-to-bottom
 */
void setPixelCount(int pixelsOn) {
    // Stop any scrolling
    currentText = "";
    
    pixelsOn = constrain(pixelsOn, 0, MATRIX_ROWS * MATRIX_COLS);
    
    uint8_t frame[MATRIX_ROWS * MATRIX_COLS];
    
    for (int i = 0; i < MATRIX_ROWS * MATRIX_COLS; i++) {
        frame[i] = (i < pixelsOn) ? 7 : 0;
    }
    
    matrix.draw(frame);
}

void setup() {
    // Initialize LED matrix
    matrix.begin();
    matrix.setGrayscaleBits(3);  // 3-bit grayscale (0-7 brightness levels)
    matrix.clear();
    
    // Initialize RGB LED 3 pins (sync indicator)
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
    
    // Flash LED3 green briefly to indicate sketch started
    setRGB3(0, 255, 0);
    delay(500);
    setRGB3(0, 0, 0);
    
    // Initialize Bridge for communication with Linux MPU
    Bridge.begin();
    
    // Expose functions to Python via Bridge
    Bridge.provide("setText", setText);
    Bridge.provide("setRGB3", setRGB3);
    Bridge.provide("setRGB4", setRGB4);
    Bridge.provide("clearMatrix", clearMatrix);
    Bridge.provide("setPixelCount", setPixelCount);
}

void loop() {
    // Handle text scrolling
    if (currentText.length() > 0) {
        unsigned long now = millis();
        if (now - lastScrollTime >= (unsigned long)scrollSpeed) {
            lastScrollTime = now;
            
            // Advance scroll position
            scrollOffset++;
            
            // Calculate total scroll width (padding + text + padding)
            int textWidth = getTextWidth(currentText);
            int totalWidth = MATRIX_COLS + textWidth + MATRIX_COLS;
            
            // Loop back when text has scrolled off
            if (scrollOffset >= totalWidth) {
                scrollOffset = 0;
            }
            
            renderFrame();
        }
    }
    
    // Small delay to prevent busy-waiting
    delay(1);
}
