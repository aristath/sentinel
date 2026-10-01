import assert from "node:assert/strict";
import test from "node:test";

const registry = new Map();
globalThis.customElements = {
  define: (name, constructor) => registry.set(name, constructor),
  get: (name) => registry.get(name),
};
await import("../src/sentinel-securities.js");
const SentinelSecurities = registry.get("sentinel-securities");
const settingKey = "ui_securities_table_columns";

test("shows new columns for a legacy selection without restoring hidden columns", () => {
  const element = new SentinelSecurities();
  element.columnSettings.value = {
    [settingKey]: ["security", "value", "pnl", "ideal", "trade"],
  };

  assert.equal(element.columnVisible("deviation"), true);
  assert.equal(element.columnVisible("price"), false);
  assert.equal(element.columnVisible("plan"), false);
  assert.equal(element.columnVisible("ai_score"), true);
  assert.equal(element.columnVisible("opportunity_score"), true);
  assert.equal(element.selectedColumns.size, 8);
});

test("supports explicitly hiding new columns while keeping security visible", () => {
  const element = new SentinelSecurities();
  element.columnSettings.value = {
    [settingKey]: { hidden: ["deviation", "ai_score", "opportunity_score", "price", "security"] },
  };

  assert.equal(element.columnVisible("deviation"), false);
  assert.equal(element.columnVisible("ai_score"), false);
  assert.equal(element.columnVisible("opportunity_score"), false);
  assert.equal(element.columnVisible("price"), false);
  assert.equal(element.columnVisible("security"), true);
  assert.equal(element.columnVisible("plan"), true);
});

test("saves a hidden deviation and restores it after creating a new table", async (context) => {
  const element = new SentinelSecurities();
  element.columnSettings.value = {
    [settingKey]: ["security", "value", "pnl", "ideal", "trade"],
  };
  let saved;
  context.mock.method(globalThis, "fetch", async (path, options) => {
    assert.equal(path, `/api/settings/${settingKey}`);
    assert.equal(options.method, "PUT");
    saved = JSON.parse(options.body).value;
    return Response.json({ status: "ok" });
  });

  await element.toggleColumn({ currentTarget: { checked: false } }, "deviation");
  assert.equal(element.columnVisible("deviation"), false);
  const restored = new SentinelSecurities();
  restored.columnSettings.value = { [settingKey]: saved };
  assert.equal(restored.columnVisible("deviation"), false);
  assert.equal(restored.columnVisible("price"), false);
  assert.equal(restored.columnVisible("plan"), false);
  assert.equal(restored.columnVisible("trade"), true);

  await restored.toggleColumn({ currentTarget: { checked: true } }, "deviation");
  const shown = new SentinelSecurities();
  shown.columnSettings.value = { [settingKey]: saved };
  assert.equal(shown.columnVisible("deviation"), true);
  assert.equal(shown.columnVisible("price"), false);
  assert.equal(shown.columnVisible("plan"), false);
});

test("restores the previous selection when saving a column choice fails", async (context) => {
  const element = new SentinelSecurities();
  element.columnSettings.value = {
    [settingKey]: ["security", "value", "pnl", "ideal", "trade"],
  };
  context.mock.method(globalThis, "fetch", async () =>
    Response.json({ detail: "Save failed" }, { status: 500 }),
  );

  await element.toggleColumn({ currentTarget: { checked: false } }, "deviation");
  assert.equal(element.columnVisible("deviation"), true);
  assert.equal(element.columnVisible("price"), false);
  assert.equal(element.columnVisible("plan"), false);
  assert.equal(element.errorMessage, "Save failed");
  assert.equal(element.columnsBusy, false);
});

test("sorts deviation numerically using current holdings before planned trades", () => {
  const element = new SentinelSecurities();
  element.securities.value = [
    { symbol: "OVER", current_allocation: 12, ideal_allocation: 10, post_plan_allocation: 5 },
    { symbol: "UNDER", current_allocation: 8, ideal_allocation: 10, post_plan_allocation: 15 },
    { symbol: "NONE", current_allocation: 0, ideal_allocation: 5, post_plan_allocation: 5 },
    { symbol: "EXACT", current_allocation: 10, ideal_allocation: 10, post_plan_allocation: 10 },
    { symbol: "NO_IDEAL", current_allocation: 3, ideal_allocation: 0, post_plan_allocation: 0 },
  ];
  element.changeSort("deviation");
  assert.deepEqual(element.visibleSecurities.map((security) => security.symbol),
    ["NONE", "UNDER", "EXACT", "OVER", "NO_IDEAL"]);
  element.changeSort("deviation");
  assert.deepEqual(element.visibleSecurities.map((security) => security.symbol),
    ["NO_IDEAL", "OVER", "EXACT", "UNDER", "NONE"]);
});
