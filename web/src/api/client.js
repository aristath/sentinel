/**
 * API Client for Sentinel backend
 */

const API_BASE = '/api';

async function request(endpoint, options = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    // Try to extract error detail from response body
    let errorMessage = `API error: ${response.status} ${response.statusText}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        errorMessage = errorData.detail;
      }
    } catch {
      // Response body is not JSON, use default message
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

// Version
export const getVersion = () => request('/version');

// Portfolio
export const getPortfolio = () => request('/portfolio');
export const getPositions = () => request('/positions');

// Securities
export const getSecurities = () => request('/securities');
export const getSecurity = (symbol) => request(`/securities/${symbol}`);
export const addSecurity = (symbol, geography = [], industry = []) =>
  request('/securities', {
    method: 'POST',
    body: JSON.stringify({
      symbol,
      geography: Array.isArray(geography) ? geography.join(', ') : geography,
      industry: Array.isArray(industry) ? industry.join(', ') : industry,
    }),
  });
export const deleteSecurity = (symbol, sellPosition = true) =>
  request(`/securities/${encodeURIComponent(symbol)}?sell_position=${sellPosition}`, {
    method: 'DELETE',
  });

// Recommendations (minValue optional - uses backend setting if not provided)
export const getRecommendations = (minValue) => {
  const url = minValue !== undefined
    ? `/planner/recommendations?min_value=${minValue}`
    : '/planner/recommendations';
  return request(url);
};

// Jobs/Scheduler
export const getSchedulerStatus = () => request('/jobs');
export const runJob = (jobName) =>
  request(`/jobs/${encodeURIComponent(jobName)}/run`, { method: 'POST' });
export const refreshAll = () =>
  request('/jobs/refresh-all', { method: 'POST' });

// Job Schedules
export const getJobSchedules = () => request('/jobs/schedules');
export const updateJobSchedule = (jobType, data) =>
  request(`/jobs/schedules/${encodeURIComponent(jobType)}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
export const getJobHistory = (jobType = null, limit = 50) => {
  const params = new URLSearchParams();
  if (jobType) params.append('job_type', jobType);
  if (limit) params.append('limit', limit);
  const query = params.toString();
  return request(`/jobs/history${query ? '?' + query : ''}`);
};

// Settings
export const getSettings = () => request('/settings');
export const updateSetting = (key, value) =>
  request(`/settings/${key}`, {
    method: 'PUT',
    body: JSON.stringify({ value }),
  });

// Unified view
export const getUnifiedView = (period = '1Y') => request(`/unified?period=${period}`);

// Update security
export const updateSecurity = (symbol, data) => {
  // Convert geography/industry arrays to comma-separated strings
  const processedData = { ...data };
  if (Array.isArray(processedData.geography)) {
    processedData.geography = processedData.geography.join(', ');
  }
  if (Array.isArray(processedData.industry)) {
    processedData.industry = processedData.industry.join(', ');
  }
  return request(`/securities/${encodeURIComponent(symbol)}`, {
    method: 'PUT',
    body: JSON.stringify(processedData),
  });
};

// Allocation
export const getAllocation = () => request('/allocation/current');
export const getAllocationTargets = () => request('/allocation/targets');
export const getAvailableGeographies = () => request('/allocation/available-geographies');
export const getAvailableIndustries = () => request('/allocation/available-industries');
export const saveGeographyTargets = (targets) =>
  request('/allocation/targets/geography', {
    method: 'PUT',
    body: JSON.stringify({ targets }),
  });
export const saveIndustryTargets = (targets) =>
  request('/allocation/targets/industry', {
    method: 'PUT',
    body: JSON.stringify({ targets }),
  });
export const deleteGeographyTarget = (name) =>
  request(`/allocation/targets/geography/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
export const deleteIndustryTarget = (name) =>
  request(`/allocation/targets/industry/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });

// Markets
export const getMarketsStatus = () => request('/markets/status');

// LED Display
export const getLedStatus = () => request('/led/status');
export const setLedEnabled = (enabled) =>
  request('/led/enabled', {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  });
export const setLedBrightness = (brightness) =>
  request('/led/brightness', {
    method: 'PUT',
    body: JSON.stringify({ brightness }),
  });
export const syncLed = () => request('/led/sync', { method: 'POST' });

// Trades
export const getTrades = (params = {}) => {
  const searchParams = new URLSearchParams();
  if (params.symbol) searchParams.append('symbol', params.symbol);
  if (params.side) searchParams.append('side', params.side);
  if (params.start_date) searchParams.append('start_date', params.start_date);
  if (params.end_date) searchParams.append('end_date', params.end_date);
  if (params.limit) searchParams.append('limit', params.limit);
  if (params.offset) searchParams.append('offset', params.offset);
  const query = searchParams.toString();
  return request(`/trades${query ? '?' + query : ''}`);
};
export const syncTrades = () => request('/trades/sync', { method: 'POST' });

// ML Training (per-symbol)
export const getMLTrainingStatus = (symbol) =>
  request(`/ml/training-status/${encodeURIComponent(symbol)}`);
export const deleteMLTrainingData = (symbol) =>
  request(`/ml/training-data/${encodeURIComponent(symbol)}`, { method: 'DELETE' });
// Note: trainSymbol uses SSE streaming and is handled in useMLTraining hook
export const getMLTrainStreamUrl = (symbol) =>
  `${API_BASE}/ml/train/${encodeURIComponent(symbol)}/stream`;

// ML Reset
export const resetAndRetrain = () =>
  request('/ml/reset-and-retrain', { method: 'POST' });
export const getResetStatus = () => request('/ml/reset-status');

// Cash Flows
export const getCashFlows = () => request('/cashflows');
export const syncCashFlows = () => request('/cashflows/sync', { method: 'POST' });

// Portfolio P&L History
export const getPortfolioPnLHistory = (period = '1Y') =>
  request(`/portfolio/pnl-history?period=${period}`);

// Categories
export const getCategories = () => request('/meta/categories');
