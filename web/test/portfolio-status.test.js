import assert from "node:assert/strict";
import test from "node:test";

const registry = new Map();
globalThis.customElements = {
  define: (name, constructor) => registry.set(name, constructor),
  get: (name) => registry.get(name),
};
globalThis.window = new EventTarget();

await import("../src/sentinel-portfolio-status.js");
const SentinelPortfolioStatus = registry.get("sentinel-portfolio-status");

test("recognizes simulated cash only while research mode is active", () => {
  const element = new SentinelPortfolioStatus();
  element.settings.value = {
    trading_mode: "research",
    simulated_cash_eur: 12_000,
  };

  assert.equal(element.cashIsSimulated, true);

  element.settings.value = {
    trading_mode: "live",
    simulated_cash_eur: 12_000,
  };

  assert.equal(element.cashIsSimulated, false);
});

test("allows whole-number cash from a fractional live balance", () => {
  const element = new SentinelPortfolioStatus();
  element.settings.value = {
    trading_mode: "research",
    simulated_cash_eur: null,
  };
  element.portfolio.value = { total_cash_eur: 16.80048168640208 };
  element.editingCash = true;
  element.cashDraft = "1000";

  const markup = element
    .renderCash(element.portfolio.value)
    .strings.join("");

  assert.match(markup, /step="any"/);
  assert.doesNotMatch(markup, /step="0\.01"/);
});

test("saves a finite simulated cash value and refreshes the portfolio", async (context) => {
  const element = new SentinelPortfolioStatus();
  element.settings.value = {
    trading_mode: "research",
    simulated_cash_eur: null,
  };
  element.cashDraft = "25000.50";
  let refreshed = false;
  element.portfolio.refresh = async () => {
    refreshed = true;
  };

  context.mock.method(globalThis, "fetch", async (path, options) => {
    assert.equal(path, "/api/settings/simulated_cash_eur");
    assert.equal(options.method, "PUT");
    assert.deepEqual(JSON.parse(options.body), { value: 25_000.5 });
    return Response.json({ status: "ok" });
  });

  await element.saveCash({ preventDefault() {} });

  assert.equal(element.settings.value.simulated_cash_eur, 25_000.5);
  assert.equal(refreshed, true);
  assert.equal(element.cashError, "");
  assert.equal(element.editingCash, false);
});

test("rejects non-finite cash without sending a request", async (context) => {
  const element = new SentinelPortfolioStatus();
  element.cashDraft = "Infinity";
  const fetchMock = context.mock.method(globalThis, "fetch", async () => {
    throw new Error("fetch should not be called");
  });

  await element.saveCash({ preventDefault() {} });

  assert.equal(fetchMock.mock.callCount(), 0);
  assert.equal(element.cashError, "Cash must be a finite number.");
});
