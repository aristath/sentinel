/**
 * Rate Security
 *
 * Produces a long-term (5-10 year) structural rating for one security and posts it
 * to Sentinel. Takes a manual `symbol` input. Flow:
 *
 *   1. resolve-rating-context.py locates the symbol and prepares every working path.
 *   2. compose-evidence-pack.py assembles a 6-month window of per-security mem0
 *      research; load-evidence-pack.py reads it back.
 *   3. The analysis prompt writes a structured bull/bear/verdict analysis.
 *   4. The rating prompt emits a {symbol, rating, rationale} JSON; validate-rating.mjs
 *      checks/repairs it. Repeat up to 5 times, feeding validator feedback back, until valid.
 *   5. submit-rating.mjs POSTs the canonical rating to Sentinel.
 *
 * Triggered by schedule-next-security-analysis with a `symbol` input.
 */

const STEP_TIMEOUT_SECONDS = 3600;

// Resolve the rating context for the requested symbol.
const ctx = JSON.parse(await run("resolve-rating-context.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { SYMBOL: process.env.symbol || "" } }));
const ctxJson = JSON.stringify(ctx);

// 1. Compose the evidence pack, then load it for the analysis prompt.
await run("compose-evidence-pack.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { CONTEXT_JSON: ctxJson } });
const evidencePack = await run("load-evidence-pack.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { CONTEXT_JSON: ctxJson } });

// 2. Write the long-term structural analysis, then load it back for the rating prompt.
await prompt("write-analysis.md", {
  timeoutSeconds: STEP_TIMEOUT_SECONDS,
  context: { symbol: ctx.symbol, name: ctx.name, analysisPath: ctx.analysisPath, evidencePack },
});
const analysis = await run("load-analysis.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { CONTEXT_JSON: ctxJson } });

// 3. Produce the rating, validating/repairing each attempt; retry up to 5 times.
let validation;
let validatorFeedback = "";
for (let attempt = 0; attempt < 5; attempt++) {
  await prompt("write-rating-raw-json.md", {
    timeoutSeconds: STEP_TIMEOUT_SECONDS,
    context: { symbol: ctx.symbol, name: ctx.name, ratingRawPath: ctx.ratingRawPath, analysis, validatorFeedback },
  });
  const rawValidation = await run("validate-rating.mjs", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { CONTEXT_JSON: ctxJson } });
  validation = JSON.parse(rawValidation);
  if (validation.valid) break;
  validatorFeedback = rawValidation;
}
if (!validation?.valid) {
  throw new Error("Security rating did not validate after 5 attempts: " + (validation?.error ?? "unknown"));
}

// 4. Submit the canonical rating to Sentinel.
const result = await run("submit-rating.mjs", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { RATING_JSON: JSON.stringify(validation.canonical) } });
console.log(result.trim());
