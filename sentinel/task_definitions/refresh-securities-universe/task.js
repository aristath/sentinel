/**
 * Refresh Securities Universe
 *
 * Rebuilds the securities-universe snapshot from the co-located Sentinel service by
 * running write-universe.py, then echoes the script's JSON summary into the run
 * record. This snapshot is the root input for security scheduling and the
 * analyze/rate pipeline.
 */
const result = await run("write-universe.py");
console.log(result.trim());
