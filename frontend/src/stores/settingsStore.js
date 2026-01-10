import { create } from 'zustand';
import { api } from '../api/client';

export const useSettingsStore = create((set, get) => ({
  // Settings
  settings: {
    limit_order_buffer_percent: 0.05,
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
    const { settings, tradingMode } = get();
    const oldValue = settings[key];
    const oldTradingMode = tradingMode;

    // Optimistic update - apply immediately for better UX
    set({ settings: { ...settings, [key]: value } });
    if (key === 'trading_mode') {
      set({ tradingMode: value });
    }

    try {
      await api.updateSetting(key, value);
    } catch (e) {
      console.error(`Failed to update setting ${key}:`, e);
      // Rollback on error
      set({ settings: { ...settings, [key]: oldValue } });
      if (key === 'trading_mode') {
        set({ tradingMode: oldTradingMode });
      }
      throw e;
    }
  },

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
