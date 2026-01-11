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

// Job type to human-readable description mapping (mirrors backend)
function getJobDescription(jobType) {
  const descriptions = {
    'planner_batch': 'Generating trading recommendations',
    'event_based_trading': 'Executing trade',
    'sync_trades': 'Syncing trades from broker',
    'sync_portfolio': 'Syncing portfolio positions',
    'sync_prices': 'Updating security prices',
    'sync_cash_flows': 'Syncing cash flows',
    'sync_exchange_rates': 'Updating exchange rates',
    'check_negative_balances': 'Checking account balances',
    'hourly_backup': 'Creating hourly backup',
    'daily_backup': 'Creating daily backup',
    'weekly_backup': 'Creating weekly backup',
    'monthly_backup': 'Creating monthly backup',
    'r2_backup': 'Uploading backup to cloud',
    'r2_backup_rotation': 'Rotating cloud backups',
    'dividend_reinvestment': 'Processing dividend reinvestment',
    'deployment': 'Checking for system updates',
    'generate_sequences': 'Generating trade sequences',
    'evaluate_sequences': 'Evaluating trade sequences',
    'get_optimizer_weights': 'Running portfolio optimizer',
    'identify_opportunities': 'Identifying opportunities',
    'create_trade_plan': 'Creating trade plan',
    'store_recommendations': 'Storing recommendations',
    'tag_update': 'Updating security tags',
    'retry_trades': 'Retrying pending trades',
    'update_display_ticker': 'Updating LED display',
    'recommendation_gc': 'Cleaning up old recommendations',
    'daily_maintenance': 'Running daily maintenance',
    'weekly_maintenance': 'Running weekly maintenance',
    'monthly_maintenance': 'Running monthly maintenance',
    'health_check': 'Running health check',
    'adaptive_market_check': 'Checking market regime',
    'formula_discovery': 'Discovering optimal formulas',
    'history_cleanup': 'Cleaning up historical data',
    'sync_cycle': 'Syncing all data from broker',
    'generate_portfolio_hash': 'Generating portfolio hash',
    'build_opportunity_context': 'Building opportunity context',
    'get_unreinvested_dividends': 'Getting unreinvested dividends',
    'group_dividends_by_symbol': 'Grouping dividends by symbol',
    'check_dividend_yields': 'Checking dividend yields',
    'create_dividend_recommendations': 'Creating dividend recommendations',
    'set_pending_bonuses': 'Setting pending bonuses',
    'execute_dividend_trades': 'Executing dividend trades',
    'check_core_databases': 'Checking core databases',
    'check_history_databases': 'Checking history databases',
    'check_wal_checkpoints': 'Checking WAL checkpoints',
  };
  return descriptions[jobType] || jobType;
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

  MARKETS_STATUS_CHANGED: (event) => {
    if (!event || !event.data) {
      console.warn('MARKETS_STATUS_CHANGED event missing data');
      return;
    }
    // Update markets state with individual market data
    useAppStore.setState({ markets: event.data.markets || {} });
  },

  // Logs events - removed (logs now use HTTP polling instead of SSE)

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

  // Job lifecycle events
  JOB_STARTED: (event) => {
    if (!event || !event.data) {
      console.warn('JOB_STARTED event missing data');
      return;
    }
    const { job_id, job_type, description, timestamp } = event.data;
    useAppStore.getState().addRunningJob({
      jobId: job_id,
      jobType: job_type,
      status: 'running',
      description: description || getJobDescription(job_type),
      startedAt: new Date(timestamp).getTime(),
    });
  },

  JOB_PROGRESS: (event) => {
    if (!event || !event.data) {
      console.warn('JOB_PROGRESS event missing data');
      return;
    }
    const { job_id, progress } = event.data;
    if (progress) {
      useAppStore.getState().updateJobProgress(job_id, progress);
    }
  },

  JOB_COMPLETED: (event) => {
    if (!event || !event.data) {
      console.warn('JOB_COMPLETED event missing data');
      return;
    }
    const { job_id, duration } = event.data;
    useAppStore.getState().completeJob(job_id, {
      status: 'completed',
      duration,
    });
  },

  JOB_FAILED: (event) => {
    if (!event || !event.data) {
      console.warn('JOB_FAILED event missing data');
      return;
    }
    const { job_id, error, duration } = event.data;
    useAppStore.getState().completeJob(job_id, {
      status: 'failed',
      error,
      duration,
    });
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
