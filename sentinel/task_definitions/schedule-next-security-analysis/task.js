/**
 * Schedule Security Analyses
 *
 * Queues analyze-security for every missing, empty, or stale summary. The
 * decision logic lives in the script; this orchestrator echoes its JSON result.
 */
const STEP_TIMEOUT_SECONDS = 3600;

const result = await run("pick-and-queue.mjs", { timeoutSeconds: STEP_TIMEOUT_SECONDS });
console.log(result.trim());
