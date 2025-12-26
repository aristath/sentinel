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
  fetchStatus: () => fetch('/api/status').then(r => r.json()),
  fetchTradernet: () => fetch('/api/status/tradernet').then(r => r.json()),
  syncPrices: () => API._post('/api/status/sync/prices'),
  syncHistorical: () => API._post('/api/status/sync/historical'),

  // Allocation
  fetchAllocation: () => fetch('/api/trades/allocation').then(r => r.json()),
  fetchTargets: () => fetch('/api/allocation/targets').then(r => r.json()),
  saveGeoTargets: (targets) => API._put('/api/allocation/targets/geography', { targets }),
  saveIndustryTargets: (targets) => API._put('/api/allocation/targets/industry', { targets }),

  // Stocks
  fetchStocks: () => fetch('/api/stocks').then(r => r.json()),
  createStock: (data) => API._post('/api/stocks', data),
  updateStock: (symbol, data) => API._put(`/api/stocks/${symbol}`, data),
  deleteStock: (symbol) => API._delete(`/api/stocks/${symbol}`),
  refreshScore: (symbol) => API._post(`/api/stocks/${symbol}/refresh`),
  refreshAllScores: () => API._post('/api/stocks/refresh-all'),

  // Trades
  fetchTrades: () => fetch('/api/trades').then(r => r.json()),
  fetchRecommendations: () => fetch('/api/trades/recommendations?limit=10').then(r => r.json()),
  dismissRecommendation: (uuid) => API._post(`/api/trades/recommendations/${uuid}/dismiss`),
  fetchSellRecommendations: () => fetch('/api/trades/sell-recommendations').then(r => r.json()),
  dismissSellRecommendation: (uuid) => API._post(`/api/trades/sell-recommendations/${uuid}/dismiss`),
  // Deprecated - recommendations now execute automatically
  // executeRecommendation: (symbol) => API._post(`/api/trades/recommendations/${symbol}/execute`),
  // executeSellRecommendation: (symbol) => API._post(`/api/trades/sell-recommendations/${symbol}/execute`),
  fetchMultiStepRecommendations: () => {
    return fetch('/api/trades/multi-step-recommendations').then(r => r.json());
  },
  fetchAllStrategyRecommendations: () => {
    return fetch('/api/trades/multi-step-recommendations/all').then(r => r.json());
  },
  executeMultiStepStep: (stepNumber) => API._post(`/api/trades/multi-step-recommendations/execute-step/${stepNumber}`),
  executeAllMultiStep: () => API._post('/api/trades/multi-step-recommendations/execute-all'),

  // Charts
  fetchStockChart: (symbol, range = '1Y', source = 'tradernet') => {
    const params = new URLSearchParams({ range, source });
    return fetch(`/api/charts/stocks/${symbol}?${params}`).then(r => r.json());
  },
  fetchSparklines: () => fetch('/api/charts/sparklines').then(r => r.json()),

  // Settings
  fetchSettings: () => fetch('/api/settings').then(r => r.json()),
  updateSetting: (key, value) => API._put(`/api/settings/${key}`, { value: parseFloat(value) }),
  getTradingMode: () => fetch('/api/settings/trading-mode').then(r => r.json()),
  toggleTradingMode: () => API._post('/api/settings/trading-mode'),
  restartService: () => API._post('/api/settings/restart-service'),
  restartSystem: () => API._post('/api/settings/restart'),
  resetCache: () => API._post('/api/settings/reset-cache'),
  rescheduleJobs: () => API._post('/api/settings/reschedule-jobs'),

  // Optimizer
  fetchOptimizerStatus: () => fetch('/api/optimizer').then(r => r.json()),
  runOptimizer: () => API._post('/api/optimizer/run'),
};

// Make available globally
window.API = API;
