/**
 * Logs State Store (Zustand)
 *
 * Manages system log entries, filtering, search, and auto-refresh functionality.
 * Uses HTTP polling to fetch logs (not SSE) to avoid overwhelming the event stream.
 *
 * Features:
 * - Parse raw log lines into structured objects
 * - Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
 * - Search logs by text query
 * - Show errors only mode
 * - Auto-refresh with configurable interval
 * - Configurable line count (50-1000)
 */
import { create } from 'zustand';
import { api } from '../api/client';

/**
 * Parses a raw log line string into a structured log object
 *
 * Handles journalctl-style log format:
 * "Jan 11 10:30:00 hostname sentinel: [LEVEL] message"
 *
 * Extracts:
 * - Timestamp (parses journalctl short format, adds current year)
 * - Log level (from [LEVEL] or LEVEL: prefix)
 * - Message (remaining text)
 *
 * @param {string} line - Raw log line string
 * @returns {Object} Parsed log object with { timestamp, level, message }
 */
function parseLogLine(line) {
  // Format: "Jan 11 10:30:00 hostname sentinel: [LEVEL] message" or similar
  const parts = line.split(': ');
  if (parts.length < 2) {
    // Malformed line - return with defaults
    return {
      timestamp: new Date().toISOString(),
      level: 'INFO',
      message: line,
    };
  }

  // Split into date/host/service part and message part
  const [dateHostService, ...messageParts] = parts;
  const message = messageParts.join(': ');  // Rejoin in case message contains colons

  // Extract log level from message
  // Try [LEVEL] format first, then LEVEL: prefix format
  let level = 'INFO';  // Default level
  const levelMatch = message.match(/\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]/) ||
    message.match(/^(DEBUG|INFO|WARNING|ERROR|CRITICAL):/i);
  if (levelMatch) {
    level = levelMatch[1].toUpperCase();
  }

  // Try to parse timestamp from the date part
  // Format is typically "Jan 11 10:30:00" or similar (journalctl short format)
  // Journalctl short format: MMM DD HH:MM:SS (no year, assumes current year)
  const dateMatch = dateHostService.match(/^(\w+ \d+ \d+:\d+:\d+)/);
  let timestamp = new Date().toISOString(); // Default to current time

  if (dateMatch) {
    const dateStr = dateMatch[1];
    // Parse date string like "Jan 11 16:25:36"
    // Add current year since journalctl short format doesn't include it
    const now = new Date();
    const year = now.getFullYear();
    const fullDateStr = `${dateStr} ${year}`;
    const parsedDate = new Date(fullDateStr);

    // Validate the parsed date (check if parsing succeeded)
    if (!isNaN(parsedDate.getTime())) {
      timestamp = parsedDate.toISOString();
    }
  }

  return {
    timestamp,
    level,
    message,
  };
}

/**
 * Logs store created with Zustand
 *
 * @type {Function} useLogsStore - Hook to access logs store state and actions
 */
export const useLogsStore = create((set, get) => ({
  // ============================================================================
  // State
  // ============================================================================

  /**
   * Array of parsed log entries (structured objects)
   * @type {Array<Object>}
   */
  entries: [],

  /**
   * Log level filter (null = all levels, or 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
   * @type {string|null}
   */
  filterLevel: null,

  /**
   * Search query string for filtering log messages
   * @type {string}
   */
  searchQuery: '',

  /**
   * Number of log lines to fetch (50-1000, clamped)
   * @type {number}
   */
  lineCount: 100,

  /**
   * Whether to show only error-level logs
   * @type {boolean}
   */
  showErrorsOnly: false,

  /**
   * Whether auto-refresh is enabled (HTTP polling)
   * @type {boolean}
   */
  autoRefresh: true,

  /**
   * Auto-refresh interval in milliseconds (default: 10 seconds)
   * @type {number}
   */
  refreshInterval: 10000,

  /**
   * Whether logs are currently being fetched
   * @type {boolean}
   */
  loading: false,

  /**
   * Interval timer ID for auto-refresh
   * @type {number|null}
   */
  refreshTimer: null,

  /**
   * Total number of log lines available (from backend)
   * @type {number}
   */
  totalLines: 0,

  // ============================================================================
  // Actions
  // ============================================================================

  /**
   * Fetches logs from the backend API
   *
   * Uses current filter settings (level, search query, line count, errors-only).
   * Parses raw log lines into structured objects and updates the store.
   */
  fetchLogs: async () => {
    const { filterLevel, searchQuery, lineCount, showErrorsOnly } = get();
    set({ loading: true });

    try {
      let data;
      if (showErrorsOnly) {
        // Fetch only error-level logs
        data = await api.fetchErrorLogs(lineCount);
      } else {
        // Fetch logs with filters
        data = await api.fetchLogs(lineCount, filterLevel, searchQuery || null);
      }

      // Parse raw log lines into structured objects
      const parsedEntries = (data.lines || []).map(parseLogLine);

      set({
        entries: parsedEntries,
        totalLines: data.total || 0,
        loading: false,
      });
    } catch (e) {
      console.error('Failed to fetch logs:', e);
      set({ loading: false });
    }
  },

  /**
   * Starts auto-refresh timer for periodic log fetching
   *
   * Clears any existing timer before creating a new one.
   * Fetches logs at the configured refreshInterval.
   */
  startAutoRefresh: () => {
    const { refreshTimer, refreshInterval } = get();
    // Clear existing timer if present
    if (refreshTimer) {
      clearInterval(refreshTimer);
    }

    // Create new interval timer
    const timer = setInterval(() => {
      get().fetchLogs();
    }, refreshInterval);

    set({ refreshTimer: timer });
  },

  /**
   * Stops auto-refresh timer
   *
   * Clears the interval and resets the timer ID.
   */
  stopAutoRefresh: () => {
    const { refreshTimer } = get();
    if (refreshTimer) {
      clearInterval(refreshTimer);
      set({ refreshTimer: null });
    }
  },

  /**
   * Sets the log level filter
   *
   * 'all' is converted to null (no filter).
   * Automatically refetches logs with the new filter.
   *
   * @param {string} level - Log level ('all', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
   */
  setFilterLevel: (level) => {
    set({ filterLevel: level === 'all' ? null : level });
    get().fetchLogs();
  },

  /**
   * Sets the search query string
   *
   * Does not automatically fetch logs - debouncing is handled by the component
   * to prevent excessive API calls while typing.
   *
   * @param {string} query - Search query string
   */
  setSearchQuery: (query) => {
    set({ searchQuery: query });
    // Debounce is handled by the component
  },

  /**
   * Sets the number of log lines to fetch
   *
   * Clamps the value between 50 and 1000 to prevent excessive API calls.
   * Automatically refetches logs with the new line count.
   *
   * @param {number} count - Number of lines to fetch (50-1000)
   */
  setLineCount: (count) => {
    set({ lineCount: Math.max(50, Math.min(1000, count || 100)) });
    get().fetchLogs();
  },

  /**
   * Sets whether to show only error-level logs
   *
   * When enabled, fetches only error logs (ignores other filters).
   * Automatically refetches logs.
   *
   * @param {boolean} show - Whether to show errors only
   */
  setShowErrorsOnly: (show) => {
    set({ showErrorsOnly: show });
    get().fetchLogs();
  },

  /**
   * Enables or disables auto-refresh
   *
   * Starts or stops the auto-refresh timer accordingly.
   *
   * @param {boolean} enabled - Whether to enable auto-refresh
   */
  setAutoRefresh: (enabled) => {
    set({ autoRefresh: enabled });
    if (enabled) {
      get().startAutoRefresh();
    } else {
      get().stopAutoRefresh();
    }
  },
}));
