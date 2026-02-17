// NeoPixel Shield (8x5) — soroban abacus portfolio value display.
//
// Shield is natively 8 wide x 5 tall, progressive (non-serpentine) wiring.
// MPU sends Bridge.call("hm.u", [total_value_eur, return_pct, has_recs, broker_connected]).
// MCU displays the value as soroban-style decimal digits:
//   Row 0 (top): heaven bead (orange, worth 5)
//   Rows 1-4: earth bead position marker (amber, worth 1-4)
//   Only the single position-indicator bead is lit per earth section.
// Column 0 indicators:
//   r0: broker connected (red blink, 200ms on / 1000ms off) — only when data is fresh
//   r1-r3: P/L bar (green up / red down, 800ms blink)
//   r4: recommendations (blue, 100ms on / 300ms off) — pending trades exist
//
// Device-only patches (not in this repo):
// - bridge.h UPDATE_THREAD_STACK_SIZE changed from 500 to 8192
// - Arduino_RPClite.h DECODER_BUFFER_SIZE changed from 1024 to 256

#define MSGPACK_MAX_ARRAY_SIZE 48
#define MSGPACK_MAX_PACKET_BYTE_SIZE 48
#define MSGPACK_MAX_OBJECT_SIZE 48
#define ARX_HAVE_LIBSTDCPLUSPLUS 0

#include <Arduino_RouterBridge.h>
#include <Adafruit_NeoPixel.h>

#define PIN 6
#define NUMPIXELS 40
#define BRIGHTNESS 3  // raw RGB value

// --- WS2812 bitbang for STM32U585 (Zephyr) ---
#define GPIOB_BSRR (*(volatile uint32_t *)0x42020418UL)
#define PB1_SET    (1UL << 1)
#define PB1_RESET  (1UL << 17)

static uint32_t wsEndTime = 0;

static void ws2812_show(Adafruit_NeoPixel &strip) {
  uint8_t *p = strip.getPixels();
  uint16_t n = strip.numPixels() * 3;
  if (!p || n == 0) return;

  while ((micros() - wsEndTime) < 300) ;

  __asm volatile ("cpsid i" ::: "memory");

  for (uint16_t i = 0; i < n; i++) {
    uint8_t pix = p[i];
    for (uint8_t mask = 0x80; mask; mask >>= 1) {
      uint32_t hi = (pix & mask) ? 40u : 20u;
      GPIOB_BSRR = PB1_SET;
      __asm volatile (
        "1: subs %[c], #1\n"
        "   bne 1b\n"
        : [c] "+r" (hi) : : "cc"
      );
      GPIOB_BSRR = PB1_RESET;
      uint32_t lo = 35u;
      __asm volatile (
        "1: subs %[c], #1\n"
        "   bne 1b\n"
        : [c] "+r" (lo) : : "cc"
      );
    }
  }

  __asm volatile ("cpsie i" ::: "memory");
  wsEndTime = micros();
}

// --- Abacus display ---

Adafruit_NeoPixel pixels(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);

static int displayValue = 0;
static int displayPnl = 0;
static int hasRecs = 0;
static int brokerConnected = 0;
static bool needsRedraw = false;

// Last successful RPC timestamp (millis).
static unsigned long lastRpcMs = 0;
// Incoming data considered fresh if RPC received within 10 minutes.
#define HEARTBEAT_TIMEOUT_MS 600000UL

// Blink states (computed from millis modulo).
static bool pnlBlinkOn = true;
static bool heartbeatOn = false;
static bool recBlinkOn = false;

static void renderDisplay() {
  pixels.clear();

  int val = displayValue;
  if (val < 0) val = 0;

  // Extract 8 decimal digits, most-significant first.
  uint8_t digits[8];
  for (int i = 7; i >= 0; i--) {
    digits[i] = val % 10;
    val /= 10;
  }

  // Abacus on columns 1-7 (column 0 reserved for indicators).
  for (int col = 1; col < 8; col++) {
    uint8_t d = digits[col];

    // Heaven bead (row 0) — orange, lit if digit >= 5.
    if (d >= 5) {
      pixels.setPixelColor(col, pixels.Color(BRIGHTNESS, BRIGHTNESS / 3, 0));
    }

    // Earth bead — amber, single pixel at position.
    // earth 1 -> row 4, earth 2 -> row 3, earth 3 -> row 2, earth 4 -> row 1.
    uint8_t earth = d % 5;
    if (earth > 0) {
      int row = 5 - earth;
      pixels.setPixelColor(row * 8 + col, pixels.Color(BRIGHTNESS, BRIGHTNESS * 2 / 3, 0));
    }
  }

  // --- Column 0 indicators ---

  // Broker connected: c0r0, red, 200ms on / 1000ms off.
  unsigned long now = millis();
  bool dataFresh = (now - lastRpcMs < HEARTBEAT_TIMEOUT_MS);
  if (heartbeatOn && dataFresh && brokerConnected > 0) {
    pixels.setPixelColor(0, pixels.Color(BRIGHTNESS, 0, 0));
  }

  // P/L bar: c0r1-r3, green/red, 500ms blink.
  if (pnlBlinkOn && displayPnl != 0) {
    int pnl = displayPnl;
    if (pnl > 0) {
      pixels.setPixelColor(2 * 8, pixels.Color(0, BRIGHTNESS, 0));
      if (pnl > 10) {
        pixels.setPixelColor(1 * 8, pixels.Color(0, BRIGHTNESS, 0));
      }
    } else {
      pixels.setPixelColor(2 * 8, pixels.Color(BRIGHTNESS, 0, 0));
      if (pnl < -10) {
        pixels.setPixelColor(3 * 8, pixels.Color(BRIGHTNESS, 0, 0));
      }
    }
  }

  // Recommendations: c0r4, blue, 100ms on / 300ms off.
  if (recBlinkOn && hasRecs > 0) {
    pixels.setPixelColor(4 * 8, pixels.Color(0, 0, BRIGHTNESS));
  }

  ws2812_show(pixels);
}

// --- RPC handler ---
static void hmUpdate(MsgPack::arr_t<int> data) {
  if ((int)data.size() < 1) return;
  int val = data[0];
  if (val < 0) val = 0;
  if (val > 99999999) val = 99999999;
  displayValue = val;

  if ((int)data.size() >= 2) {
    displayPnl = data[1];
    if (displayPnl < -99) displayPnl = -99;
    if (displayPnl >  99) displayPnl =  99;
  }

  if ((int)data.size() >= 3) {
    hasRecs = data[2];
  }

  if ((int)data.size() >= 4) {
    brokerConnected = data[3] > 0 ? 1 : 0;
  }

  lastRpcMs = millis();
  needsRedraw = true;
}

void setup() {
  pixels.begin();
  pixels.clear();
  ws2812_show(pixels);

  Bridge.begin();
  Bridge.provide("hm.u", hmUpdate);
}

void loop() {
  Bridge.update();

  unsigned long now = millis();

  // Compute blink states from time (avoids per-feature timers).
  bool newPnlBlink = (now % 1600) < 800;
  bool newHeartbeat = (now % 1200) < 200;
  bool newRecBlink  = (now % 400) < 100;
  bool newDataFresh = (now - lastRpcMs < HEARTBEAT_TIMEOUT_MS);
  static bool dataFresh = false;

  // Redraw only when a visible blink state changes.
  bool changed = false;
  if (newPnlBlink != pnlBlinkOn && displayPnl != 0) changed = true;
  if (newHeartbeat != heartbeatOn && newDataFresh && brokerConnected > 0) changed = true;
  if (newDataFresh != dataFresh) changed = true;
  if (newRecBlink != recBlinkOn && hasRecs > 0) changed = true;

  pnlBlinkOn = newPnlBlink;
  heartbeatOn = newHeartbeat;
  recBlinkOn = newRecBlink;
  dataFresh = newDataFresh;

  if (changed) needsRedraw = true;

  if (needsRedraw) {
    needsRedraw = false;
    renderDisplay();
  }
}
