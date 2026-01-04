/**
 * Centralized API client for Arduino Trader
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
      errorMessage = errorData.detail || errorData.message || errorMessage;
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
  fetchLogs: (logFile = 'arduino-trader.log', lines = 100, level = null, search = null) => {
    const params = new URLSearchParams({ log_file: logFile, lines: lines.toString() });
    if (level) params.append('level', level);
    if (search) params.append('search', search);
    return fetchJSON(`/api/system/logs?${params}`);
  },
  fetchErrorLogs: (logFile = 'arduino-trader.log', lines = 50) => {
    const params = new URLSearchParams({ log_file: logFile, lines: lines.toString() });
    return fetchJSON(`/api/system/logs/errors?${params}`);
  },
  fetchAvailableLogFiles: () => fetchJSON('/api/system/logs/list'),

  // Jobs
  triggerSyncCycle: () => fetchJSON('/api/system/jobs/sync-cycle', { method: 'POST' }),
  triggerDailyPipeline: () => fetchJSON('/api/system/sync/daily-pipeline', { method: 'POST' }),
  triggerDividendReinvestment: () => fetchJSON('/api/system/jobs/dividend-reinvestment', { method: 'POST' }),

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
    const stringSettings = ['tradernet_api_key', 'tradernet_api_secret', 'trading_mode', 'display_mode'];
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

  // Planner Configuration
  fetchPlanners: () => fetchJSON('/api/planners/'),
  fetchPlannerById: (id) => fetchJSON(`/api/planners/${id}`),
  createPlanner: (data) => fetchJSON('/api/planners/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updatePlanner: (id, data) => fetchJSON(`/api/planners/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deletePlanner: (id) => fetchJSON(`/api/planners/${id}`, { method: 'DELETE' }),
  validatePlannerToml: (toml) => fetchJSON('/api/planners/validate', {
    method: 'POST',
    body: JSON.stringify({ toml }),
  }),
  applyPlanner: (id) => fetchJSON(`/api/planners/${id}/apply`, { method: 'POST' }),
  fetchPlannerHistory: (id) => fetchJSON(`/api/planners/${id}/history`),

  // Satellites/Buckets
  fetchBuckets: () => fetchJSON('/api/satellites/buckets'),
  fetchBucketBalances: (bucketId) => fetchJSON(`/api/satellites/buckets/${bucketId}/balances`),
  fetchAllBucketBalances: () => fetchJSON('/api/satellites/balances/summary'),
  createBucket: (data) => fetchJSON('/api/satellites/buckets', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  retireBucket: (bucketId) => fetchJSON(`/api/satellites/buckets/${bucketId}/retire`, { method: 'POST' }),
  transferCash: (data) => fetchJSON('/api/satellites/balances/transfer', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Markets
  fetchMarkets: () => fetchJSON('/api/system/markets'),

  // Cash Breakdown
  fetchCashBreakdown: () => fetchJSON('/api/portfolio/cash-breakdown'),
};
