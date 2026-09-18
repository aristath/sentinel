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
 *   3. Generate 3-5 research queries from the profile.
 *   4. For each query (sequential): search, fetch+summarise sources, extract findings.
 *   5. Aggregate all findings and distill them into structural theses.
 *   6. finalize-security-report.py writes the report and stores one mem0 memory per
 *      finding.
 *   7. Pull macro context for the symbol, write the short 5-10 year summary, and save
 *      it as <symbol>.summary.md (consumed by the picker and rate-portfolio).
 *
 * Triggered by schedule-next-security-analysis (manual `symbol` input).
 */

// Resolve the security and prepare paths (+ any cached profile).
const resolved = JSON.parse(await run("resolve-security.py", { env: { SYMBOL: process.env.symbol || "" } }));
const item = resolved[0];
const itemJson = JSON.stringify(item);

// 2. Build the factual profile, but only when one isn't already cached.
if (!item.profileCacheHit) {
  const overview = await tool("searxng_web_search", {
    query: `What is ${item.name} 10-year strategy`,
    language: "all",
    pageno: 1,
  }, { timeoutSeconds: 120 });
  await run("fetch-profile-sources.py", { timeoutSeconds: 600, env: { SEARCH_TEXT: overview, ITEM_JSON: itemJson } });
  const profileSummaries = await run("load-profile-summaries.py", { env: { WORK_ROOT: item.workRoot } });
  const profile = await prompt("generate-profile.md", { timeoutSeconds: 600, context: { name: item.name, profileSummaries } });
  await run("save-generated-profile.py", { env: { PROFILE: profile, ITEM_JSON: itemJson } });
}

// 3. Load the profile and generate research queries from it.
const profileText = await run("load-profile.py", { env: { WORK_ROOT: item.workRoot } });
await prompt("generate-queries.md", { timeoutSeconds: 600, context: { name: item.name, profile: profileText, queriesPath: item.queriesPath } });
const queries = JSON.parse(await run("save-queries.py", { env: { QUERIES_PATH: item.queriesPath } }));

// 4. Research each query in turn (the original ran the loop at concurrency 1).
for (const query of queries) {
  const searchResults = await tool("searxng_web_search", {
    query,
    language: "all",
    time_range: "year",
    pageno: 1,
  }, { timeoutSeconds: 300 });
  const fetched = JSON.parse(await run("fetch-query-sources.py", { timeoutSeconds: 1500, env: { WORK_ROOT: item.workRoot, QUERY: query, SEARCH_TEXT: searchResults } }));
  const querySummaries = await run("load-query-source-summaries.py", { env: { SOURCE_SUMMARIES_PATH: fetched.sourceSummariesPath } });
  const findings = await prompt("extract-query-findings.md", { timeoutSeconds: 1500, context: { name: item.name, query, querySummaries } });
  await run("save-query-findings.py", { env: { FINDINGS: findings, FINDINGS_PATH: fetched.findingsPath } });
}

// 5. Aggregate all query findings and distill them into actionable theses.
const aggregated = await run("aggregate-query-findings.py", { env: { WORK_ROOT: item.workRoot } });
const distilled = await prompt("distill-security-findings.md", { timeoutSeconds: 900, context: { name: item.name, profile: profileText, rawFindings: aggregated } });

// 6. Write the canonical report and persist findings to mem0.
await run("finalize-security-report.py", { timeoutSeconds: 300, env: { ITEM_JSON: itemJson, DISTILL_OUTPUT: distilled, PROFILE: profileText } });

// 7. Pull macro context, write the short structural summary, and save it.
const macro = JSON.parse(await run("resolve-macro-context.py", { env: { ITEM_JSON: itemJson, DISTILL_OUTPUT: distilled } }));
const summary = await prompt("write-security-summary.md", {
  timeoutSeconds: 300,
  context: { name: macro.name, symbol: macro.symbol, industry: macro.industry, geography: macro.geography, distilledFindings: macro.distilledFindings, macroContextPrompt: macro.macroContextPrompt },
});
const result = await run("save-security-summary.py", { env: { ITEM_JSON: itemJson, SUMMARY: summary } });
console.log(result.trim());
