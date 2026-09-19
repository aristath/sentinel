/**
 * Picks the next unit of securities work and enqueues it, in priority order:
 *
 *   1. If any security's analysis summary is missing or older than seven days,
 *      queue analyze-security for the single most-overdue one (oldest/absent
 *      first, ties broken by symbol for determinism).
 *   2. Otherwise, if every summary is fresh AND the portfolio rating is older
 *      than the newest summary or the universe snapshot, queue one rate-portfolio
 *      run (deduped so concurrent ticks don't pile up duplicates).
 *   3. Otherwise do nothing.
 *
 * Run on a short idle cadence, each invocation advances at most one unit of work,
 * so the whole universe is analysed and then rated gradually and in order.
 *
 * Environment:
 *   SENTINEL_TASKS_HOME  (required) - Sentinel's task data root; the universe snapshot, the
 *                                per-security summaries, and the portfolio rating
 *                                all live beneath it.
 *   SENTINEL_BASE_URL  (optional) - base URL of the local Sentinel API
 *                                (defaults to http://127.0.0.1:8000).
 *
 * Prints one JSON line describing the decision (queued analyze-security, triggered
 * rate-portfolio, or a "queued:false" no-op with the reason).
 */
import { mkdirSync, statSync, readFileSync } from "node:fs";
import { join } from "node:path";

const dataDir = process.env.SENTINEL_TASKS_HOME;
if (!dataDir) throw new Error("SENTINEL_TASKS_HOME is required");
const base = process.env.SENTINEL_BASE_URL || "http://127.0.0.1:8000";

// Input universe, the directory of per-security analysis artifacts, and the
// portfolio rating file that step 2 compares freshness against.
const universePath = join(dataDir, "tasks/artifacts/refresh-securities-universe/securities-universe.json");
const outputDir = join(dataDir, "tasks/artifacts/analyze-security");
const portfolioRatingPath = join(dataDir, "tasks/artifacts/rate-portfolio/latest.json");

// A summary is stale once it is older than seven days.
const staleMs = 7 * 24 * 60 * 60 * 1000;
const now = Date.now();

// Filesystem-safe filename stem derived from a symbol (unsafe chars collapsed).
const slug = (value) => String(value || "item").replace(/[^A-Za-z0-9_.-]+/g, "-").replace(/^-+|-+$/g, "") || "item";

const usableSummaryMtimeMs = (path) => {
  try {
    if (!readFileSync(path, "utf8").trim()) return 0;
    return statSync(path).mtimeMs;
  } catch {
    return 0;
  }
};

mkdirSync(outputDir, { recursive: true });

const universe = JSON.parse(readFileSync(universePath, "utf8"));
if (!Array.isArray(universe)) throw new Error("securities-universe.json must contain an array");

// Step 1: find securities whose *summary* file (not the full report — that's what
// rate-portfolio consumes) is missing or stale. Missing files sort first (Infinity age).
const candidates = universe
  .filter((item) => item && typeof item.symbol === "string" && item.symbol.trim())
  .map((item) => {
    const symbol = item.symbol.trim();
    const path = join(outputDir, `${slug(symbol)}.summary.md`);
    const mtimeMs = usableSummaryMtimeMs(path);
    return {
      symbol,
      name: typeof item.name === "string" ? item.name : "",
      path,
      mtimeMs,
      ageMs: mtimeMs ? now - mtimeMs : Infinity,
    };
  })
  .filter((item) => item.ageMs >= staleMs);

candidates.sort((a, b) => a.mtimeMs - b.mtimeMs || a.symbol.localeCompare(b.symbol));
const selected = candidates[0];

// Step 2: nothing stale. If every summary exists and is fresh, consider whether the
// portfolio rating needs refreshing relative to the newest summary / universe file.
if (!selected) {
  const universeMtimeMs = statSync(universePath).mtimeMs;
  let newestSummaryMtimeMs = 0;
  const allFresh = universe.every((item) => {
    const symbol = (typeof item.symbol === "string" ? item.symbol : "").trim();
    if (!symbol) return true;
    const path = join(outputDir, `${slug(symbol)}.summary.md`);
    const mtimeMs = usableSummaryMtimeMs(path);
    newestSummaryMtimeMs = Math.max(newestSummaryMtimeMs, mtimeMs);
    return mtimeMs > 0 && now - mtimeMs < staleMs;
  });

  if (allFresh) {
    // The portfolio rating must be at least as new as the newest summary and the
    // universe snapshot; if it already is, there's nothing to do.
    let portfolioMtimeMs = 0;
    try { portfolioMtimeMs = statSync(portfolioRatingPath).mtimeMs; } catch {}
    const requiredPortfolioMtimeMs = Math.max(newestSummaryMtimeMs, universeMtimeMs);

    if (portfolioMtimeMs >= requiredPortfolioMtimeMs) {
      console.log(JSON.stringify({
        queued: false,
        reason: "portfolio rating already current",
        portfolioMtimeMs,
        newestSummaryMtimeMs,
        universeMtimeMs,
      }));
      process.exit(0);
    }

    // Portfolio rating is behind — queue one rate-portfolio run. The dedupeKey keeps
    // overlapping idle ticks from enqueuing duplicate portfolio ratings.
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
      queued: false,
      reason: "all summaries fresh",
      triggeredPortfolioRating: true,
      workItemId: result.item?.id ?? null,
      portfolioMtimeMs: portfolioMtimeMs || null,
      newestSummaryMtimeMs,
      universeMtimeMs,
    }));
  } else {
    // Some summaries are still being produced (present but not all fresh, or some
    // missing on this pass) — wait for a later tick rather than rating early.
    console.log(JSON.stringify({ queued: false, reason: "no stale securities, not all fresh yet" }));
  }
  process.exit(0);
}

// Step 1 result: queue analysis for the most-overdue security.
const queueResponse = await fetch(`${base}/api/scheduler`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({
    task: "analyze-security",
    inputs: { symbol: selected.symbol },
  }),
});

if (!queueResponse.ok) {
  const text = await queueResponse.text();
  throw new Error(`Queue request failed: HTTP ${queueResponse.status} ${text}`);
}
const queueResult = await queueResponse.json();

console.log(JSON.stringify({
  queued: true,
  taskId: "analyze-security",
  workItemId: queueResult.item?.id ?? null,
  symbol: selected.symbol,
  name: selected.name,
  previousMtimeMs: selected.mtimeMs || null,
  remainingStale: candidates.length - 1,
}));
