import assert from "node:assert/strict";
import test from "node:test";

const registry = new Map();
globalThis.customElements = {
  define: (name, constructor) => registry.set(name, constructor),
  get: (name) => registry.get(name),
};
await import("../src/sentinel-planner-status.js");
const SentinelPlannerStatus = registry.get("sentinel-planner-status");

const recommendation = (action, marketOpen) => ({
  symbol: action === "sell" ? "ATHEX" : "HKEX",
  action,
  market_open: marketOpen,
  value_delta_eur: action === "sell" ? -500 : 500,
  current_value_eur: 1000,
  reason: "Portfolio rebalance",
});

test("open-market sales use red and purchases use green", () => {
  const element = new SentinelPlannerStatus();
  const sale = element.renderRecommendation(recommendation("sell", true), 0);
  const buy = element.renderRecommendation(recommendation("buy", true), 1);

  assert.equal(sale.values[1], "error");
  assert.equal(buy.values[1], "success");
  assert.equal(sale.values[0], "");
  assert.equal(buy.values[0], "");
});

test("closed-market sales and purchases use grey and explain the wait", () => {
  const element = new SentinelPlannerStatus();
  for (const action of ["sell", "buy"]) {
    const result = element.renderRecommendation(recommendation(action, false), 0);
    assert.equal(result.values[1], "default");
    assert.equal(result.values[0], "--tui-color: var(--tui-disabled-color)");
    assert.equal(result.values[2], "Waiting for market to open · Portfolio rebalance");
    assert.ok(result.values.includes(action.toUpperCase()));
  }
});

test("market updates change colors while retaining every trade in the current plan", () => {
  const element = new SentinelPlannerStatus();
  const planner = {
    recommendations: [recommendation("sell", false), recommendation("buy", true)],
    summary: { valid_for_minutes: 20 },
  };

  const before = element.renderPlanner(planner);
  assert.match(before.strings.join(""), /Current plan:/);
  assert.doesNotMatch(before.strings.join(""), /Next.*min|Trades:/);
  const beforeTrades = before.values.find(Array.isArray);
  assert.equal(beforeTrades.length, 2);
  assert.equal(beforeTrades[0].values[1], "default");
  assert.equal(beforeTrades[1].values[1], "success");

  planner.recommendations[0].market_open = true;
  planner.recommendations[1].market_open = false;
  const after = element.renderPlanner(planner);
  const afterTrades = after.values.find(Array.isArray);
  assert.equal(afterTrades.length, 2);
  assert.equal(afterTrades[0].values[1], "error");
  assert.equal(afterTrades[1].values[1], "default");
});
