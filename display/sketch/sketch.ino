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
 * - RGB LED 3: LED_BUILTIN (R), LED_BUILTIN+1 (G), LED_BUILTIN+2 (B) - Active LOW
 * - RGB LED 4: LED_BUILTIN+3 (R), LED_BUILTIN+4 (G), LED_BUILTIN+5 (B) - Active LOW
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
// The ArduinoLEDMatrix library provides hardware-accelerated rendering
// for the 8x13 LED matrix on Arduino Uno Q
ArduinoLEDMatrix matrix;

// Matrix dimensions
// The LED matrix has 8 rows and 13 columns, for a total of 104 pixels
const uint8_t MATRIX_ROWS = 8;
const uint8_t MATRIX_COLS = 13;

// Scrolling text state
// These variables track the current scrolling text display mode
String currentText = "";           // The text string currently being displayed
int scrollOffset = 0;                // Current horizontal scroll position in pixels
unsigned long lastScrollTime = 0;   // Timestamp of last scroll update (for timing)
int scrollSpeed = 80;                // Scroll speed in milliseconds per pixel (lower = faster)

// Portfolio health animation state
// Maximum number of security clusters that can be displayed simultaneously
// Limited by available RAM and processing power
#define MAX_SECURITIES 20

/**
 * SecurityCluster represents a single security's health visualization
 * 
 * Each security is displayed as an animated cluster that moves organically
 * using Perlin noise. The cluster size and brightness are determined by
 * the security's health score (0-100).
 */
struct SecurityCluster {
    char symbol[11];      // Security symbol (10 chars + null terminator, e.g., "AAPL.US")
    uint8_t health;       // Health score 0-100 (0=unhealthy, 100=excellent)
    float centerX;        // Current X position (0.0 to 12.99, floating point for smooth movement)
    float centerY;        // Current Y position (0.0 to 7.99, floating point for smooth movement)
    float velocityX;      // Current horizontal velocity (pixels per frame)
    float velocityY;      // Current vertical velocity (pixels per frame)
    float noiseOffsetX;   // Perlin noise X offset (incremented each frame for animation)
    float noiseOffsetY;   // Perlin noise Y offset (incremented each frame for animation)
    float radius;        // Visual cluster radius (larger for healthier securities)
    bool active;         // Whether this cluster is currently active and should be rendered
};

// Portfolio health animation state variables
SecurityCluster clusters[MAX_SECURITIES];  // Array of all security clusters
uint8_t numActiveClusters = 0;             // Number of currently active clusters
bool healthMode = false;                    // Whether health animation mode is active (vs text scrolling)
unsigned long lastHealthFrame = 0;         // Timestamp of last health animation frame
uint16_t healthFrameInterval = 16;         // Frame interval in milliseconds (~60 FPS = 16ms per frame)

// 5x7 bitmap font configuration
// Each character is 5 columns wide, stored as column bytes where LSB = top row
// This is a custom font supporting uppercase letters, numbers, and common symbols
// Font data is stored in PROGMEM (program memory) to save RAM
const uint8_t FONT_WIDTH = 5;   // Character width in pixels (5 columns)
const uint8_t FONT_HEIGHT = 7;  // Character height in pixels (7 rows)

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

/**
 * Maps a character to its font data index
 * 
 * The font_data array contains bitmap data for each supported character.
 * This function converts a character to the corresponding index in that array.
 * Unsupported characters are mapped to space (index 0).
 * 
 * @param c The character to map
 * @return The font data index for the character, or 0 (space) if unsupported
 */
int getCharIndex(char c) {
    // Special symbols and punctuation
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
    // Numbers: '0' is index 12, '1' is 13, etc.
    if (c >= '0' && c <= '9') return 12 + (c - '0');
    if (c == ':') return 22;
    if (c == '=') return 23;
    if (c == '?') return 24;
    // Uppercase letters: 'A' is index 25, 'B' is 26, etc.
    if (c >= 'A' && c <= 'Z') return 25 + (c - 'A');
    // Lowercase letters are converted to uppercase (same font glyph)
    if (c >= 'a' && c <= 'z') return 25 + (c - 'a');
    if (c == '_') return 51;
    // Unknown character -> space (index 0)
    return 0;
}

/**
 * Gets a single column of bitmap data for a character
 * 
 * Each character is 5 columns wide. This function retrieves the byte data
 * for a specific column (0-4) of a character. The byte represents which
 * pixels in that column should be lit (LSB = top row).
 * 
 * @param c The character to get column data for
 * @param col The column index (0-4)
 * @return The column byte data, or 0 if column is out of range
 */
uint8_t getCharColumn(char c, int col) {
    if (col < 0 || col >= FONT_WIDTH) return 0;
    int idx = getCharIndex(c);
    // Read from PROGMEM (program memory) to save RAM
    return pgm_read_byte(&font_data[idx][col]);
}

/**
 * Calculates the total width of text in columns (including gaps between characters)
 * 
 * Each character is 5 pixels wide, with 1 pixel gap between characters.
 * This function calculates the total width needed to display the entire text string.
 * 
 * @param text The text string to measure
 * @return Total width in pixels (including character gaps)
 */
int getTextWidth(const String& text) {
    return text.length() * (FONT_WIDTH + 1);  // +1 for gap between chars
}

/**
 * Gets the column byte data at a specific position in the rendered text
 * 
 * This function maps a horizontal pixel position in the scrolling text
 * to the corresponding column byte data. It handles character boundaries
 * and gaps between characters.
 * 
 * @param text The text string being rendered
 * @param col The horizontal pixel position (0 = leftmost)
 * @return The column byte data at that position, or 0 if out of bounds or in a gap
 */
uint8_t getTextColumn(const String& text, int col) {
    if (col < 0 || text.length() == 0) return 0;
    
    // Each character takes up FONT_WIDTH pixels + 1 gap pixel
    int charWidth = FONT_WIDTH + 1;
    int charIndex = col / charWidth;  // Which character this position is in
    int charCol = col % charWidth;   // Which column within that character
    
    // Check bounds
    if (charIndex >= (int)text.length()) return 0;
    if (charCol >= FONT_WIDTH) return 0;  // This is a gap column (empty)
    
    // Get the column data for this character
    return getCharColumn(text.charAt(charIndex), charCol);
}

/**
 * Renders the current scrolling text frame to the LED matrix
 * 
 * This function takes the current scroll position and renders the visible
 * portion of the text onto the LED matrix. The text scrolls from right to left,
 * with padding on both sides so it scrolls completely off-screen before looping.
 * 
 * The frame buffer uses 3-bit grayscale (0-7 brightness levels), where 7 is
 * maximum brightness and 0 is off.
 */
void renderFrame() {
    // If no text, clear the matrix
    if (currentText.length() == 0) {
        matrix.clear();
        return;
    }
    
    // Frame buffer: 8 rows x 13 columns = 104 pixels
    uint8_t frame[MATRIX_ROWS * MATRIX_COLS];
    int textWidth = getTextWidth(currentText);
    // Total scroll width includes padding on both sides for smooth scrolling
    int totalWidth = MATRIX_COLS + textWidth + MATRIX_COLS;  // padding + text + padding
    
    // Render each pixel in the matrix
    for (int row = 0; row < MATRIX_ROWS; row++) {
        for (int col = 0; col < MATRIX_COLS; col++) {
            // Calculate which column in the text corresponds to this matrix column
            // scrollOffset is the current scroll position, MATRIX_COLS is left padding
            int textCol = scrollOffset + col - MATRIX_COLS;
            uint8_t colData = 0;
            
            // Get column data if we're within the text bounds
            if (textCol >= 0 && textCol < textWidth) {
                colData = getTextColumn(currentText, textCol);
            }
            
            // Check if this row's bit is set in the column byte
            // Font uses LSB = row 0 (top row), so we check bit position 'row'
            // If set, use maximum brightness (7), otherwise off (0)
            uint8_t pixel = (colData & (1 << row)) ? 7 : 0;
            frame[row * MATRIX_COLS + col] = pixel;
        }
    }
    
    // Send frame to hardware for display
    matrix.draw(frame);
}

/**
 * Sets the scrolling text to display on the LED matrix
 * 
 * This function is called via the Arduino Bridge from the Python app.
 * It sets the text that will scroll continuously from right to left.
 * The text will loop indefinitely until changed or cleared.
 * 
 * @param text The text string to display (will be converted to uppercase if needed)
 */
void setText(String text) {
    currentText = text;
    scrollOffset = 0;              // Reset scroll position to start
    lastScrollTime = millis();    // Reset scroll timer
    renderFrame();                 // Render initial frame immediately
}

/**
 * Sets RGB LED 3 color (service health/sync indicator)
 * 
 * LED 3 is used to indicate the health status of the main Sentinel service.
 * This function is called via the Arduino Bridge from the Python app.
 * 
 * RGB LEDs on Arduino Uno Q are active-low: LOW = ON, HIGH = OFF
 * This means we write LOW to turn on a color channel and HIGH to turn it off.
 * 
 * @param r Red component (0-255, any non-zero value turns red on)
 * @param g Green component (0-255, any non-zero value turns green on)
 * @param b Blue component (0-255, any non-zero value turns blue on)
 */
void setRGB3(uint8_t r, uint8_t g, uint8_t b) {
    // Active-low: LOW = LED on, HIGH = LED off
    // LED3 uses LED_BUILTIN (R), LED_BUILTIN+1 (G), LED_BUILTIN+2 (B)
    digitalWrite(LED_BUILTIN, r > 0 ? LOW : HIGH);
    digitalWrite(LED_BUILTIN + 1, g > 0 ? LOW : HIGH);
    digitalWrite(LED_BUILTIN + 2, b > 0 ? LOW : HIGH);
}

/**
 * Sets RGB LED 4 color (planner activity/processing indicator)
 * 
 * LED 4 is used to indicate when the planning system is actively generating
 * recommendations or evaluating trade sequences.
 * This function is called via the Arduino Bridge from the Python app.
 * 
 * RGB LEDs on Arduino Uno Q are active-low: LOW = ON, HIGH = OFF
 * 
 * @param r Red component (0-255, any non-zero value turns red on)
 * @param g Green component (0-255, any non-zero value turns green on)
 * @param b Blue component (0-255, any non-zero value turns blue on)
 */
void setRGB4(uint8_t r, uint8_t g, uint8_t b) {
    // Active-low: LOW = LED on, HIGH = LED off
    // LED4 uses LED_BUILTIN+3 (R), LED_BUILTIN+4 (G), LED_BUILTIN+5 (B)
    digitalWrite(LED_BUILTIN + 3, r > 0 ? LOW : HIGH);
    digitalWrite(LED_BUILTIN + 4, g > 0 ? LOW : HIGH);
    digitalWrite(LED_BUILTIN + 5, b > 0 ? LOW : HIGH);
}

/**
 * Clears the LED matrix and stops text scrolling
 * 
 * This function is called via the Arduino Bridge from the Python app.
 * It turns off all pixels on the LED matrix and resets the scrolling state.
 * This does not affect RGB LEDs 3 or 4.
 */
void clearMatrix() {
    currentText = "";      // Clear text string
    scrollOffset = 0;     // Reset scroll position
    matrix.clear();        // Turn off all matrix pixels
}

/**
 * Sets a specific number of pixels to light up (for system stats visualization)
 * 
 * This function is used to display system statistics as a bar graph.
 * Pixels are filled from left-to-right, top-to-bottom order.
 * This function is called via the Arduino Bridge from the Python app.
 * 
 * @param pixelsOn Number of pixels to light up (0-104, clamped to valid range)
 */
void setPixelCount(int pixelsOn) {
    // Stop any scrolling and health mode when switching to stats mode
    currentText = "";
    healthMode = false;
    
    // Clamp pixel count to valid range (0 to total matrix size)
    pixelsOn = constrain(pixelsOn, 0, MATRIX_ROWS * MATRIX_COLS);
    
    // Create frame buffer
    uint8_t frame[MATRIX_ROWS * MATRIX_COLS];
    
    // Fill pixels from left-to-right, top-to-bottom
    // Each pixel is either maximum brightness (7) or off (0)
    for (int i = 0; i < MATRIX_ROWS * MATRIX_COLS; i++) {
        frame[i] = (i < pixelsOn) ? 7 : 0;
    }
    
    // Render frame to matrix
    matrix.draw(frame);
}

// ============================================================================
// PORTFOLIO HEALTH ANIMATION
// ============================================================================

/**
 * Simple hash function for Perlin noise generation
 * 
 * This hash function converts an integer input into a pseudo-random integer.
 * It's used to generate deterministic "random" gradients for Perlin noise.
 * The same input always produces the same output (deterministic).
 * 
 * @param x Input integer value
 * @return Hashed integer value
 */
int32_t hash(int32_t x) {
    // Multi-stage hash mixing for good distribution
    x = ((x >> 16) ^ x) * 0x45d9f3b;
    x = ((x >> 16) ^ x) * 0x45d9f3b;
    x = (x >> 16) ^ x;
    return x;
}

/**
 * Gradient function for Perlin noise
 * 
 * Converts a hash value into a gradient value. The gradient determines
 * the direction and magnitude of the noise at a point.
 * 
 * @param hash Hash value (determines gradient direction)
 * @param x Position offset within the grid cell
 * @return Gradient value (positive or negative based on hash)
 */
float gradient(int32_t hash, float x) {
    // Use least significant bit to determine gradient direction
    return (hash & 1) ? x : -x;
}

/**
 * Linear interpolation between two values
 * 
 * Interpolates between 'a' and 'b' using parameter 't' (0.0 to 1.0).
 * When t=0, returns a; when t=1, returns b; values in between are interpolated.
 * 
 * @param a Start value
 * @param b End value
 * @param t Interpolation parameter (0.0 to 1.0)
 * @return Interpolated value
 */
float lerp(float a, float b, float t) {
    return a + t * (b - a);
}

/**
 * Simple 1D Perlin noise implementation
 * 
 * Perlin noise generates smooth, organic-looking random values that vary
 * continuously. This is used to create natural-looking movement for the
 * portfolio health clusters.
 * 
 * The algorithm:
 * 1. Determines which grid cell the point falls in
 * 2. Gets hash values for the grid cell boundaries
 * 3. Calculates gradients at those boundaries
 * 4. Interpolates between the gradients using a smooth curve
 * 
 * @param x Input position (can be fractional)
 * @return Noise value between -1.0 and 1.0
 */
float perlinNoise(float x) {
    // Get integer part (grid cell index) and fractional part (position within cell)
    int32_t xi = (int32_t)x;
    float xf = x - xi;
    
    // Fade curve (smoothstep) for smooth interpolation
    // This creates a smooth transition instead of linear interpolation
    float u = xf * xf * (3.0 - 2.0 * xf);
    
    // Get hash values for grid cell boundaries (deterministic pseudo-random)
    int32_t a = hash(xi);
    int32_t b = hash(xi + 1);
    
    // Interpolate between gradients at the two boundaries
    return lerp(gradient(a, xf), gradient(b, xf - 1.0), u);
}

/**
 * Parses JSON data and initializes security clusters for health animation
 * 
 * This function performs simple JSON parsing (no external library) to extract
 * security symbols and health scores from the JSON string received from Python.
 * 
 * Expected JSON format:
 * {
 *   "securities": [
 *     {"symbol": "AAPL", "health": 0.85},
 *     {"symbol": "MSFT", "health": 0.92},
 *     ...
 *   ]
 * }
 * 
 * Health values are expected as floats (0.0 to 1.0) and converted to 0-100 scale.
 * 
 * @param jsonData JSON string containing securities array with symbol and health fields
 */
void parseAndInitClusters(String jsonData) {
    numActiveClusters = 0;
    
    // Simple JSON parsing for Arduino
    // Find "securities" array
    int secStart = jsonData.indexOf("\"securities\"");
    if (secStart == -1) return;
    
    int arrayStart = jsonData.indexOf('[', secStart);
    if (arrayStart == -1) return;
    
    int pos = arrayStart + 1;
    
    while (numActiveClusters < MAX_SECURITIES) {
        // Find next object
        int objStart = jsonData.indexOf('{', pos);
        if (objStart == -1) break;
        
        int objEnd = jsonData.indexOf('}', objStart);
        if (objEnd == -1) break;
        
        String obj = jsonData.substring(objStart, objEnd + 1);
        
        // Extract symbol
        int symStart = obj.indexOf("\"symbol\"");
        if (symStart != -1) {
            int symValStart = obj.indexOf('\"', symStart + 8);
            int symValEnd = obj.indexOf('\"', symValStart + 1);
            if (symValStart != -1 && symValEnd != -1) {
                String symbol = obj.substring(symValStart + 1, symValEnd);
                symbol.toCharArray(clusters[numActiveClusters].symbol, 11);
            }
        }
        
        // Extract health
        int healthStart = obj.indexOf("\"health\"");
        if (healthStart != -1) {
            int healthValStart = obj.indexOf(':', healthStart);
            int healthValEnd = obj.indexOf(',', healthValStart);
            if (healthValEnd == -1) healthValEnd = obj.indexOf('}', healthValStart);
            
            if (healthValStart != -1 && healthValEnd != -1) {
                String healthStr = obj.substring(healthValStart + 1, healthValEnd);
                healthStr.trim();
                float healthFloat = healthStr.toFloat();
                clusters[numActiveClusters].health = (uint8_t)(healthFloat * 100.0);
            }
        }
        
        // Initialize cluster position and physics
        // Random starting position within matrix bounds (0-12.9 for X, 0-7.9 for Y)
        clusters[numActiveClusters].centerX = random(0, 130) / 10.0; // 0-13
        clusters[numActiveClusters].centerY = random(0, 80) / 10.0;  // 0-8
        // Start with zero velocity (will be set by Perlin noise)
        clusters[numActiveClusters].velocityX = 0;
        clusters[numActiveClusters].velocityY = 0;
        // Random noise offsets ensure each cluster moves independently
        clusters[numActiveClusters].noiseOffsetX = random(0, 1000) / 10.0;
        clusters[numActiveClusters].noiseOffsetY = random(0, 1000) / 10.0;
        // Radius scales with health: healthier securities have larger clusters
        // Base radius 2.0, up to 3.5 for 100% health
        clusters[numActiveClusters].radius = 2.0 + (clusters[numActiveClusters].health / 100.0) * 1.5;
        clusters[numActiveClusters].active = true;
        
        numActiveClusters++;
        pos = objEnd + 1;
    }
}

/**
 * Updates cluster positions using Perlin noise for organic movement
 * 
 * This function is called each frame to animate the security clusters.
 * Each cluster moves organically using Perlin noise, which creates smooth,
 * natural-looking motion. Clusters bounce softly off the matrix boundaries.
 * 
 * The animation uses:
 * - Perlin noise to generate smooth, continuous movement directions
 * - Velocity smoothing (90% old + 10% new) for fluid motion
 * - Soft boundary bouncing to keep clusters within matrix bounds
 */
void updateHealthClusters() {
    for (uint8_t i = 0; i < numActiveClusters; i++) {
        if (!clusters[i].active) continue;
        
        // Update Perlin noise offsets (increment for continuous animation)
        // Small increment (0.01) creates smooth, slow movement
        clusters[i].noiseOffsetX += 0.01;
        clusters[i].noiseOffsetY += 0.01;
        
        // Get noise values (-1 to 1) for X and Y movement directions
        float noiseX = perlinNoise(clusters[i].noiseOffsetX);
        float noiseY = perlinNoise(clusters[i].noiseOffsetY);
        
        // Update velocity with smoothing (90% old + 10% new)
        // This creates fluid, organic motion instead of jerky movement
        clusters[i].velocityX = clusters[i].velocityX * 0.9 + noiseX * 0.1;
        clusters[i].velocityY = clusters[i].velocityY * 0.9 + noiseY * 0.1;
        
        // Update position based on velocity
        // Small multiplier (0.05) keeps movement smooth and controlled
        clusters[i].centerX += clusters[i].velocityX * 0.05;
        clusters[i].centerY += clusters[i].velocityY * 0.05;
        
        // Soft boundary bounce - keep clusters within matrix bounds
        // When hitting a boundary, reverse velocity and reduce it by 50%
        if (clusters[i].centerX < 0) {
            clusters[i].centerX = 0;
            clusters[i].velocityX *= -0.5;
        }
        if (clusters[i].centerX > 12) {
            clusters[i].centerX = 12;
            clusters[i].velocityX *= -0.5;
        }
        if (clusters[i].centerY < 0) {
            clusters[i].centerY = 0;
            clusters[i].velocityY *= -0.5;
        }
        if (clusters[i].centerY > 7) {
            clusters[i].centerY = 7;
            clusters[i].velocityY *= -0.5;
        }
    }
}

/**
 * Renders the portfolio health animation frame to the LED matrix
 * 
 * This function calculates the brightness of each pixel based on its distance
 * from the nearest security cluster. Pixels closer to cluster centers are
 * brighter, and brightness also scales with the security's health score.
 * 
 * The algorithm:
 * 1. For each pixel, find the nearest active cluster
 * 2. Calculate distance from pixel to cluster center
 * 3. Calculate brightness based on distance (falloff) and health score
 * 4. Map to 3-bit grayscale (0-7 brightness levels)
 */
void renderHealthFrame() {
    uint8_t frame[MATRIX_ROWS * MATRIX_COLS];
    
    // For each pixel, find nearest cluster and calculate brightness
    for (uint8_t row = 0; row < MATRIX_ROWS; row++) {
        for (uint8_t col = 0; col < MATRIX_COLS; col++) {
            float minDist = 999.0;
            uint8_t nearestCluster = 0;
            
            // Find nearest cluster
            for (uint8_t i = 0; i < numActiveClusters; i++) {
                if (!clusters[i].active) continue;
                
                float dx = col - clusters[i].centerX;
                float dy = row - clusters[i].centerY;
                float dist = sqrt(dx*dx + dy*dy);
                
                if (dist < minDist) {
                    minDist = dist;
                    nearestCluster = i;
                }
            }
            
            // Calculate brightness based on distance and health
            uint8_t brightness = 0;
            // Only render if we have clusters and pixel is within 2x radius
            if (numActiveClusters > 0 && minDist < clusters[nearestCluster].radius * 2) {
                // Falloff from center: 1.0 at center, 0.0 at 2x radius
                // Creates smooth gradient from cluster center to edge
                float falloff = 1.0 - (minDist / (clusters[nearestCluster].radius * 2));
                if (falloff < 0) falloff = 0;
                
                // Health-based brightness: healthier securities are brighter
                // Health is stored as 0-100, convert to 0.0-1.0 factor
                float healthFactor = clusters[nearestCluster].health / 100.0;
                
                // Map to 0-7 brightness (3-bit grayscale)
                // Multiply falloff, health factor, and max brightness (7)
                brightness = (uint8_t)(falloff * healthFactor * 7.0);
            }
            
            frame[row * MATRIX_COLS + col] = brightness;
        }
    }
    
    matrix.draw(frame);
}

/**
 * Sets portfolio health data and starts health animation mode
 * 
 * This function is called via the Arduino Bridge from the Python app.
 * It receives JSON data with security symbols and health scores, parses it,
 * initializes the clusters, and switches the display to health animation mode.
 * 
 * @param jsonData JSON string containing securities array with symbol and health fields
 */
void setPortfolioHealth(String jsonData) {
    // Stop text scrolling when switching to health mode
    currentText = "";
    
    // Parse JSON and initialize clusters with security data
    parseAndInitClusters(jsonData);
    
    // Enable health animation mode (disables text scrolling)
    healthMode = true;
    lastHealthFrame = millis();  // Reset animation timer
    
    // Render initial frame immediately
    renderHealthFrame();
}

/**
 * Stops health animation mode and clears the matrix
 * 
 * This function is called via the Arduino Bridge from the Python app.
 * It disables health mode, clears all clusters, and clears the LED matrix.
 * The display can then be used for text scrolling or other modes.
 */
void stopHealthMode() {
    healthMode = false;        // Disable health mode
    numActiveClusters = 0;      // Clear all clusters
    matrix.clear();             // Turn off all matrix pixels
}

/**
 * Arduino setup function - called once at startup
 * 
 * Initializes all hardware (LED matrix, RGB LEDs) and sets up communication
 * with the Python app via the Arduino Bridge. This function runs once when
 * the Arduino boots up.
 */
void setup() {
    // Initialize LED matrix hardware
    matrix.begin();
    // Set 3-bit grayscale mode (0-7 brightness levels, 8 total levels)
    // This provides smooth brightness gradients for text and health animation
    matrix.setGrayscaleBits(3);
    matrix.clear();  // Start with matrix cleared
    
    // Initialize RGB LED 3 pins (service health/sync indicator)
    // LED3: LED_BUILTIN (R), LED_BUILTIN+1 (G), LED_BUILTIN+2 (B)
    pinMode(LED_BUILTIN, OUTPUT);       // LED3 R
    pinMode(LED_BUILTIN + 1, OUTPUT);   // LED3 G
    pinMode(LED_BUILTIN + 2, OUTPUT);   // LED3 B

    // Initialize RGB LED 4 pins (planner activity/processing indicator)
    // LED4: LED_BUILTIN+3 (R), LED_BUILTIN+4 (G), LED_BUILTIN+5 (B)
    pinMode(LED_BUILTIN + 3, OUTPUT);   // LED4 R
    pinMode(LED_BUILTIN + 4, OUTPUT);   // LED4 G
    pinMode(LED_BUILTIN + 5, OUTPUT);   // LED4 B
    
    // Start with all LEDs off (active-low: HIGH = OFF)
    setRGB3(0, 0, 0);
    setRGB4(0, 0, 0);
    
    // Flash LED3 green briefly to indicate sketch started successfully
    // This provides visual feedback that the Arduino is running
    setRGB3(0, 255, 0);
    delay(500);
    setRGB3(0, 0, 0);
    
    // Initialize Bridge for communication with Linux MPU (Python app)
    // The Bridge allows the Python app to call functions on the Arduino
    Bridge.begin();
    
    // Expose functions to Python via Bridge
    // These functions can be called from the Python app using Bridge.call()
    Bridge.provide("setText", setText);
    Bridge.provide("setRGB3", setRGB3);
    Bridge.provide("setRGB4", setRGB4);
    Bridge.provide("clearMatrix", clearMatrix);
    Bridge.provide("setPixelCount", setPixelCount);
    Bridge.provide("setPortfolioHealth", setPortfolioHealth);
    Bridge.provide("stopHealthMode", stopHealthMode);
}

/**
 * Arduino loop function - called repeatedly after setup
 * 
 * This is the main animation loop. It handles:
 * - Text scrolling animation (when text mode is active)
 * - Portfolio health animation (when health mode is active)
 * 
 * The loop runs continuously, updating the display at appropriate intervals
 * to create smooth animations. A small delay prevents CPU busy-waiting.
 */
void loop() {
    // Handle text scrolling animation
    // Only scroll if we have text and health mode is not active
    if (currentText.length() > 0 && !healthMode) {
        unsigned long now = millis();
        // Check if enough time has passed for next scroll step
        if (now - lastScrollTime >= (unsigned long)scrollSpeed) {
            lastScrollTime = now;
            
            // Advance scroll position by one pixel
            scrollOffset++;
            
            // Calculate total scroll width (left padding + text + right padding)
            int textWidth = getTextWidth(currentText);
            int totalWidth = MATRIX_COLS + textWidth + MATRIX_COLS;
            
            // Loop back to start when text has completely scrolled off
            // This creates continuous scrolling effect
            if (scrollOffset >= totalWidth) {
                scrollOffset = 0;
            }
            
            // Render the current frame with new scroll position
            renderFrame();
        }
    }
    
    // Handle portfolio health animation
    // Only animate if health mode is active and we have clusters
    if (healthMode && numActiveClusters > 0) {
        unsigned long now = millis();
        // Check if enough time has passed for next animation frame (~60 FPS)
        if (now - lastHealthFrame >= healthFrameInterval) {
            lastHealthFrame = now;
            // Update cluster positions using Perlin noise
            updateHealthClusters();
            // Render the updated frame
            renderHealthFrame();
        }
    }
    
    // Small delay to prevent busy-waiting and reduce CPU usage
    // This allows other Arduino tasks to run
    delay(1);
}
