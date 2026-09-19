/**
 * Queue analysis for every security whose summary is missing, empty, or at
 * least seven days old. Requests are split into scheduler-sized batches and
 * use per-symbol dedupe keys so overlapping checks cannot pile up duplicates.
 */
import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const dataDir = process.env.SENTINEL_TASKS_HOME;
if (!dataDir) throw new Error("SENTINEL_TASKS_HOME is required");
const base = process.env.SENTINEL_BASE_URL || "http://127.0.0.1:8000";
const universePath = join(dataDir, "tasks/artifacts/refresh-securities-universe/securities-universe.json");
const outputDir = join(dataDir, "tasks/artifacts/analyze-security");
const staleMs = 7 * 24 * 60 * 60 * 1000;
const now = Date.now();

const slug = (value) => String(value || "item").replace(/[^A-Za-z0-9_.-]+/g, "-").replace(/^-+|-+$/g, "") || "item";
const usableSummaryMtimeMs = (path) => {
  try {
    if (!readFileSync(path, "utf8").trim()) return 0;
    return statSync(path).mtimeMs;
  } catch {
    return 0;
  }
};

const universe = JSON.parse(readFileSync(universePath, "utf8"));
if (!Array.isArray(universe)) throw new Error("securities-universe.json must contain an array");

const stale = universe
  .filter((item) => item && typeof item.symbol === "string" && item.symbol.trim())
  .map((item) => {
    const symbol = item.symbol.trim();
    const mtimeMs = usableSummaryMtimeMs(join(outputDir, `${slug(symbol)}.summary.md`));
    return { symbol, mtimeMs, ageMs: mtimeMs ? now - mtimeMs : Infinity };
  })
  .filter((item) => item.ageMs >= staleMs)
  .sort((a, b) => a.mtimeMs - b.mtimeMs || a.symbol.localeCompare(b.symbol));

if (!stale.length) {
  console.log(JSON.stringify({ queued: false, reason: "all security summaries fresh" }));
  process.exit(0);
}

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
