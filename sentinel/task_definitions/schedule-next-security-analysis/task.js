/**
 * Schedule Next Security Analysis
 *
 * Drives per-security coverage one step at a time. Each run asks pick-and-queue.mjs
 * to either (a) queue an analyze-security run for the security whose summary is most
 * overdue, or (b) once every summary is fresh, queue a rate-portfolio run if the
 * portfolio rating itself has fallen behind the summaries/universe. The decision
 * logic lives in the script; this orchestrator runs it and echoes its JSON result.
 */
const STEP_TIMEOUT_SECONDS = 3600;

const result = await run("pick-and-queue.mjs", { timeoutSeconds: STEP_TIMEOUT_SECONDS });
console.log(result.trim());
