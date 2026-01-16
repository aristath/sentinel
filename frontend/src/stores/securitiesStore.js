/**
 * Securities State Store (Zustand)
 *
 * Manages the investment universe (securities), their scores, sparklines,
 * filtering, sorting, and column visibility preferences.
 *
 * Features:
 * - Security list with scores and metadata
 * - Sparkline charts for price trends
 * - Filtering by geography, industry, search query, minimum score
 * - Sorting by various fields
 * - Column visibility preferences (persisted to settings)
 * - Score refresh (single or all securities)
 */
import { create } from 'zustand';
import { notifications } from '@mantine/notifications';
import { api } from '../api/client';

/**
 * Default column visibility settings - all columns visible by default
 * @type {Object<string, boolean>}
 */
const DEFAULT_VISIBLE_COLUMNS = {
  chart: true,      // Sparkline chart
  company: true,    // Company name
  geography: true,  // Geographic region
  exchange: true,   // Stock exchange
  sector: true,     // Industry sector
  tags: true,       // Security tags
  value: true,      // Portfolio value
  score: true,      // Priority score
  mult: true,       // Priority multiplier
  bs: true,         // Buy/sell signal
  priority: true,   // Priority ranking
};

/**
 * Securities store created with Zustand
 *
 * @type {Function} useSecuritiesStore - Hook to access securities store state and actions
 */
export const useSecuritiesStore = create((set, get) => ({
  // ============================================================================
  // Securities Data
  // ============================================================================

  /**
   * Array of all securities in the investment universe
   * @type {Array<Object>}
   */
  securities: [],

  /**
   * Sparkline data for securities (mini price charts)
   * Map: ISIN -> array of price points
   * @type {Object<string, Array>}
   */
  sparklines: {},

  /**
   * Sparkline timeframe ('1Y' for 1 year, '5Y' for 5 years)
   * @type {string}
   */
  sparklineTimeframe: '1Y',

  // ============================================================================
  // Filters and Sorting
  // ============================================================================

  /**
   * Geography filter ('all' or specific geography name)
   * @type {string}
   */
  securityFilter: 'all',

  /**
   * Industry filter ('all' or specific industry name)
   * @type {string}
   */
  industryFilter: 'all',

  /**
   * Search query for filtering by symbol or name
   * @type {string}
   */
  searchQuery: '',

  /**
   * Minimum priority score filter (0 = no filter)
   * @type {number}
   */
  minScore: 0,

  /**
   * Field to sort by (e.g., 'priority_score', 'symbol', 'value')
   * @type {string}
   */
  sortBy: 'priority_score',

  /**
   * Whether to sort in descending order
   * @type {boolean}
   */
  sortDesc: true,

  // ============================================================================
  // Column Visibility
  // ============================================================================

  /**
   * Column visibility preferences (persisted to settings)
   * @type {Object<string, boolean>}
   */
  visibleColumns: DEFAULT_VISIBLE_COLUMNS,

  // ============================================================================
  // Loading States
  // ============================================================================

  /**
   * Loading state flags for async operations
   * @type {Object}
   */
  loading: {
    scores: false,        // Refreshing security scores
    refreshData: false,   // Refreshing all data
    securitySave: false,  // Saving security data
  },

  // ============================================================================
  // Data Fetching Actions
  // ============================================================================

  /**
   * Fetches all securities from the investment universe
   * Updates the securities array with latest data including scores and metadata
   */
  fetchSecurities: async () => {
    try {
      const securities = await api.fetchSecurities();
      set({ securities });
    } catch (e) {
      console.error('Failed to fetch securities:', e);
    }
  },

  /**
   * Fetches sparkline data for all securities
   * Uses the current sparklineTimeframe setting
   */
  fetchSparklines: async () => {
    try {
      const { sparklineTimeframe } = get();
      const sparklines = await api.fetchSparklines(sparklineTimeframe);
      set({ sparklines });
    } catch (e) {
      console.error('Failed to fetch sparklines:', e);
    }
  },

  /**
   * Sets the sparkline timeframe and refetches data
   *
   * @param {string} timeframe - Timeframe ('1Y' or '5Y')
   */
  setSparklineTimeframe: (timeframe) => {
    set({ sparklineTimeframe: timeframe });
    get().fetchSparklines(); // Refetch with new timeframe
  },

  // ============================================================================
  // Filter and Sort Actions
  // ============================================================================

  /**
   * Sets the geography filter
   * @param {string} filter - Geography name or 'all'
   */
  setSecurityFilter: (filter) => set({ securityFilter: filter }),

  /**
   * Sets the industry filter
   * @param {string} filter - Industry name or 'all'
   */
  setIndustryFilter: (filter) => set({ industryFilter: filter }),

  /**
   * Sets the search query (filters by symbol or name)
   * @param {string} query - Search query string
   */
  setSearchQuery: (query) => set({ searchQuery: query }),

  /**
   * Sets the minimum score filter
   * @param {number} score - Minimum priority score (0 = no filter)
   */
  setMinScore: (score) => set({ minScore: score }),

  /**
   * Sets the sort field and direction
   * @param {string} field - Field name to sort by
   * @param {boolean} desc - Whether to sort descending (default: true)
   */
  setSortBy: (field, desc = true) => set({ sortBy: field, sortDesc: desc }),

  /**
   * Gets filtered and sorted securities based on current filter settings
   *
   * Applies all active filters (geography, industry, search, min score)
   * and sorts by the configured field and direction.
   *
   * @returns {Array<Object>} Filtered and sorted array of securities
   */
  getFilteredSecurities: () => {
    const { securities, securityFilter, industryFilter, searchQuery, minScore, sortBy, sortDesc } = get();

    // Start with a copy of all securities
    let filtered = [...securities];

    // Filter by geography
    if (securityFilter !== 'all') {
      filtered = filtered.filter(s => s.geography === securityFilter);
    }

    // Filter by industry
    if (industryFilter !== 'all') {
      filtered = filtered.filter(s => s.industry === industryFilter);
    }

    // Filter by search query (case-insensitive search in symbol or name)
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(s =>
        s.symbol?.toLowerCase().includes(query) ||
        s.name?.toLowerCase().includes(query)
      );
    }

    // Filter by minimum score
    if (minScore > 0) {
      filtered = filtered.filter(s => (s.priority_score || 0) >= minScore);
    }

    // Sort by configured field and direction
    filtered.sort((a, b) => {
      const aVal = a[sortBy] ?? 0;
      const bVal = b[sortBy] ?? 0;
      if (sortDesc) {
        // Descending: higher values first
        return bVal > aVal ? 1 : bVal < aVal ? -1 : 0;
      }
      // Ascending: lower values first
      return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
    });

    return filtered;
  },

  // ============================================================================
  // Score Refresh Actions
  // ============================================================================

  /**
   * Refreshes the score for a single security
   *
   * Triggers score recalculation on the backend and refreshes the securities list.
   * Shows success/error notification.
   *
   * @param {string} isin - Security ISIN identifier
   */
  refreshScore: async (isin) => {
    set({ loading: { ...get().loading, scores: true } });
    try {
      await api.refreshScore(isin);
      await get().fetchSecurities();
      notifications.show({
        title: 'Score refreshed',
        message: 'Security score updated successfully',
        color: 'green',
      });
    } catch (e) {
      console.error('Failed to refresh score:', e);
      notifications.show({
        title: 'Score refresh failed',
        message: e.message || 'Failed to refresh security score',
        color: 'red',
      });
    } finally {
      set({ loading: { ...get().loading, scores: false } });
    }
  },

  /**
   * Refreshes scores for all securities in the universe
   *
   * Triggers score recalculation for all securities on the backend.
   * This can take a while for large universes. Shows success/error notification.
   */
  refreshAllScores: async () => {
    set({ loading: { ...get().loading, scores: true } });
    try {
      await api.refreshAllScores();
      await get().fetchSecurities();
      notifications.show({
        title: 'All scores refreshed',
        message: 'All security scores updated successfully',
        color: 'green',
      });
    } catch (e) {
      console.error('Failed to refresh all scores:', e);
      notifications.show({
        title: 'Score refresh failed',
        message: e.message || 'Failed to refresh all scores',
        color: 'red',
      });
    } finally {
      set({ loading: { ...get().loading, scores: false } });
    }
  },

  // ============================================================================
  // Security Management Actions
  // ============================================================================

  /**
   * Removes a security from the investment universe
   *
   * Shows confirmation dialog before deletion. Refreshes securities list after removal.
   *
   * @param {string} isin - Security ISIN identifier
   */
  removeSecurity: async (isin) => {
    const { securities } = get();
    const security = securities.find(s => s.isin === isin);
    const displaySymbol = security ? security.symbol : isin;
    // Confirm deletion with user
    if (!confirm(`Remove ${displaySymbol} from the universe?`)) return;
    try {
      await api.deleteSecurity(isin);
      await get().fetchSecurities();
      notifications.show({
        title: 'Success',
        message: `${displaySymbol} removed from universe`,
        color: 'green',
      });
    } catch (e) {
      console.error('Failed to remove security:', e);
      notifications.show({
        title: 'Error',
        message: 'Failed to remove security',
        color: 'red',
      });
    }
  },

  /**
   * Updates the priority multiplier for a security
   *
   * Multiplier adjusts the priority score (0.1 to 3.0 range).
   * Clamps value to valid range before saving.
   *
   * @param {string} isin - Security ISIN identifier
   * @param {number|string} value - New multiplier value
   */
  updateMultiplier: async (isin, value) => {
    // Clamp multiplier to valid range (0.1 to 3.0)
    const multiplier = Math.max(0.1, Math.min(3.0, parseFloat(value) || 1.0));
    try {
      await api.updateSecurity(isin, { priority_multiplier: multiplier });
      await get().fetchSecurities();
    } catch (e) {
      console.error('Failed to update multiplier:', e);
      notifications.show({
        title: 'Error',
        message: 'Failed to update multiplier',
        color: 'red',
      });
    }
  },

  // ============================================================================
  // Column Visibility Actions
  // ============================================================================

  /**
   * Fetches column visibility preferences from settings
   *
   * Loads saved preferences and merges with defaults to handle new columns
   * that may have been added since preferences were saved.
   */
  fetchColumnVisibility: async () => {
    try {
      const settings = await api.fetchSettings();
      const columnsJson = settings.security_table_visible_columns;
      if (columnsJson) {
        try {
          const parsed = JSON.parse(columnsJson);
          // Merge with defaults to handle new columns that weren't in saved preferences
          set({ visibleColumns: { ...DEFAULT_VISIBLE_COLUMNS, ...parsed } });
        } catch (e) {
          console.error('Failed to parse column visibility:', e);
          set({ visibleColumns: DEFAULT_VISIBLE_COLUMNS });
        }
      } else {
        // No saved preferences - use defaults
        set({ visibleColumns: DEFAULT_VISIBLE_COLUMNS });
      }
    } catch (e) {
      console.error('Failed to fetch column visibility:', e);
      set({ visibleColumns: DEFAULT_VISIBLE_COLUMNS });
    }
  },

  /**
   * Toggles visibility of a column and persists to settings
   *
   * Updates local state immediately for responsive UI, then persists to backend.
   * Reverts local state if persistence fails.
   *
   * @param {string} columnKey - Column identifier (e.g., 'chart', 'score', 'value')
   */
  toggleColumnVisibility: async (columnKey) => {
    const { visibleColumns } = get();
    const newVisibility = {
      ...visibleColumns,
      [columnKey]: !visibleColumns[columnKey],
    };

    // Update local state immediately for responsive UI
    set({ visibleColumns: newVisibility });

    // Persist to settings (stored as JSON string)
    try {
      await api.updateSetting('security_table_visible_columns', JSON.stringify(newVisibility));
    } catch (e) {
      console.error('Failed to save column visibility:', e);
      // Revert on error to keep UI in sync with backend
      set({ visibleColumns });
      notifications.show({
        title: 'Error',
        message: 'Failed to save column visibility preference',
        color: 'red',
      });
    }
  },
}));
