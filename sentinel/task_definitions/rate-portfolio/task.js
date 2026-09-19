/**
 * Rate Portfolio
 *
 * Rates every security in the universe relative to the others for a 5-10 year
 * allocation, then submits those ratings to Sentinel. Flow:
 *
 *   1. compile-summaries.py gathers all per-security summaries into one document
 *      and reports the expected symbols and output paths.
 *   2. The rater (an LLM prompt) writes a candidate ratings JSON; validate-ratings.mjs
 *      checks and repairs it. This repeats up to 3 times, feeding the validator's
 *      errors back into each retry, until the output validates.
 *   3. prepare-ratings.py gate-checks the validated result and submit-ratings.py
 *      POSTs each rating to Sentinel, persisting latest.json on full success.
 */

const STEP_TIMEOUT_SECONDS = 3600;

// 1. Compile all per-security summaries into a single document for the rater.
const compiled = JSON.parse(await run("compile-summaries.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS }));

// 2. Rate, then validate/repair; retry up to 3 times, feeding errors back each round.
let validation;
let validationFeedback = "";
for (let attempt = 0; attempt < 3; attempt++) {
  // The rater reads every summary and writes its ratings JSON to ratingsRawPath
  // via the write_file tool.
  await prompt("rate-all.md", {
    timeoutSeconds: STEP_TIMEOUT_SECONDS,
    context: {
      compiledText: compiled.compiledText,
      count: compiled.count,
      ratingsRawPath: compiled.ratingsRawPath,
      validationFeedback,
    },
  });

  // Validate + repair the candidate. On success the canonical ratings file is written.
  const rawValidation = await run("validate-ratings.mjs", {
    timeoutSeconds: STEP_TIMEOUT_SECONDS,
    env: {
      EXPECTED_SYMBOLS: JSON.stringify(compiled.expectedSymbols),
      RATINGS_RAW_PATH: compiled.ratingsRawPath,
      RATINGS_PATH: compiled.ratingsPath,
    },
  });
  validation = JSON.parse(rawValidation);
  if (validation.ok) break;
  // Hand the full validator output to the next attempt so it can fix the exact issues.
  validationFeedback = rawValidation;
}
if (!validation?.ok) {
  throw new Error("Portfolio ratings did not validate after 3 attempts: " + JSON.stringify(validation?.errors ?? []));
}

// 3. Gate-check the validated ratings, then submit them to Sentinel.
const prepared = await run("prepare-ratings.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { VALIDATION_JSON: JSON.stringify(validation) } });
const result = await run("submit-ratings.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { RATINGS_JSON: prepared } });
console.log(result.trim());
