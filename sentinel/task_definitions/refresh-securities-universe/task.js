/**
 * Refresh Securities Universe
 *
 * Rebuilds the securities-universe snapshot from the co-located Sentinel service by
 * running write-universe.py, then echoes the script's JSON summary into the run
 * record. This snapshot is the root input for security scheduling and the
 * analyze/rate pipeline.
 */
const STEP_TIMEOUT_SECONDS = 3600;

const result = await run("write-universe.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS });
console.log(result.trim());
