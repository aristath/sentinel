/**
 * Settings State Store (Zustand)
 *
 * Manages application settings and trading mode.
 * Uses optimistic updates for better UX - changes are applied immediately
 * and rolled back if the API call fails.
 *
 * Features:
 * - Application settings (limit order buffer, display mode, etc.)
 * - Trading mode (research/paper vs live trading)
 * - Optimistic updates with rollback on error
 */
import { create } from 'zustand';
import { api } from '../api/client';

/**
 * Settings store created with Zustand
 *
 * @type {Function} useSettingsStore - Hook to access settings store state and actions
 */
export const useSettingsStore = create((set, get) => ({
  // ============================================================================
  // State
  // ============================================================================

  /**
   * Application settings object
   * Contains all configurable settings (limit order buffer, display mode, etc.)
   * @type {Object}
   */
  settings: {
    limit_order_buffer_percent: 0.05,  // Default 5% buffer for limit orders
  },

  /**
   * Current trading mode ('research' for paper trading, 'live' for real trading)
   * @type {string}
   */
  tradingMode: 'research',

  // ============================================================================
  // Actions
  // ============================================================================

  /**
   * Fetches all settings from the backend
   *
   * Updates both settings object and tradingMode from the response.
   */
  fetchSettings: async () => {
    try {
      const settings = await api.fetchSettings();
      set({
        settings,
        tradingMode: settings.trading_mode || 'research',
      });
    } catch (e) {
      console.error('Failed to fetch settings:', e);
    }
  },

  /**
   * Updates a single setting value
   *
   * Uses optimistic update pattern:
   * 1. Updates local state immediately (better UX)
   * 2. Sends update to backend
   * 3. Rolls back on error
   *
   * @param {string} key - Setting key name
   * @param {any} value - New setting value
   * @throws {Error} Re-throws errors so components can handle them
   */
  updateSetting: async (key, value) => {
    const { settings, tradingMode } = get();
    const oldValue = settings[key];
    const oldTradingMode = tradingMode;

    // Optimistic update - apply immediately for better UX
    set({ settings: { ...settings, [key]: value } });
    // Also update tradingMode if this is the trading_mode setting
    if (key === 'trading_mode') {
      set({ tradingMode: value });
    }

    try {
      await api.updateSetting(key, value);
    } catch (e) {
      console.error(`Failed to update setting ${key}:`, e);
      // Rollback on error - restore previous values
      set({ settings: { ...settings, [key]: oldValue } });
      if (key === 'trading_mode') {
        set({ tradingMode: oldTradingMode });
      }
      throw e;
    }
  },

  /**
   * Toggles trading mode between 'live' and 'research'
   *
   * Uses optimistic update pattern - toggles immediately, then syncs with backend.
   * Rolls back on error.
   *
   * @throws {Error} Re-throws errors so components can handle them
   */
  toggleTradingMode: async () => {
    const { tradingMode } = get();
    const oldMode = tradingMode;
    const newMode = tradingMode === 'live' ? 'research' : 'live';

    // Optimistic update - toggle immediately
    set({ tradingMode: newMode });

    try {
      await api.toggleTradingMode();
    } catch (e) {
      console.error('Failed to toggle trading mode:', e);
      // Rollback on error
      set({ tradingMode: oldMode });
      throw e;
    }
  },
}));
