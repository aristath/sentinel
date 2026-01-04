import { create } from 'zustand';
import { api } from '../api/client';

export const useTradesStore = create((set) => ({
  trades: [],

  fetchTrades: async () => {
    try {
      const trades = await api.fetchTrades();
      set({ trades });
    } catch (e) {
      console.error('Failed to fetch trades:', e);
    }
  },
}));

