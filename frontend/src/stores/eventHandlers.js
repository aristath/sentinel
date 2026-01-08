import { useAppStore } from './appStore';
import { useSecuritiesStore } from './securitiesStore';
import { usePortfolioStore } from './portfolioStore';
import { useTradesStore } from './tradesStore';
import { useLogsStore } from './logsStore';
import { useSettingsStore } from './settingsStore';

// Store reference to SecurityChart refresh function
let securityChartRefreshFn = null;

export function setSecurityChartRefreshFn(fn) {
  securityChartRefreshFn = fn;
}

// Debounce utility
const debounceMap = new Map();
const MAX_DEBOUNCE_ENTRIES = 50; // Prevent unbounded growth

function debounce(key, fn, delay) {
  if (debounceMap.has(key)) {
    clearTimeout(debounceMap.get(key));
  }

  // Cleanup old entries if map grows too large
  if (debounceMap.size >= MAX_DEBOUNCE_ENTRIES) {
    const firstKey = debounceMap.keys().next().value;
    const firstTimeout = debounceMap.get(firstKey);
    clearTimeout(firstTimeout);
    debounceMap.delete(firstKey);
  }

  const timeoutId = setTimeout(() => {
    debounceMap.delete(key);
    fn();
  }, delay);
  debounceMap.set(key, timeoutId);
}

// Clear all pending debounces (call on cleanup/unmount)
export function clearAllDebounces() {
  debounceMap.forEach(timeoutId => clearTimeout(timeoutId));
  debounceMap.clear();
}

// Event-to-action mapper
export const eventHandlers = {
  // Securities events
  PRICE_UPDATED: (event) => {
    if (!event) {
      console.warn('PRICE_UPDATED event is null or undefined');
      return;
    }

    debounce('securities', () => {
      useSecuritiesStore.getState().fetchSecurities();
      useSecuritiesStore.getState().fetchSparklines();

      // Refresh security chart if open for this security
      if (securityChartRefreshFn && event.data) {
        const { selectedSecuritySymbol, selectedSecurityIsin } = useAppStore.getState();
        const eventIsin = event.data.isin;
        const eventSymbol = event.data.symbol;
        if (selectedSecuritySymbol &&
            (eventSymbol === selectedSecuritySymbol || eventIsin === selectedSecurityIsin)) {
          securityChartRefreshFn();
        }
      }
    }, 100);
  },

  SCORE_UPDATED: () => {
    debounce('securities', () => {
      useSecuritiesStore.getState().fetchSecurities();
    }, 100);
  },

  SECURITY_SYNCED: (event) => {
    if (!event) {
      console.warn('SECURITY_SYNCED event is null or undefined');
      return;
    }

    useSecuritiesStore.getState().fetchSecurities();
    useSecuritiesStore.getState().fetchSparklines();

    // Refresh security chart if open for this security
    if (securityChartRefreshFn && event.data) {
      const { selectedSecuritySymbol, selectedSecurityIsin } = useAppStore.getState();
      const eventIsin = event.data.isin;
      const eventSymbol = event.data.symbol;
      if (selectedSecuritySymbol &&
          (eventSymbol === selectedSecuritySymbol || eventIsin === selectedSecurityIsin)) {
        securityChartRefreshFn();
      }
    }
  },

  SECURITY_ADDED: () => {
    useSecuritiesStore.getState().fetchSecurities();
  },

  // Portfolio events
  PORTFOLIO_CHANGED: () => {
    debounce('portfolio', () => {
      usePortfolioStore.getState().fetchAllocation();
      usePortfolioStore.getState().fetchCashBreakdown();
    }, 100);
  },

  TRADE_EXECUTED: () => {
    usePortfolioStore.getState().fetchAllocation();
    usePortfolioStore.getState().fetchCashBreakdown();
    useTradesStore.getState().fetchTrades();
  },

  DEPOSIT_PROCESSED: () => {
    usePortfolioStore.getState().fetchAllocation();
    usePortfolioStore.getState().fetchCashBreakdown();
  },

  DIVIDEND_CREATED: () => {
    usePortfolioStore.getState().fetchAllocation();
    usePortfolioStore.getState().fetchCashBreakdown();
  },

  CASH_UPDATED: () => {
    usePortfolioStore.getState().fetchCashBreakdown();
  },

  ALLOCATION_TARGETS_CHANGED: () => {
    usePortfolioStore.getState().fetchTargets();
    usePortfolioStore.getState().fetchAllocation();
  },

  // Recommendations events
  RECOMMENDATIONS_READY: () => {
    useAppStore.getState().fetchRecommendations();
  },

  PLAN_GENERATED: () => {
    useAppStore.getState().fetchRecommendations();
  },

  PLANNING_STATUS_UPDATED: (event) => {
    if (!event) {
      console.warn('PLANNING_STATUS_UPDATED event is null or undefined');
      return;
    }
    const status = event.data || {};
    useAppStore.getState().updatePlannerStatus(status);
  },

  // System status events
  SYSTEM_STATUS_CHANGED: () => {
    useAppStore.getState().fetchStatus();
  },

  TRADERNET_STATUS_CHANGED: () => {
    useAppStore.getState().fetchTradernet();
  },

  MARKETS_STATUS_CHANGED: () => {
    useAppStore.getState().fetchMarkets();
  },

  // Logs events
  LOG_FILE_CHANGED: (event) => {
    if (!event || !event.data) {
      console.warn('LOG_FILE_CHANGED event missing data');
      return;
    }
    const { selectedLogFile } = useLogsStore.getState();
    if (event.data.log_file === selectedLogFile) {
      useLogsStore.getState().fetchLogs();
    }
  },

  // Settings events
  SETTINGS_CHANGED: () => {
    useSettingsStore.getState().fetchSettings();
    useSecuritiesStore.getState().fetchColumnVisibility();
  },

  PLANNER_CONFIG_CHANGED: () => {
    // Planner modal will refetch on open, or emit custom event
    // For now, just log it
    console.log('Planner config changed');
  },

  // Heartbeat - no action needed
  heartbeat: () => {
    // Heartbeat received, connection is alive
  },

  // Connected - no action needed
  connected: () => {
    console.log('Connected to unified event stream');
  },
};

// Handle an event from the SSE stream
export function handleEvent(event) {
  const { type, data } = event;

  if (!type) {
    console.warn('Received event without type:', event);
    return;
  }

  const handler = eventHandlers[type];
  if (handler) {
    try {
      handler({ type, data });
    } catch (error) {
      console.error(`Error handling event ${type}:`, error);
    }
  } else {
    console.debug(`No handler for event type: ${type}`);
  }
}
