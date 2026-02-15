// NeoPixel Shield (8×5) — heartbeat pulse portfolio indicator.
//
// Shield is natively 8 wide × 5 tall, progressive (non-serpentine) wiring.
// MPU sends Bridge.call("hm.u", [return_pct]) — single int, range [-99, 99].
// MCU pulses a heartbeat ripple from center, colored by portfolio direction:
//   green (> +1%), red (< -1%), yellow (-1% to +1%).
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
#define BRIGHTNESS 3  // peak brightness (raw RGB value)

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

// --- Heartbeat animation ---

// Distance from center (3.5, 2.0) for each pixel, scaled 0-100.
static uint8_t dist[NUMPIXELS];

// Timing
#define FRAME_MS       50   // 20 fps
#define BEAT_MS      1400   // full heartbeat cycle
#define P1_DUR        250   // first pulse duration
#define P2_START      350   // second pulse start
#define P2_DUR        150   // second pulse duration
#define WAVE_W         25   // wave ring width (in dist units)

static unsigned long lastFrame = 0;

static void precomputeDistances() {
  for (int y = 0; y < 5; y++) {
    for (int x = 0; x < 8; x++) {
      int dx = x * 10 - 35;  // (x - 3.5) * 10
      int dy = y * 10 - 20;  // (y - 2.0) * 10
      int d2 = dx * dx + dy * dy;
      // integer sqrt
      int d = 0;
      for (int bit = 64; bit > 0; bit >>= 1) {
        int t = d + bit;
        if (t * t <= d2) d = t;
      }
      // d is distance*10 (range ~5 to ~40), scale to 0-100
      dist[y * 8 + x] = (uint8_t)((d * 5) / 2);
    }
  }
}

Adafruit_NeoPixel pixels(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);

static int displayValue = 0;
static bool hasData = false;

static void renderFrame() {
  unsigned long phase = millis() % BEAT_MS;

  // Wave positions (0-100), -1 = inactive.
  int wave1 = -1, wave2 = -1;
  if (phase < P1_DUR)
    wave1 = (int)(phase * 100 / P1_DUR);
  if (phase >= P2_START && phase < P2_START + P2_DUR)
    wave2 = (int)((phase - P2_START) * 100 / P2_DUR);

  // Base color unit vector.
  uint8_t cR, cG, cB;
  if (displayValue > 1)       { cR = 0; cG = 1; cB = 0; }
  else if (displayValue < -1) { cR = 1; cG = 0; cB = 0; }
  else                        { cR = 1; cG = 1; cB = 0; }

  pixels.clear();

  for (int i = 0; i < NUMPIXELS; i++) {
    int d = dist[i];
    int br = 0;

    // First pulse — full brightness.
    if (wave1 >= 0) {
      int diff = (d > wave1) ? d - wave1 : wave1 - d;
      if (diff < WAVE_W) {
        int b = (WAVE_W - diff) * BRIGHTNESS / WAVE_W;
        if (b > br) br = b;
      }
    }

    // Second pulse — slightly dimmer.
    if (wave2 >= 0) {
      int diff = (d > wave2) ? d - wave2 : wave2 - d;
      if (diff < WAVE_W) {
        int b = (WAVE_W - diff) * (BRIGHTNESS - 1) / WAVE_W;
        if (b > br) br = b;
      }
    }

    if (br > 0) {
      pixels.setPixelColor(i, pixels.Color(cR * br, cG * br, cB * br));
    }
  }

  ws2812_show(pixels);
}

// --- RPC handler ---
static void hmUpdate(MsgPack::arr_t<int> data) {
  if ((int)data.size() < 1) return;
  displayValue = data[0];
  if (displayValue < -99) displayValue = -99;
  if (displayValue >  99) displayValue =  99;
  hasData = true;
}

void setup() {
  precomputeDistances();
  pixels.begin();
  pixels.clear();
  ws2812_show(pixels);

  Bridge.begin();
  Bridge.provide("hm.u", hmUpdate);
}

void loop() {
  Bridge.update();

  unsigned long now = millis();
  if (hasData && (now - lastFrame >= FRAME_MS)) {
    lastFrame = now;
    renderFrame();
  }
}
