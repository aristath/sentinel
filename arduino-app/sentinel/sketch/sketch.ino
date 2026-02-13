// NeoPixel Shield (5x8) drifting heatmap for Arduino UNO Q MCU, using Arduino_RouterBridge.
//
// Official transport:
// - arduino-router runs on the MPU and bridges MsgPack-RPC over Serial1.
// - Sketch polls the MPU by calling Bridge.call("heatmap/get") every 30s.
//
// Data:
// - The MPU returns [[before40],[after40]] where each list contains 40 floats (scores in [-0.5,+0.5]).
// - We render a constantly drifting heatmap driven by a moving center+end point.
// - Recommendations appear as a 2s pulse between before/after, strength based on abs(diff), auto-scaled.
//
// Pin:
// - NeoPixel data on D6 (per your wiring).

#define MSGPACK_MAX_ARRAY_SIZE 96
#define MSGPACK_MAX_OBJECT_SIZE 256

#include <Arduino_RouterBridge.h>
#include <Adafruit_NeoPixel.h>
#include <math.h>

#define PIN 6
#define W 5
#define H 8
#define NUMPIXELS (W * H)

// Keep very low, but non-zero-visible for typical indoor light.
// Once we confirm hardware visibility, we can tune this back down.
static const uint8_t BRIGHTNESS_CAP = 24;
static const uint32_t POLL_INTERVAL_MS = 30000;
static const float PULSE_PERIOD_S = 2.0f;

static const float DRIFT_SPEED = 0.10f;
static const float WARP_AMP = 0.55f;
static const float WARP_FREQ = 0.65f;

Adafruit_NeoPixel pixels(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);

static float before40[40];
static float after40[40];
static bool hasHeatmapData = false;

static uint32_t lastPollMs = 0;
static uint32_t lastFrameMs = 0;
static float tSec = 0.0f;

static float cx = 2.0f, cy = 3.5f;
static float ex = 4.0f, ey = 7.0f;
static float cdx = 0.31f, cdy = -0.17f;
static float edx = -0.23f, edy = 0.19f;

static int XY(int x, int y) {
  const bool serpentine = true;
  if (!serpentine) return y * W + x;
  if (y & 1) return y * W + (W - 1 - x);
  return y * W + x;
}

static float clampf(float v, float lo, float hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

static float absf(float v) {
  return (v < 0.0f) ? -v : v;
}

static uint8_t gamma8(uint8_t x) {
  // Avoid powf(). A simple gamma~2 curve is fine at our low brightness cap.
  uint16_t y = (uint16_t)x * (uint16_t)x; // 0..65025
  return (uint8_t)((y + 255) / 255);
}

static void hsv2rgb(float h, float s, float v, uint8_t &r, uint8_t &g, uint8_t &b) {
  // Avoid floorf()/fmodf() to keep the link simple on Zephyr.
  h = h - (int)h;
  if (h < 0.0f) h += 1.0f;
  float c = v * s;
  float hp = h * 6.0f;
  float hp_mod2 = hp;
  if (hp_mod2 >= 2.0f) hp_mod2 -= 2.0f * (int)(hp_mod2 / 2.0f); // since hp>=0
  float x = c * (1.0f - absf(hp_mod2 - 1.0f));
  float r1 = 0, g1 = 0, b1 = 0;
  if (hp < 1) { r1 = c; g1 = x; b1 = 0; }
  else if (hp < 2) { r1 = x; g1 = c; b1 = 0; }
  else if (hp < 3) { r1 = 0; g1 = c; b1 = x; }
  else if (hp < 4) { r1 = 0; g1 = x; b1 = c; }
  else if (hp < 5) { r1 = x; g1 = 0; b1 = c; }
  else { r1 = c; g1 = 0; b1 = x; }
  float m = v - c;
  r = (uint8_t)clampf((r1 + m) * 255.0f, 0.0f, 255.0f);
  g = (uint8_t)clampf((g1 + m) * 255.0f, 0.0f, 255.0f);
  b = (uint8_t)clampf((b1 + m) * 255.0f, 0.0f, 255.0f);
}

static void scoreToColor(float score, uint8_t &r, uint8_t &g, uint8_t &b) {
  score = clampf(score, -0.5f, 0.5f);
  float t = (score + 0.5f) / 1.0f;
  float hue = (t * 120.0f) / 360.0f; // red->green
  hsv2rgb(hue, 1.0f, 1.0f, r, g, b);
}

static void driftPoints(float dt) {
  cx += cdx * dt * DRIFT_SPEED * 10.0f;
  cy += cdy * dt * DRIFT_SPEED * 10.0f;
  ex += edx * dt * DRIFT_SPEED * 10.0f;
  ey += edy * dt * DRIFT_SPEED * 10.0f;

  if (cx < 0.0f) { cx = 0.0f; cdx = absf(cdx); }
  if (cx > (float)(W - 1)) { cx = (float)(W - 1); cdx = -absf(cdx); }
  if (cy < 0.0f) { cy = 0.0f; cdy = absf(cdy); }
  if (cy > (float)(H - 1)) { cy = (float)(H - 1); cdy = -absf(cdy); }

  if (ex < 0.0f) { ex = 0.0f; edx = absf(edx); }
  if (ex > (float)(W - 1)) { ex = (float)(W - 1); edx = -absf(edx); }
  if (ey < 0.0f) { ey = 0.0f; edy = absf(edy); }
  if (ey > (float)(H - 1)) { ey = (float)(H - 1); edy = -absf(edy); }

  cdx += 0.002f * sinf(tSec * 0.7f);
  cdy += 0.002f * cosf(tSec * 0.9f);
  edx += 0.002f * cosf(tSec * 0.8f);
  edy += 0.002f * sinf(tSec * 0.6f);
}

static void maybePoll() {
  uint32_t now = millis();
  if ((now - lastPollMs) < POLL_INTERVAL_MS) return;
  lastPollMs = now;

  MsgPack::arr_t<MsgPack::arr_t<float>> out;
  if (!Bridge.call("heatmap/get").result(out)) {
    return;
  }
  if (out.size() < 2) return;
  if (out[0].size() < 40 || out[1].size() < 40) return;

  for (int i = 0; i < 40; i++) {
    before40[i] = clampf(out[0][i], -0.5f, 0.5f);
    after40[i] = clampf(out[1][i], -0.5f, 0.5f);
  }
  hasHeatmapData = true;
}

static void renderStartupComet() {
  // If the shield is miswired / signal-level is wrong, everything will look "off".
  // This moving comet makes hardware visibility debugging unambiguous.
  pixels.setBrightness(BRIGHTNESS_CAP);
  const float speed = 6.0f; // pixels per second
  float head = tSec * speed;
  int headI = (int)head;
  for (int i = 0; i < NUMPIXELS; i++) {
    int d = headI - i;
    // Wrap distance into [-NUMPIXELS, NUMPIXELS]
    while (d > NUMPIXELS) d -= NUMPIXELS;
    while (d < -NUMPIXELS) d += NUMPIXELS;
    int ad = (d < 0) ? -d : d;
    // Exponential-ish tail without powf(): 1/(1+ad^2)
    float inv = 1.0f / (1.0f + (float)(ad * ad));
    uint8_t v = (uint8_t)clampf(inv * 255.0f, 0.0f, 255.0f);
    v = gamma8(v);
    // Cyan comet (still shows clearly even if G/R swapped).
    pixels.setPixelColor(i, pixels.Color(0, v, v));
  }
  pixels.show();
}

static void renderFrame() {
  if (!hasHeatmapData) {
    renderStartupComet();
    return;
  }

  float cycles = tSec / PULSE_PERIOD_S;
  float phase = cycles - (int)cycles; // 0..1 for tSec>=0
  float pulse = 0.5f + 0.5f * sinf(phase * 2.0f * (float)M_PI);

  float maxAbsDiff = 0.0f;
  for (int i = 0; i < 40; i++) {
    float d = absf(after40[i] - before40[i]);
    if (d > maxAbsDiff) maxAbsDiff = d;
  }
  if (maxAbsDiff < 0.001f) maxAbsDiff = 0.001f;

  float dx = ex - cx;
  float dy = ey - cy;
  float len = sqrtf(dx * dx + dy * dy);
  if (len < 0.001f) { dx = 1.0f; dy = 0.0f; len = 1.0f; }
  dx /= len;
  dy /= len;
  float px = -dy;
  float py = dx;

  float uMin = 1e9f, uMax = -1e9f;
  float uField[NUMPIXELS];

  for (int y = 0; y < H; y++) {
    for (int x = 0; x < W; x++) {
      float fx = (float)x;
      float fy = (float)y;
      float rx = fx - cx;
      float ry = fy - cy;
      float u = rx * dx + ry * dy;
      float v = rx * px + ry * py;
      u += WARP_AMP * sinf((v * WARP_FREQ) + tSec * 0.9f);
      u += 0.25f * sinf((u * 1.3f) + tSec * 0.6f);

      int p = XY(x, y);
      uField[p] = u;
      if (u < uMin) uMin = u;
      if (u > uMax) uMax = u;
    }
  }

  float denom = uMax - uMin;
  if (denom < 0.001f) denom = 0.001f;

  pixels.setBrightness(BRIGHTNESS_CAP);

  for (int y = 0; y < H; y++) {
    for (int x = 0; x < W; x++) {
      int p = XY(x, y);
      float uNorm = (uField[p] - uMin) / denom;
      int idx = (int)(uNorm * 40.0f);
      if (idx < 0) idx = 0;
      if (idx > 39) idx = 39;

      float diff = absf(after40[idx] - before40[idx]);
      float strength = clampf(diff / maxAbsDiff, 0.0f, 1.0f);
      float mix = strength * pulse;
      float s = after40[idx] * (1.0f - mix) + before40[idx] * mix;

      uint8_t r, g, b;
      scoreToColor(s, r, g, b);
      r = gamma8(r);
      g = gamma8(g);
      b = gamma8(b);
      pixels.setPixelColor(p, pixels.Color(r, g, b));
    }
  }

  pixels.show();
}

void setup() {
  pixels.begin();
  pixels.setBrightness(BRIGHTNESS_CAP);
  pixels.clear();
  pixels.show();

  for (int i = 0; i < 40; i++) { before40[i] = 0.0f; after40[i] = 0.0f; }

  Bridge.begin();

  lastPollMs = millis();
  lastFrameMs = millis();
}

void loop() {
  uint32_t now = millis();
  uint32_t dtMs = now - lastFrameMs;
  if (dtMs > 100) dtMs = 100;
  lastFrameMs = now;
  float dt = (float)dtMs / 1000.0f;
  tSec += dt;

  maybePoll();
  driftPoints(dt);
  renderFrame();
  delay(12);
}
