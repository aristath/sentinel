/**
 * API Client for Sentinel backend
 */

const API_BASE = import.meta.env.VITE_MONOLITH_API_BASE || '/api';
const ML_API_BASE = import.meta.env.VITE_ML_API_BASE || '/ml-api';
const ML_JOB_TYPES = new Set(['ml:retrain', 'ml:monitor', 'analytics:regime']);
let mlBaseUrlCache = null;

async function requestFrom(base, endpoint, options = {}) {
  const response = await fetch(`${base}${endpoint}`, {
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

async function request(endpoint, options = {}) {
  return requestFrom(API_BASE, endpoint, options);
}

async function resolveMLBaseUrl() {
  if (mlBaseUrlCache) {
    return mlBaseUrlCache;
  }

  // If explicitly configured, trust that first.
  if (ML_API_BASE && ML_API_BASE !== '/ml-api') {
    mlBaseUrlCache = ML_API_BASE;
    return mlBaseUrlCache;
  }

  // Runtime fallback for monolith-served frontend: read ML base URL from settings.
  try {
    const settings = await request('/settings');
    const configured = (settings?.ml_service_base_url || '').trim();
    if (configured) {
      mlBaseUrlCache = configured.replace(/\/$/, '');
      return mlBaseUrlCache;
    }
  } catch {
    // Keep proxy default below when settings are temporarily unavailable.
  }

  mlBaseUrlCache = ML_API_BASE;
  return mlBaseUrlCache;
}

async function requestML(endpoint, options = {}) {
  const mlBase = await resolveMLBaseUrl();
  return requestFrom(mlBase, endpoint, options);
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
const isMLJobType = (jobType) => ML_JOB_TYPES.has(jobType);

const parseEpoch = (iso) => (iso ? new Date(iso).getTime() : 0);

const mergeStatus = (mono = {}, ml = {}) => {
  const current =
    mono.current && ml.current
      ? `${mono.current} | ${ml.current}`
      : (mono.current || ml.current || null);

  const upcoming = [...(mono.upcoming || []), ...(ml.upcoming || [])]
    .sort((a, b) => parseEpoch(a.next_run) - parseEpoch(b.next_run))
    .slice(0, 3);

  const recent = [...(mono.recent || []), ...(ml.recent || [])]
    .sort((a, b) => parseEpoch(b.executed_at) - parseEpoch(a.executed_at))
    .slice(0, 3);

  return { current, upcoming, recent };
};

export const getSchedulerStatus = async () => {
  const [mono, ml] = await Promise.all([request('/jobs'), requestML('/jobs')]);
  return mergeStatus(mono, ml);
};

export const runJob = (jobName) => {
  const runner = isMLJobType(jobName) ? requestML : request;
  return runner(`/jobs/${encodeURIComponent(jobName)}/run`, { method: 'POST' });
};

export const refreshAll = async () => {
  await Promise.all([
    request('/jobs/refresh-all', { method: 'POST' }),
    requestML('/jobs/refresh-all', { method: 'POST' }),
  ]);
  return { status: 'ok', message: 'All jobs rescheduled' };
};

// Job Schedules
export const getJobSchedules = async () => {
  const [mono, ml] = await Promise.all([request('/jobs/schedules'), requestML('/jobs/schedules')]);
  const merged = [...(mono.schedules || []), ...(ml.schedules || [])];
  return { schedules: merged };
};

export const updateJobSchedule = (jobType, data) => {
  const updater = isMLJobType(jobType) ? requestML : request;
  return updater(`/jobs/schedules/${encodeURIComponent(jobType)}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
};
export const getJobHistory = (jobType = null, limit = 50) => {
  if (jobType) {
    const getter = isMLJobType(jobType) ? requestML : request;
    const params = new URLSearchParams();
    params.append('job_type', jobType);
    if (limit) params.append('limit', limit);
    return getter(`/jobs/history?${params.toString()}`);
  }

  const params = new URLSearchParams();
  if (limit) params.append('limit', limit);
  const query = params.toString();
  return Promise.all([
    request(`/jobs/history${query ? '?' + query : ''}`),
    requestML(`/jobs/history${query ? '?' + query : ''}`),
  ]).then(([mono, ml]) => {
    const merged = [...(mono.history || []), ...(ml.history || [])]
      .sort((a, b) => (b.executed_at || 0) - (a.executed_at || 0))
      .slice(0, limit);
    return { history: merged };
  });
};

// Settings
export const getSettings = () => request('/settings');
export const updateSetting = (key, value) =>
  request(`/settings/${key}`, {
    method: 'PUT',
    body: JSON.stringify({ value }),
  });
export const updateSettingsBatch = (values) =>
  request('/settings', {
    method: 'PUT',
    body: JSON.stringify({ values }),
  }).catch(async (error) => {
    // Backward-compatible fallback when batch endpoint is not available yet.
    if (!String(error?.message || '').includes('405')) {
      throw error;
    }
    const entries = Object.entries(values);
    await Promise.all(entries.map(([key, value]) => updateSetting(key, value)));
    return { status: 'ok' };
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
  if (Array.isArray(processedData.aliases)) {
    processedData.aliases = processedData.aliases.join(', ');
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
  requestML(`/ml/training-status/${encodeURIComponent(symbol)}`);
export const deleteMLTrainingData = (symbol) =>
  requestML(`/ml/training-data/${encodeURIComponent(symbol)}`, { method: 'DELETE' });
// Note: trainSymbol uses SSE streaming and is handled in useMLTraining hook
export const getMLTrainStreamUrl = (symbol) =>
  `${ML_API_BASE}/ml/train/${encodeURIComponent(symbol)}/stream`;

// ML Reset
export const resetAndRetrain = () =>
  requestML('/ml/reset-and-retrain', { method: 'POST' });
export const getResetStatus = () => requestML('/ml/reset-status');
export const getMLPortfolioOverlays = () => requestML('/ml/portfolio-overlays');
export const getMLSecurityOverlays = (symbols, days = 365) => {
  const list = Array.isArray(symbols) ? symbols.filter(Boolean) : [];
  if (list.length === 0) return Promise.resolve({ series: {} });
  const params = new URLSearchParams({ symbols: list.join(','), days: String(days) });
  return requestML(`/ml/security-overlays?${params.toString()}`);
};

// Cash Flows
export const getCashFlows = () => request('/cashflows');
export const syncCashFlows = () => request('/cashflows/sync', { method: 'POST' });

// Portfolio P&L History
export const getPortfolioPnLHistory = () => request('/portfolio/pnl-history');

// Categories
export const getCategories = () => request('/meta/categories');
