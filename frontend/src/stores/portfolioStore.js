/**
 * Portfolio State Store (Zustand)
 *
 * Manages portfolio allocation data, targets, and cash breakdown.
 * Handles geography and industry allocation targets with editing capabilities.
 *
 * Features:
 * - Current portfolio allocation (geography, industry, total value, cash)
 * - Allocation targets (desired percentages)
 * - Cash breakdown (available, pending, allocated, etc.)
 * - Concentration alerts
 * - Edit mode for targets with slider adjustments
 */
import { create } from 'zustand';
import { api } from '../api/client';

/**
 * Portfolio store created with Zustand
 *
 * @type {Function} usePortfolioStore - Hook to access portfolio store state and actions
 */
export const usePortfolioStore = create((set, get) => ({
  // ============================================================================
  // Portfolio Data
  // ============================================================================

  /**
   * Current portfolio allocation data
   * @type {Object}
   * @property {Array} geography - Geography allocation percentages
   * @property {Array} industry - Industry allocation percentages
   * @property {number} total_value - Total portfolio value
   * @property {number} cash_balance - Available cash balance
   */
  allocation: {
    geography: [],
    industry: [],
    total_value: 0,
    cash_balance: 0,
  },

  /**
   * Concentration alerts (warnings about over-concentration)
   * @type {Array}
   */
  alerts: [],

  /**
   * Cash breakdown by category (available, pending, allocated, etc.)
   * @type {Array}
   */
  cashBreakdown: [],

  // ============================================================================
  // Geography Allocation
  // ============================================================================

  /**
   * Available geography options (from active securities)
   * @type {Array<string>}
   */
  geographies: [],

  /**
   * Geography allocation targets (desired percentages)
   * Map: geography name -> target percentage (0.0 to 1.0)
   * @type {Object<string, number>}
   */
  geographyTargets: {},

  /**
   * Whether geography targets are currently being edited
   * @type {boolean}
   */
  editingGeography: false,

  /**
   * Active geographies (geographies present in current portfolio)
   * @type {Array<string>}
   */
  activeGeographies: [],

  // ============================================================================
  // Industry Allocation
  // ============================================================================

  /**
   * Available industry options (from active securities)
   * @type {Array<string>}
   */
  industries: [],

  /**
   * Industry allocation targets (desired percentages)
   * Map: industry name -> target percentage (0.0 to 1.0)
   * @type {Object<string, number>}
   */
  industryTargets: {},

  /**
   * Whether industry targets are currently being edited
   * @type {boolean}
   */
  editingIndustry: false,

  /**
   * Active industries (industries present in current portfolio)
   * @type {Array<string>}
   */
  activeIndustries: [],

  // ============================================================================
  // Loading States
  // ============================================================================

  /**
   * Loading state flags for async operations
   * @type {Object}
   */
  loading: {
    geographySave: false,  // Saving geography targets
    industrySave: false,    // Saving industry targets
  },

  // ============================================================================
  // Data Fetching Actions
  // ============================================================================

  /**
   * Fetches current portfolio allocation data
   *
   * Retrieves actual allocation percentages, total value, cash balance,
   * and concentration alerts from the backend.
   */
  fetchAllocation: async () => {
    try {
      const data = await api.fetchAllocation();
      set({
        allocation: {
          geography: data.geography || [],
          industry: data.industry || [],
          total_value: data.total_value || 0,
          cash_balance: data.cash_balance || 0,
        },
        alerts: data.alerts || [],
      });
    } catch (e) {
      console.error('Failed to fetch allocation:', e);
    }
  },

  /**
   * Fetches cash breakdown by category
   *
   * Retrieves detailed cash information (available, pending, allocated, etc.)
   * for display in the cash breakdown view.
   */
  fetchCashBreakdown: async () => {
    try {
      const data = await api.fetchCashBreakdown();
      set({ cashBreakdown: data.balances || [] });
    } catch (e) {
      console.error('Failed to fetch cash breakdown:', e);
    }
  },

  /**
   * Fetches allocation targets and available options
   *
   * Fetches in parallel:
   * - Saved allocation targets (desired percentages)
   * - Available geographies (from active securities)
   * - Available industries (from active securities)
   *
   * Updates both target values and available options for the UI.
   */
  fetchTargets: async () => {
    try {
      // Fetch targets and available options in parallel for efficiency
      const [targets, availableGeo, availableInd] = await Promise.all([
        api.fetchTargets(),
        api.fetchAvailableGeographies(),
        api.fetchAvailableIndustries(),
      ]);

      // Available geographies/industries come from active securities in the universe
      const activeGeographies = availableGeo.geographies || [];
      const activeIndustries = availableInd.industries || [];

      // Targets are the saved weights (desired allocation percentages)
      const geographyTargets = {};
      const industryTargets = {};

      // Convert target arrays to objects for easier manipulation
      for (const [name, weight] of Object.entries(targets.geography || {})) {
        geographyTargets[name] = weight;
      }
      for (const [name, weight] of Object.entries(targets.industry || {})) {
        industryTargets[name] = weight;
      }

      set({
        geographies: activeGeographies,
        geographyTargets,
        industries: activeIndustries,
        industryTargets,
        activeGeographies,
        activeIndustries,
      });
    } catch (e) {
      console.error('Failed to fetch targets:', e);
    }
  },

  // ============================================================================
  // Geography Target Actions
  // ============================================================================

  /**
   * Enters geography target editing mode
   * Enables UI for adjusting geography allocation sliders
   */
  startEditGeography: () => set({ editingGeography: true }),

  /**
   * Cancels geography target editing
   * Discards unsaved changes and exits edit mode
   */
  cancelEditGeography: () => set({ editingGeography: false }),

  /**
   * Adjusts a geography target slider value
   * Updates the target percentage for a specific geography
   *
   * @param {string} name - Geography name
   * @param {number} value - Target percentage (0.0 to 1.0)
   */
  adjustGeographySlider: (name, value) => {
    const { geographyTargets } = get();
    set({ geographyTargets: { ...geographyTargets, [name]: value } });
  },

  /**
   * Saves geography allocation targets to the backend
   *
   * Saves targets, then refreshes targets and allocation to show updated values.
   * Exits edit mode on success. Loading state is always reset, even on error.
   *
   * @throws {Error} Re-throws errors so components can handle them
   */
  saveGeographyTargets: async () => {
    set({ loading: { ...get().loading, geographySave: true } });
    try {
      await api.saveGeographyTargets(get().geographyTargets);
      // Refresh targets and allocation to show updated values
      await get().fetchTargets();
      await get().fetchAllocation();
      set({ editingGeography: false });
      // Notification will be shown via appStore.showMessage if needed
    } catch (e) {
      console.error('Failed to save geography targets:', e);
      throw e; // Re-throw so components can handle it
    } finally {
      // Ensure loading flag is ALWAYS reset, even if state update fails
      // This prevents the UI from getting stuck in loading state
      try {
        set({ loading: { ...get().loading, geographySave: false } });
      } catch (finallyError) {
        console.error('Failed to reset loading state:', finallyError);
      }
    }
  },

  // ============================================================================
  // Industry Target Actions
  // ============================================================================

  /**
   * Enters industry target editing mode
   * Enables UI for adjusting industry allocation sliders
   */
  startEditIndustry: () => set({ editingIndustry: true }),

  /**
   * Cancels industry target editing
   * Discards unsaved changes and exits edit mode
   */
  cancelEditIndustry: () => set({ editingIndustry: false }),

  /**
   * Adjusts an industry target slider value
   * Updates the target percentage for a specific industry
   *
   * @param {string} name - Industry name
   * @param {number} value - Target percentage (0.0 to 1.0)
   */
  adjustIndustrySlider: (name, value) => {
    const { industryTargets } = get();
    set({ industryTargets: { ...industryTargets, [name]: value } });
  },

  /**
   * Saves industry allocation targets to the backend
   *
   * Saves targets, then refreshes targets and allocation to show updated values.
   * Exits edit mode on success. Loading state is always reset, even on error.
   *
   * @throws {Error} Re-throws errors so components can handle them
   */
  saveIndustryTargets: async () => {
    set({ loading: { ...get().loading, industrySave: true } });
    try {
      await api.saveIndustryTargets(get().industryTargets);
      // Refresh targets and allocation to show updated values
      await get().fetchTargets();
      await get().fetchAllocation();
      set({ editingIndustry: false });
      // Notification will be shown via appStore.showMessage if needed
    } catch (e) {
      console.error('Failed to save industry targets:', e);
      throw e; // Re-throw so components can handle it
    } finally {
      // Ensure loading flag is ALWAYS reset, even if state update fails
      // This prevents the UI from getting stuck in loading state
      try {
        set({ loading: { ...get().loading, industrySave: false } });
      } catch (finallyError) {
        console.error('Failed to reset loading state:', finallyError);
      }
    }
  },

  // ============================================================================
  // Test Cash Management
  // ============================================================================

  /**
   * Updates virtual test cash amount (for paper trading/testing)
   *
   * Updates the setting and refreshes cash breakdown and allocation
   * to reflect the new test cash amount.
   *
   * @param {number} amount - New test cash amount
   * @throws {Error} Re-throws errors so components can handle them
   */
  updateTestCash: async (amount) => {
    try {
      await api.updateSetting('virtual_test_cash', amount);
      // Refresh cash breakdown to reflect the updated value
      await get().fetchCashBreakdown();
      // Also refresh allocation to update total cash balance
      await get().fetchAllocation();
    } catch (e) {
      console.error('Failed to update TEST cash:', e);
      throw e; // Re-throw so components can handle it
    }
  },
}));
