// NeoPixel Shield (8x5) — soroban abacus portfolio value display.
//
// Shield is natively 8 wide x 5 tall, progressive (non-serpentine) wiring.
// MPU sends Bridge.call("hm.u", [total_value_eur]) — single int.
// MCU displays the value as soroban-style decimal digits:
//   Row 0 (top): heaven bead (blue, worth 5)
//   Rows 1-4: earth bead position marker (amber, worth 1-4)
//   Only the single position-indicator bead is lit per earth section.
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
static bool needsRedraw = false;

static void renderAbacus() {
  pixels.clear();

  int val = displayValue;
  if (val < 0) val = 0;

  // Extract 8 decimal digits, most-significant first.
  uint8_t digits[8];
  for (int i = 7; i >= 0; i--) {
    digits[i] = val % 10;
    val /= 10;
  }

  for (int col = 0; col < 8; col++) {
    uint8_t d = digits[col];

    // Heaven bead (row 0) — blue, lit if digit >= 5.
    if (d >= 5) {
      pixels.setPixelColor(col, pixels.Color(0, 0, BRIGHTNESS));
    }

    // Earth bead — amber, single pixel at position.
    // earth 1 -> row 4, earth 2 -> row 3, earth 3 -> row 2, earth 4 -> row 1.
    uint8_t earth = d % 5;
    if (earth > 0) {
      int row = 5 - earth;
      int px = row * 8 + col;
      pixels.setPixelColor(px, pixels.Color(BRIGHTNESS, BRIGHTNESS * 2 / 3, 0));
    }
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

  if (needsRedraw) {
    needsRedraw = false;
    renderAbacus();
  }
}
