/**
 * Schedule Rate Portfolio
 *
 * Checks the portfolio result and its security-summary dependencies, then
 * queues either every stale security or one rate-portfolio run.
 */
const STEP_TIMEOUT_SECONDS = 3600;

const result = await run("check-and-queue.mjs", { timeoutSeconds: STEP_TIMEOUT_SECONDS });
console.log(result.trim());
