import { create } from 'zustand';
import { api } from '../api/client';

export const useSettingsStore = create((set, get) => ({
  // Settings
  settings: {
    optimizer_blend: 0.5,
    optimizer_target_return: 0.11,
    transaction_cost_fixed: 2.0,
    transaction_cost_percent: 0.002,
    min_cash_reserve: 500.0,
  },
  tradingMode: 'research',

  // Actions
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

  updateSetting: async (key, value) => {
    try {
      await api.updateSetting(key, value);
      const { settings } = get();
      set({ settings: { ...settings, [key]: value } });
      if (key === 'trading_mode') {
        set({ tradingMode: value });
      }
    } catch (e) {
      console.error(`Failed to update setting ${key}:`, e);
      throw e;
    }
  },

  toggleTradingMode: async () => {
    try {
      await api.toggleTradingMode();
      const { tradingMode } = get();
      set({ tradingMode: tradingMode === 'live' ? 'research' : 'live' });
    } catch (e) {
      console.error('Failed to toggle trading mode:', e);
      throw e;
    }
  },
}));
