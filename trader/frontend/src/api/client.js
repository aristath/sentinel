/**
 * Centralized API client for Sentinel
 */

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!res.ok) {
    let errorMessage = `Request failed with status ${res.status}`;
    try {
      const errorData = await res.json();
      errorMessage = errorData.detail || errorData.message || errorData.error || errorMessage;
    } catch (e) {
      errorMessage = res.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return res.json();
}

export const api = {
  // Base methods
  get: (url) => fetchJSON(url),
  post: (url, data) => fetchJSON(url, {
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
  }),
  put: (url, data) => fetchJSON(url, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  delete: (url) => fetchJSON(url, { method: 'DELETE' }),

  // Status
  fetchStatus: () => fetchJSON('/api/system/status'),
  fetchTradernet: () => fetchJSON('/api/system/tradernet'),
  syncPrices: () => fetchJSON('/api/system/sync/prices', { method: 'POST' }),
  syncHistorical: () => fetchJSON('/api/system/sync/historical', { method: 'POST' }),

  // Logs
  fetchLogs: (logFile = 'sentinel.log', lines = 100, level = null, search = null) => {
    const params = new URLSearchParams({ log_file: logFile, lines: lines.toString() });
    if (level) params.append('level', level);
    if (search) params.append('search', search);
    return fetchJSON(`/api/system/logs?${params}`);
  },
  fetchErrorLogs: (logFile = 'sentinel.log', lines = 50) => {
    const params = new URLSearchParams({ log_file: logFile, lines: lines.toString() });
    return fetchJSON(`/api/system/logs/errors?${params}`);
  },
  fetchAvailableLogFiles: () => fetchJSON('/api/system/logs/list'),

  // Jobs - Original composite jobs
  triggerSyncCycle: () => fetchJSON('/api/system/jobs/sync-cycle', { method: 'POST' }),
  triggerDailyPipeline: () => fetchJSON('/api/system/sync/daily-pipeline', { method: 'POST' }),
  triggerDividendReinvestment: () => fetchJSON('/api/system/jobs/dividend-reinvestment', { method: 'POST' }),
  triggerHealthCheck: () => fetchJSON('/api/system/jobs/health-check', { method: 'POST' }),
  triggerPlannerBatch: () => fetchJSON('/api/system/jobs/planner-batch', { method: 'POST' }),
  triggerEventBasedTrading: () => fetchJSON('/api/system/jobs/event-based-trading', { method: 'POST' }),
  triggerTagUpdate: () => fetchJSON('/api/system/jobs/tag-update', { method: 'POST' }),
  hardUpdate: () => fetchJSON('/api/system/deployment/hard-update', { method: 'POST' }),

  // Jobs - Individual sync jobs
  triggerSyncTrades: () => fetchJSON('/api/system/jobs/sync-trades', { method: 'POST' }),
  triggerSyncCashFlows: () => fetchJSON('/api/system/jobs/sync-cash-flows', { method: 'POST' }),
  triggerSyncPortfolio: () => fetchJSON('/api/system/jobs/sync-portfolio', { method: 'POST' }),
  triggerSyncPrices: () => fetchJSON('/api/system/jobs/sync-prices', { method: 'POST' }),
  triggerCheckNegativeBalances: () => fetchJSON('/api/system/jobs/check-negative-balances', { method: 'POST' }),
  triggerUpdateDisplayTicker: () => fetchJSON('/api/system/jobs/update-display-ticker', { method: 'POST' }),

  // Jobs - Individual planning jobs
  triggerGeneratePortfolioHash: () => fetchJSON('/api/system/jobs/generate-portfolio-hash', { method: 'POST' }),
  triggerGetOptimizerWeights: () => fetchJSON('/api/system/jobs/get-optimizer-weights', { method: 'POST' }),
  triggerBuildOpportunityContext: () => fetchJSON('/api/system/jobs/build-opportunity-context', { method: 'POST' }),
  triggerCreateTradePlan: () => fetchJSON('/api/system/jobs/create-trade-plan', { method: 'POST' }),
  triggerStoreRecommendations: () => fetchJSON('/api/system/jobs/store-recommendations', { method: 'POST' }),

  // Jobs - Individual dividend jobs
  triggerGetUnreinvestedDividends: () => fetchJSON('/api/system/jobs/get-unreinvested-dividends', { method: 'POST' }),
  triggerGroupDividendsBySymbol: () => fetchJSON('/api/system/jobs/group-dividends-by-symbol', { method: 'POST' }),
  triggerCheckDividendYields: () => fetchJSON('/api/system/jobs/check-dividend-yields', { method: 'POST' }),
  triggerCreateDividendRecommendations: () => fetchJSON('/api/system/jobs/create-dividend-recommendations', { method: 'POST' }),
  triggerSetPendingBonuses: () => fetchJSON('/api/system/jobs/set-pending-bonuses', { method: 'POST' }),
  triggerExecuteDividendTrades: () => fetchJSON('/api/system/jobs/execute-dividend-trades', { method: 'POST' }),

  // Jobs - Individual health check jobs
  triggerCheckCoreDatabases: () => fetchJSON('/api/system/jobs/check-core-databases', { method: 'POST' }),
  triggerCheckHistoryDatabases: () => fetchJSON('/api/system/jobs/check-history-databases', { method: 'POST' }),
  triggerCheckWALCheckpoints: () => fetchJSON('/api/system/jobs/check-wal-checkpoints', { method: 'POST' }),

  // Allocation
  fetchAllocation: () => fetchJSON('/api/allocation/groups/allocation'),
  fetchTargets: () => fetchJSON('/api/allocation/targets'),
  saveCountryTargets: (targets) => fetchJSON('/api/allocation/groups/targets/country', {
    method: 'PUT',
    body: JSON.stringify({ targets }),
  }),
  saveIndustryTargets: (targets) => fetchJSON('/api/allocation/groups/targets/industry', {
    method: 'PUT',
    body: JSON.stringify({ targets }),
  }),

  // Securities
  fetchSecurities: () => fetchJSON('/api/securities'),
  createSecurity: (data) => fetchJSON('/api/securities', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  addSecurityByIdentifier: (data) => fetchJSON('/api/securities/add-by-identifier', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateSecurity: (isin, data) => fetchJSON(`/api/securities/${isin}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteSecurity: (isin) => fetchJSON(`/api/securities/${isin}`, { method: 'DELETE' }),
  refreshScore: (isin) => fetchJSON(`/api/securities/${isin}/refresh`, { method: 'POST' }),
  refreshAllScores: () => fetchJSON('/api/securities/refresh-all', { method: 'POST' }),

  // Trades
  fetchTrades: () => fetchJSON('/api/trades'),
  fetchRecommendations: () => fetchJSON('/api/trades/recommendations'),
  executeRecommendation: () => fetchJSON('/api/trades/recommendations/execute', { method: 'POST' }),

  // Charts
  fetchSecurityChart: (isin, range = '1Y', source = 'tradernet') => {
    const params = new URLSearchParams({ range, source });
    return fetchJSON(`/api/charts/securities/${isin}?${params}`);
  },
  fetchSparklines: () => fetchJSON('/api/charts/sparklines'),

  // Settings
  fetchSettings: () => fetchJSON('/api/settings'),
  updateSetting: (key, value) => {
    const stringSettings = ['tradernet_api_key', 'tradernet_api_secret', 'trading_mode', 'display_mode', 'security_table_visible_columns'];
    const finalValue = stringSettings.includes(key) ? value : parseFloat(value);
    return fetchJSON(`/api/settings/${key}`, {
      method: 'PUT',
      body: JSON.stringify({ value: finalValue }),
    });
  },
  getTradingMode: () => fetchJSON('/api/settings/trading-mode'),
  toggleTradingMode: () => fetchJSON('/api/settings/trading-mode', { method: 'POST' }),
  restartService: () => fetchJSON('/api/settings/restart-service', { method: 'POST' }),
  restartSystem: () => fetchJSON('/api/settings/restart', { method: 'POST' }),
  resetCache: () => fetchJSON('/api/settings/reset-cache', { method: 'POST' }),
  rescheduleJobs: () => fetchJSON('/api/settings/reschedule-jobs', { method: 'POST' }),
  testTradernetConnection: () => fetchJSON('/api/system/tradernet'),

  // Planner
  regenerateSequences: () => fetchJSON('/api/planner/regenerate-sequences', { method: 'POST' }),

  // Planner Configuration (single config - no ID needed)
  fetchPlannerConfig: () => fetchJSON('/api/planning/config'),
  updatePlannerConfig: (config, changedBy, changeNote) => fetchJSON('/api/planning/config', {
    method: 'PUT',
    body: JSON.stringify({ config, changed_by: changedBy, change_note: changeNote }),
  }),
  deletePlannerConfig: () => fetchJSON('/api/planning/config', { method: 'DELETE' }),
  validatePlannerConfig: () => fetchJSON('/api/planning/config/validate', {
    method: 'POST',
  }),

  // Markets
  fetchMarkets: () => fetchJSON('/api/system/markets'),

  // Cash Breakdown
  fetchCashBreakdown: () => fetchJSON('/api/portfolio/cash-breakdown'),

  // Grouping
  fetchAvailableCountries: () => fetchJSON('/api/allocation/groups/available/countries'),
  fetchAvailableIndustries: () => fetchJSON('/api/allocation/groups/available/industries'),
  fetchCountryGroups: () => fetchJSON('/api/allocation/groups/country'),
  fetchIndustryGroups: () => fetchJSON('/api/allocation/groups/industry'),
  updateCountryGroup: (data) => fetchJSON('/api/allocation/groups/country', {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  updateIndustryGroup: (data) => fetchJSON('/api/allocation/groups/industry', {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteCountryGroup: (groupName) => fetchJSON(`/api/allocation/groups/country/${encodeURIComponent(groupName)}`, {
    method: 'DELETE',
  }),
  deleteIndustryGroup: (groupName) => fetchJSON(`/api/allocation/groups/industry/${encodeURIComponent(groupName)}`, {
    method: 'DELETE',
  }),
};
