/**
 * Arduino Trader - API Layer
 * Centralized API calls for the application
 */

const API = {
  // Base fetch with JSON handling
  async _fetch(url, options = {}) {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    // Check if response is OK before parsing JSON
    if (!res.ok) {
      let errorMessage = `Request failed with status ${res.status}`;
      try {
        const errorData = await res.json();
        errorMessage = errorData.detail || errorData.message || errorMessage;
      } catch (e) {
        // If response isn't JSON, use status text
        errorMessage = res.statusText || errorMessage;
      }
      throw new Error(errorMessage);
    }

    return res.json();
  },

  async _post(url, data) {
    return this._fetch(url, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  },

  async _put(url, data) {
    return this._fetch(url, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  async _delete(url) {
    return this._fetch(url, { method: 'DELETE' });
  },

  // Status
  fetchStatus: () => fetch('/api/system/status').then(r => r.json()),
  fetchTradernet: () => fetch('/api/system/tradernet').then(r => r.json()),
  syncPrices: () => API._post('/api/system/sync/prices'),
  syncHistorical: () => API._post('/api/system/sync/historical'),

  // Logs
  fetchLogs: (logFile = 'arduino-trader.log', lines = 100, level = null, search = null) => {
    const params = new URLSearchParams({ log_file: logFile, lines: lines.toString() });
    if (level) params.append('level', level);
    if (search) params.append('search', search);
    return fetch(`/api/system/logs?${params}`).then(r => r.json());
  },
  fetchErrorLogs: (logFile = 'arduino-trader.log', lines = 50) => {
    const params = new URLSearchParams({ log_file: logFile, lines: lines.toString() });
    return fetch(`/api/system/logs/errors?${params}`).then(r => r.json());
  },
  fetchAvailableLogFiles: () => fetch('/api/system/logs/list').then(r => r.json()),

  // Jobs
  triggerSyncCycle: () => API._post('/api/system/jobs/sync-cycle'),
  triggerDailyPipeline: () => API._post('/api/system/sync/daily-pipeline'),
  triggerDailyMaintenance: () => API._post('/api/system/jobs/health-check'), // Using health-check as daily maintenance
  triggerWeeklyMaintenance: () => API._post('/api/system/jobs/health-check'), // Using health-check as weekly maintenance
  triggerDividendReinvestment: () => API._post('/api/system/jobs/dividend-reinvestment'),

  // Allocation
  fetchAllocation: () => fetch('/api/allocation/groups/allocation').then(r => r.json()),
  fetchTargets: () => fetch('/api/allocation/targets').then(r => r.json()),
  saveCountryTargets: (targets) => API._put('/api/allocation/groups/targets/country', { targets }),
  saveIndustryTargets: (targets) => API._put('/api/allocation/groups/targets/industry', { targets }),

  // Securities
  fetchSecurities: () => fetch('/api/securities').then(r => r.json()),
  createSecurity: (data) => API._post('/api/securities', data),
  addSecurityByIdentifier: (data) => API._post('/api/securities/add-by-identifier', data),
  updateSecurity: (isin, data) => API._put(`/api/securities/${isin}`, data),
  deleteSecurity: (isin) => API._delete(`/api/securities/${isin}`),
  refreshScore: (isin) => API._post(`/api/securities/${isin}/refresh`),
  refreshAllScores: () => API._post('/api/securities/refresh-all'),

  // Trades
  fetchTrades: () => fetch('/api/trades').then(r => r.json()),
  // Unified recommendations endpoint - returns optimal sequence from holistic planner
  fetchRecommendations: () => fetch('/api/trades/recommendations').then(r => r.json()),
  // Execute the first step of the current optimal sequence
  executeRecommendation: () => API._post('/api/trades/recommendations/execute'),

  // Charts
  fetchSecurityChart: (isin, range = '1Y', source = 'tradernet') => {
    const params = new URLSearchParams({ range, source });
    return fetch(`/api/charts/securities/${isin}?${params}`).then(r => r.json());
  },
  fetchSparklines: () => fetch('/api/charts/sparklines').then(r => r.json()),

  // Settings
  fetchSettings: () => fetch('/api/settings').then(r => r.json()),
  updateSetting: (key, value) => {
    // Handle string settings vs numeric settings
    const stringSettings = ['tradernet_api_key', 'tradernet_api_secret', 'trading_mode', 'display_mode'];
    const finalValue = stringSettings.includes(key) ? value : parseFloat(value);
    return API._put(`/api/settings/${key}`, { value: finalValue });
  },
  getTradingMode: () => fetch('/api/settings/trading-mode').then(r => r.json()),
  toggleTradingMode: () => API._post('/api/settings/trading-mode'),
  restartService: () => API._post('/api/settings/restart-service'),
  restartSystem: () => API._post('/api/settings/restart'),
  resetCache: () => API._post('/api/settings/reset-cache'),
  rescheduleJobs: () => API._post('/api/settings/reschedule-jobs'),
  testTradernetConnection: () => API._fetch('/api/system/tradernet'),

  // Planner
  regenerateSequences: () => API._post('/api/planner/regenerate-sequences'),

  // Planner Configuration Management
  fetchPlanners: () => fetch('/api/planners/').then(r => r.json()),
  fetchPlannerById: (id) => fetch(`/api/planners/${id}`).then(r => r.json()),
  createPlanner: (data) => API._post('/api/planners/', data),
  updatePlanner: (id, data) => API._put(`/api/planners/${id}`, data),
  deletePlanner: (id) => API._delete(`/api/planners/${id}`),
  validatePlannerToml: (toml) => API._post('/api/planners/validate', { toml }),
  applyPlanner: (id) => API._post(`/api/planners/${id}/apply`),
  fetchPlannerHistory: (id) => fetch(`/api/planners/${id}/history`).then(r => r.json()),

  // Satellites/Buckets
  fetchBuckets: () => fetch('/api/satellites/buckets').then(r => r.json()),
  fetchBucketBalances: (bucketId) => fetch(`/api/satellites/buckets/${bucketId}/balances`).then(r => r.json()),
  fetchAllBucketBalances: () => fetch('/api/satellites/balances/summary').then(r => r.json()),
  createBucket: (data) => API._post('/api/satellites/buckets', data),
  retireBucket: (bucketId) => API._post(`/api/satellites/buckets/${bucketId}/retire`),
  transferCash: (data) => API._post('/api/satellites/balances/transfer', data),

};

// Make available globally
window.API = API;
