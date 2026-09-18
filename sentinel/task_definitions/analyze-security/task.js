/**
 * Analyze Security
 *
 * Researches one security (manual `symbol` input) for a 5-10 year horizon, writes a
 * report + a short summary, and persists findings to mem0. Flow:
 *
 *   1. resolve-security.py resolves the symbol, seeds a cached profile from prior
 *      artifacts if available, and prepares the scratch paths.
 *   2. Profile (only if not cached): search for the security's 10-year strategy, fetch+summarise
 *      sources, generate a factual profile, and save it.
 *   3. Generate security-specific and external-context research queries from the profile.
 *   4. Research each query through bounded search/fetch/extract steps. External-context
 *      searches always use the latest month; the LLM does not choose the time range.
 *   5. Distill the two research branches independently.
 *   6. Write the report and per-security external-context artifact, then store findings.
 *   7. Write <symbol>.summary.md from the two distilled briefs.
 *
 * Triggered by schedule-next-security-analysis (manual `symbol` input).
 */

const STEP_TIMEOUT_SECONDS = 3600;

// Resolve the security and prepare paths (+ any cached profile).
const resolved = JSON.parse(await run("resolve-security.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { SYMBOL: process.env.symbol || "" } }));
const item = resolved[0];
const itemJson = JSON.stringify(item);

// 2. Build the factual profile, but only when one isn't already cached.
if (!item.profileCacheHit) {
  const overview = await tool("searxng_web_search", {
    query: `strategy of ${item.name} for the next 10 years`,
    language: "all",
    pageno: 1,
  }, { timeoutSeconds: STEP_TIMEOUT_SECONDS });
  await run("fetch-profile-sources.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { SEARCH_TEXT: overview, ITEM_JSON: itemJson } });
  const profileSummaries = await run("load-profile-summaries.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { WORK_ROOT: item.workRoot } });
  const profile = await prompt("generate-profile.md", { timeoutSeconds: STEP_TIMEOUT_SECONDS, context: { name: item.name, profileSummaries } });
  await run("save-generated-profile.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { PROFILE: profile, ITEM_JSON: itemJson } });
}

// 3. Load the profile and generate the two bounded query sets from it.
const profileText = await run("load-profile.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { WORK_ROOT: item.workRoot } });
await prompt("generate-queries.md", { timeoutSeconds: STEP_TIMEOUT_SECONDS, context: { name: item.name, profile: profileText, queriesPath: item.queriesPath } });
const queries = JSON.parse(await run("save-queries.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { QUERIES_PATH: item.queriesPath } }));
const rawContextQueries = await prompt("generate-context-queries.md", {
  timeoutSeconds: STEP_TIMEOUT_SECONDS,
  outputType: "json",
  useTools: false,
  context: { name: item.name, profile: profileText },
});
const contextQueries = JSON.parse(await run("validate-context-queries.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { QUERIES_JSON: rawContextQueries } }));

// 4. Research each query in turn (the original ran the loop at concurrency 1).
for (const query of queries) {
  const searchResults = await tool("searxng_web_search", {
    query,
    language: "all",
    time_range: "year",
    pageno: 1,
  }, { timeoutSeconds: STEP_TIMEOUT_SECONDS });
  const fetched = JSON.parse(await run("fetch-query-sources.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { WORK_ROOT: item.workRoot, QUERY: query, SEARCH_TEXT: searchResults } }));
  const querySummaries = await run("load-query-source-summaries.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { SOURCE_SUMMARIES_PATH: fetched.sourceSummariesPath } });
  const findings = await prompt("extract-query-findings.md", { timeoutSeconds: STEP_TIMEOUT_SECONDS, context: { name: item.name, query, querySummaries } });
  await run("save-query-findings.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { FINDINGS: findings, FINDINGS_PATH: fetched.findingsPath } });
}

// 5. Research current external context with the same bounded per-query pipeline.
for (const query of contextQueries) {
  const searchResults = await tool("searxng_web_search", {
    query,
    language: "all",
    time_range: "month",
    pageno: 1,
  }, { timeoutSeconds: STEP_TIMEOUT_SECONDS });
  const fetched = JSON.parse(await run("fetch-query-sources.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { WORK_ROOT: item.contextRoot, QUERY: query, SEARCH_TEXT: searchResults } }));
  const querySummaries = await run("load-query-source-summaries.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { SOURCE_SUMMARIES_PATH: fetched.sourceSummariesPath } });
  const findings = await prompt("extract-context-findings.md", {
    timeoutSeconds: STEP_TIMEOUT_SECONDS,
    useTools: false,
    context: { name: item.name, query, querySummaries },
  });
  await run("save-query-findings.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { FINDINGS: findings, FINDINGS_PATH: fetched.findingsPath } });
}

// 6. Distill both branches independently so later prompts receive compact inputs.
const aggregated = await run("aggregate-query-findings.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { WORK_ROOT: item.workRoot } });
const distilled = await prompt("distill-security-findings.md", { timeoutSeconds: STEP_TIMEOUT_SECONDS, context: { name: item.name, profile: profileText, rawFindings: aggregated } });
const contextAggregated = await run("aggregate-query-findings.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { WORK_ROOT: item.contextRoot } });
const contextDistilled = await prompt("distill-context-findings.md", {
  timeoutSeconds: STEP_TIMEOUT_SECONDS,
  useTools: false,
  context: { name: item.name, rawFindings: contextAggregated },
});
await run("save-context-report.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { ITEM_JSON: itemJson, CONTEXT_OUTPUT: contextDistilled } });

// 7. Write the canonical report and persist both kinds of findings to mem0.
await run("finalize-security-report.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { ITEM_JSON: itemJson, DISTILL_OUTPUT: distilled, CONTEXT_OUTPUT: contextDistilled, PROFILE: profileText } });

// 8. Write the short structural summary from the two distilled briefs.
const summary = await prompt("write-security-summary.md", {
  timeoutSeconds: STEP_TIMEOUT_SECONDS,
  useTools: false,
  context: { name: item.name, symbol: item.symbol, distilledFindings: distilled, externalContext: contextDistilled },
});
const result = await run("save-security-summary.py", { timeoutSeconds: STEP_TIMEOUT_SECONDS, env: { ITEM_JSON: itemJson, SUMMARY: summary } });
console.log(result.trim());
