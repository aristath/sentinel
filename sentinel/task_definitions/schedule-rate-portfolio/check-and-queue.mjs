/**
 * Apply the portfolio-rating schedule rules in order:
 *
 *   1. If the canonical portfolio result is under five days old, do nothing.
 *   2. Otherwise, queue analysis for every missing, empty, or seven-day-old
 *      security summary and stop.
 *   3. If every summary is fresh, queue rate-portfolio.
 */
import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const dataDir = process.env.SENTINEL_TASKS_HOME;
if (!dataDir) throw new Error("SENTINEL_TASKS_HOME is required");
const base = process.env.SENTINEL_BASE_URL || "http://127.0.0.1:8000";
const artifacts = join(dataDir, "tasks/artifacts");
const universePath = join(artifacts, "refresh-securities-universe/securities-universe.json");
const summaryDir = join(artifacts, "analyze-security");
const portfolioPath = join(artifacts, "rate-portfolio/latest.json");
const summaryStaleMs = 7 * 24 * 60 * 60 * 1000;
const portfolioStaleMs = 5 * 24 * 60 * 60 * 1000;
const now = Date.now();

const slug = (value) => String(value || "item").replace(/[^A-Za-z0-9_.-]+/g, "-").replace(/^-+|-+$/g, "") || "item";
const usableMtimeMs = (path) => {
  try {
    if (!readFileSync(path, "utf8").trim()) return 0;
    return statSync(path).mtimeMs;
  } catch {
    return 0;
  }
};

const portfolioMtimeMs = usableMtimeMs(portfolioPath);
if (portfolioMtimeMs > 0 && now - portfolioMtimeMs < portfolioStaleMs) {
  console.log(JSON.stringify({
    queued: false,
    reason: "portfolio rating is under five days old",
    portfolioMtimeMs,
    portfolioAgeMs: now - portfolioMtimeMs,
  }));
  process.exit(0);
}

const universe = JSON.parse(readFileSync(universePath, "utf8"));
if (!Array.isArray(universe)) throw new Error("securities-universe.json must contain an array");
const securities = universe
  .filter((item) => item && typeof item.symbol === "string" && item.symbol.trim())
  .map((item) => {
    const symbol = item.symbol.trim();
    const mtimeMs = usableMtimeMs(join(summaryDir, `${slug(symbol)}.summary.md`));
    return { symbol, mtimeMs, ageMs: mtimeMs ? now - mtimeMs : Infinity };
  });
if (!securities.length) throw new Error("The securities universe contains no securities");

const stale = securities
  .filter((item) => item.ageMs >= summaryStaleMs)
  .sort((a, b) => a.mtimeMs - b.mtimeMs || a.symbol.localeCompare(b.symbol));
if (stale.length) {
  const workItemIds = [];
  for (let offset = 0; offset < stale.length; offset += 500) {
    const batch = stale.slice(offset, offset + 500).map((item) => ({
      task: "analyze-security",
      inputs: { symbol: item.symbol },
      dedupeKey: `analyze-security:${item.symbol}:stale`,
    }));
    const response = await fetch(`${base}/api/scheduler`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(batch),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Queue stale security analysis failed: HTTP ${response.status} ${text}`);
    }
    const result = await response.json();
    workItemIds.push(...(result.items ?? [result.item]).filter(Boolean).map((item) => item.id));
  }
  console.log(JSON.stringify({
    queued: true,
    taskId: "analyze-security",
    staleSymbols: stale.map((item) => item.symbol),
    workItemIds,
  }));
  process.exit(0);
}

const response = await fetch(`${base}/api/scheduler`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({
    task: "rate-portfolio",
    inputs: {},
    dedupeKey: "rate-portfolio:current",
  }),
});
if (!response.ok) {
  const text = await response.text();
  throw new Error(`Queue rate-portfolio failed: HTTP ${response.status} ${text}`);
}
const result = await response.json();
console.log(JSON.stringify({
  queued: true,
  taskId: "rate-portfolio",
  workItemId: result.item?.id ?? null,
  portfolioMtimeMs: portfolioMtimeMs || null,
  portfolioAgeMs: portfolioMtimeMs ? now - portfolioMtimeMs : null,
}));
