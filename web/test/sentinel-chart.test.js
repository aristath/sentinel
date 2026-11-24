import assert from "node:assert/strict";
import test from "node:test";

const registry = new Map();
globalThis.customElements = {
  define(name, constructor) {
    void constructor.observedAttributes;
    registry.set(name, constructor);
  },
  get: (name) => registry.get(name),
};
await import("../src/sentinel-chart.js");
const SentinelChart = registry.get("sentinel-chart");

test("replacing chart values requests a redraw with the same scale", () => {
  const chart = new SentinelChart();
  chart.min = 0;
  chart.max = 10;
  const originalValues = [2, 4, 6];
  chart.values = originalValues;

  const updates = [];
  chart.requestUpdate = (property, previousValue) => {
    updates.push([property, previousValue]);
  };
  chart.values = [4, 6];

  assert.deepEqual(updates, [["values", originalValues]]);
});
