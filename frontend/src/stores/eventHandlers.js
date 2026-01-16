/**
 * Event Handlers for Server-Sent Events (SSE) Stream
 *
 * This module handles events received from the backend via Server-Sent Events.
 * Events are routed to appropriate store actions to update the UI in real-time.
 *
 * Event Types:
 * - Securities events: PRICE_UPDATED, SCORE_UPDATED, SECURITY_SYNCED, SECURITY_ADDED
 * - Portfolio events: PORTFOLIO_CHANGED, TRADE_EXECUTED, DEPOSIT_PROCESSED, etc.
 * - Recommendations events: RECOMMENDATIONS_READY, PLAN_GENERATED
 * - System events: SYSTEM_STATUS_CHANGED, TRADERNET_STATUS_CHANGED, MARKETS_STATUS_CHANGED
 * - Settings events: SETTINGS_CHANGED, PLANNER_CONFIG_CHANGED
 * - Job lifecycle events: JOB_STARTED, JOB_PROGRESS, JOB_COMPLETED, JOB_FAILED
 *
 * Many handlers use debouncing to prevent excessive API calls when multiple
 * events arrive in quick succession.
 */
import { useAppStore } from './appStore';
import { useSecuritiesStore } from './securitiesStore';
import { usePortfolioStore } from './portfolioStore';
import { useTradesStore } from './tradesStore';
import { useSettingsStore } from './settingsStore';

/**
 * Reference to SecurityChart component's refresh function
 * Set by the SecurityChart component to allow event handlers to refresh
 * the chart when price data for the displayed security is updated
 * @type {Function|null}
 */
let securityChartRefreshFn = null;

/**
 * Sets the security chart refresh function
 * Called by SecurityChart component to register its refresh callback
 *
 * @param {Function} fn - Function to call when chart needs refresh
 */
export function setSecurityChartRefreshFn(fn) {
  securityChartRefreshFn = fn;
}

/**
 * Maps job type identifiers to human-readable descriptions
 *
 * This mapping mirrors the backend job type definitions and is used
 * to display user-friendly job descriptions in the UI.
 *
 * @param {string} jobType - Job type identifier (e.g., 'planner_batch', 'sync_prices')
 * @returns {string} Human-readable job description
 */
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

// ============================================================================
// Debounce Utility
// ============================================================================
// Prevents excessive API calls when multiple events arrive in quick succession.
// Each debounce key can have one pending timeout; new calls reset the timer.

/**
 * Map of debounce keys to their timeout IDs
 * @type {Map<string, number>}
 */
const debounceMap = new Map();

/**
 * Maximum number of debounce entries before cleanup
 * Prevents unbounded memory growth if many different events are debounced
 */
const MAX_DEBOUNCE_ENTRIES = 50;

/**
 * Debounces a function call - delays execution until no new calls for 'delay' ms
 *
 * If called multiple times with the same key within the delay period,
 * only the last call will execute. This prevents excessive API calls
 * when many events arrive in quick succession (e.g., multiple price updates).
 *
 * @param {string} key - Unique key for this debounce operation
 * @param {Function} fn - Function to execute after delay
 * @param {number} delay - Delay in milliseconds
 */
function debounce(key, fn, delay) {
  // Clear existing timeout for this key if present
  if (debounceMap.has(key)) {
    clearTimeout(debounceMap.get(key));
  }

  // Cleanup old entries if map grows too large
  // Prevents memory leaks if many different events are debounced
  if (debounceMap.size >= MAX_DEBOUNCE_ENTRIES) {
    const firstKey = debounceMap.keys().next().value;
    const firstTimeout = debounceMap.get(firstKey);
    clearTimeout(firstTimeout);
    debounceMap.delete(firstKey);
  }

  // Set new timeout
  const timeoutId = setTimeout(() => {
    debounceMap.delete(key);
    fn();
  }, delay);
  debounceMap.set(key, timeoutId);
}

/**
 * Clears all pending debounced function calls
 *
 * Should be called on component unmount or cleanup to prevent
 * stale function calls after the component is destroyed.
 */
export function clearAllDebounces() {
  debounceMap.forEach(timeoutId => clearTimeout(timeoutId));
  debounceMap.clear();
}

// ============================================================================
// Event Handlers Map
// ============================================================================
// Maps event type names to handler functions that update stores accordingly

/**
 * Event handlers object - maps event types to handler functions
 *
 * Each handler receives an event object with { type, data } structure.
 * Handlers update appropriate stores to reflect the event in the UI.
 */
export const eventHandlers = {
  // ============================================================================
  // Securities Events
  // ============================================================================

  /**
   * Handles price update events for securities
   *
   * Debounced to prevent excessive API calls when many prices update simultaneously.
   * Refreshes securities list, sparklines, and security chart if open.
   *
   * @param {Object} event - Event object with { type, data }
   * @param {Object} event.data - Price update data with isin and symbol
   */
  PRICE_UPDATED: (event) => {
    if (!event) {
      console.warn('PRICE_UPDATED event is null or undefined');
      return;
    }

    // Debounce to batch multiple price updates together
    debounce('securities', () => {
      // Refresh securities list and sparklines with updated prices
      useSecuritiesStore.getState().fetchSecurities();
      useSecuritiesStore.getState().fetchSparklines();

      // Refresh security chart if it's open for the updated security
      if (securityChartRefreshFn && event.data) {
        const { selectedSecuritySymbol, selectedSecurityIsin } = useAppStore.getState();
        const eventIsin = event.data.isin;
        const eventSymbol = event.data.symbol;
        // Check if the updated security matches the currently displayed chart
        if (selectedSecuritySymbol &&
            (eventSymbol === selectedSecuritySymbol || eventIsin === selectedSecurityIsin)) {
          securityChartRefreshFn();
        }
      }
    }, 100);  // 100ms debounce delay
  },

  /**
   * Handles security score update events
   *
   * Debounced to prevent excessive API calls. Refreshes securities list
   * to show updated scores.
   *
   * @param {Object} event - Event object (data not used for this event)
   */
  SCORE_UPDATED: () => {
    debounce('securities', () => {
      useSecuritiesStore.getState().fetchSecurities();
    }, 100);
  },

  /**
   * Handles security synchronization completion events
   *
   * Not debounced (immediate refresh) since sync events are less frequent.
   * Refreshes securities list, sparklines, and security chart if open.
   *
   * @param {Object} event - Event object with { type, data }
   * @param {Object} event.data - Sync data with isin and symbol
   */
  SECURITY_SYNCED: (event) => {
    if (!event) {
      console.warn('SECURITY_SYNCED event is null or undefined');
      return;
    }

    // Immediate refresh (no debounce) since sync events are infrequent
    useSecuritiesStore.getState().fetchSecurities();
    useSecuritiesStore.getState().fetchSparklines();

    // Refresh security chart if it's open for the synced security
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

  /**
   * Handles new security added events
   *
   * Immediately refreshes securities list to show the new security.
   *
   * @param {Object} event - Event object (data not used)
   */
  SECURITY_ADDED: () => {
    useSecuritiesStore.getState().fetchSecurities();
  },

  // ============================================================================
  // Portfolio Events
  // ============================================================================

  /**
   * Handles portfolio change events (positions, values, etc.)
   *
   * Debounced to batch multiple portfolio updates together.
   * Refreshes allocation and cash breakdown.
   *
   * @param {Object} event - Event object (data not used)
   */
  PORTFOLIO_CHANGED: () => {
    debounce('portfolio', () => {
      usePortfolioStore.getState().fetchAllocation();
      usePortfolioStore.getState().fetchCashBreakdown();
    }, 100);
  },

  /**
   * Handles trade execution events
   *
   * Immediately refreshes portfolio allocation, cash breakdown, and trades list.
   * Not debounced since trade executions are important and infrequent.
   *
   * @param {Object} event - Event object (data not used)
   */
  TRADE_EXECUTED: () => {
    usePortfolioStore.getState().fetchAllocation();
    usePortfolioStore.getState().fetchCashBreakdown();
    useTradesStore.getState().fetchTrades();
  },

  /**
   * Handles deposit processing events
   *
   * Immediately refreshes portfolio allocation and cash breakdown.
   *
   * @param {Object} event - Event object (data not used)
   */
  DEPOSIT_PROCESSED: () => {
    usePortfolioStore.getState().fetchAllocation();
    usePortfolioStore.getState().fetchCashBreakdown();
  },

  /**
   * Handles dividend creation events
   *
   * Immediately refreshes portfolio allocation and cash breakdown.
   *
   * @param {Object} event - Event object (data not used)
   */
  DIVIDEND_CREATED: () => {
    usePortfolioStore.getState().fetchAllocation();
    usePortfolioStore.getState().fetchCashBreakdown();
  },

  /**
   * Handles cash balance update events
   *
   * Immediately refreshes cash breakdown only (allocation unchanged).
   *
   * @param {Object} event - Event object (data not used)
   */
  CASH_UPDATED: () => {
    usePortfolioStore.getState().fetchCashBreakdown();
  },

  /**
   * Handles allocation target change events
   *
   * Immediately refreshes both targets and current allocation
   * to show the difference between target and actual.
   *
   * @param {Object} event - Event object (data not used)
   */
  ALLOCATION_TARGETS_CHANGED: () => {
    usePortfolioStore.getState().fetchTargets();
    usePortfolioStore.getState().fetchAllocation();
  },

  // ============================================================================
  // Recommendations Events
  // ============================================================================

  /**
   * Handles recommendations ready events
   *
   * Immediately fetches new recommendations from the planning system.
   *
   * @param {Object} event - Event object (data not used)
   */
  RECOMMENDATIONS_READY: () => {
    useAppStore.getState().fetchRecommendations();
  },

  /**
   * Handles trade plan generation events
   *
   * Immediately fetches recommendations (plan contains recommendations).
   *
   * @param {Object} event - Event object (data not used)
   */
  PLAN_GENERATED: () => {
    useAppStore.getState().fetchRecommendations();
  },

  // ============================================================================
  // System Status Events
  // ============================================================================

  /**
   * Handles system status change events
   *
   * Immediately fetches updated system status (health, uptime, etc.).
   *
   * @param {Object} event - Event object (data not used)
   */
  SYSTEM_STATUS_CHANGED: () => {
    useAppStore.getState().fetchStatus();
  },

  /**
   * Handles Tradernet broker connection status change events
   *
   * Immediately fetches updated Tradernet connection status.
   *
   * @param {Object} event - Event object (data not used)
   */
  TRADERNET_STATUS_CHANGED: () => {
    useAppStore.getState().fetchTradernet();
  },

  /**
   * Handles market status change events
   *
   * Updates markets state directly from event data (no API call needed).
   *
   * @param {Object} event - Event object with { type, data }
   * @param {Object} event.data - Market status data with markets object
   */
  MARKETS_STATUS_CHANGED: (event) => {
    if (!event || !event.data) {
      console.warn('MARKETS_STATUS_CHANGED event missing data');
      return;
    }
    // Update markets state directly from event data (more efficient than API call)
    useAppStore.setState({ markets: event.data.markets || {} });
  },

  // ============================================================================
  // Logs Events
  // ============================================================================
  // Logs events removed - logs now use HTTP polling instead of SSE for better
  // performance and to avoid overwhelming the event stream with log messages

  // ============================================================================
  // Settings Events
  // ============================================================================

  /**
   * Handles settings change events
   *
   * Immediately refreshes settings and security column visibility
   * (column visibility is stored in settings).
   *
   * @param {Object} event - Event object (data not used)
   */
  SETTINGS_CHANGED: () => {
    useSettingsStore.getState().fetchSettings();
    useSecuritiesStore.getState().fetchColumnVisibility();
  },

  /**
   * Handles planner configuration change events
   *
   * Currently just logs the event. Planner modal will refetch config
   * when opened, or a custom event can be emitted if needed.
   *
   * @param {Object} event - Event object (data not used)
   */
  PLANNER_CONFIG_CHANGED: () => {
    // Planner modal will refetch on open, or emit custom event
    // For now, just log it
    console.log('Planner config changed');
  },

  // ============================================================================
  // Job Lifecycle Events
  // ============================================================================

  /**
   * Handles job started events
   *
   * Adds the job to the running jobs list in the app store.
   *
   * @param {Object} event - Event object with { type, data }
   * @param {Object} event.data - Job data with job_id, job_type, description, timestamp
   */
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
      description: description || getJobDescription(job_type),  // Use provided description or lookup
      startedAt: new Date(timestamp).getTime(),
    });
  },

  /**
   * Handles job progress events
   *
   * Updates progress information for a running job.
   *
   * @param {Object} event - Event object with { type, data }
   * @param {Object} event.data - Progress data with job_id and progress object
   */
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

  /**
   * Handles job completion events
   *
   * Moves the job from running to completed and records duration.
   *
   * @param {Object} event - Event object with { type, data }
   * @param {Object} event.data - Completion data with job_id and duration
   */
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

  /**
   * Handles job failure events
   *
   * Moves the job from running to completed (with failed status)
   * and records error message and duration.
   *
   * @param {Object} event - Event object with { type, data }
   * @param {Object} event.data - Failure data with job_id, error, and duration
   */
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

  // ============================================================================
  // Connection Events
  // ============================================================================

  /**
   * Handles heartbeat events
   *
   * Heartbeat events indicate the SSE connection is alive.
   * No action needed - connection health is managed by the app store.
   *
   * @param {Object} event - Event object (not used)
   */
  heartbeat: () => {
    // Heartbeat received, connection is alive
  },

  /**
   * Handles connection established events
   *
   * Logs successful connection to the unified event stream.
   * Connection state is managed by the app store.
   *
   * @param {Object} event - Event object (not used)
   */
  connected: () => {
    console.log('Connected to unified event stream');
  },
};

/**
 * Main event handler function - routes events to appropriate handlers
 *
 * This function is called by the app store's event stream when a new event
 * is received. It looks up the appropriate handler and executes it safely.
 *
 * @param {Object} event - Event object from SSE stream
 * @param {string} event.type - Event type (e.g., 'PRICE_UPDATED', 'JOB_STARTED')
 * @param {Object} event.data - Event data (structure varies by event type)
 */
export function handleEvent(event) {
  const { type, data } = event;

  // Validate event has a type
  if (!type) {
    console.warn('Received event without type:', event);
    return;
  }

  // Look up handler for this event type
  const handler = eventHandlers[type];
  if (handler) {
    try {
      // Execute handler with event object
      handler({ type, data });
    } catch (error) {
      // Log errors but don't crash - event handling failures shouldn't break the app
      console.error(`Error handling event ${type}:`, error);
    }
  } else {
    // Unknown event type - log for debugging but don't error
    console.debug(`No handler for event type: ${type}`);
  }
}
