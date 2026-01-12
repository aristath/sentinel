import { create } from 'zustand';
import { api } from '../api/client';

export const useTradesStore = create((set) => ({
  trades: [],
  pendingOrders: [],

  fetchTrades: async () => {
    try {
      const trades = await api.fetchTrades();
      set({ trades });
    } catch (e) {
      console.error('Failed to fetch trades:', e);
    }
  },

  fetchPendingOrders: async () => {
    try {
      const response = await api.fetchPendingOrders();
      if (response.success && response.pending_orders) {
        set({ pendingOrders: response.pending_orders });
      }
    } catch (e) {
      console.error('Failed to fetch pending orders:', e);
    }
  },

  fetchAll: async () => {
    try {
      const [trades, pendingResponse] = await Promise.all([
        api.fetchTrades(),
        api.fetchPendingOrders(),
      ]);
      set({
        trades,
        pendingOrders: pendingResponse.success ? pendingResponse.pending_orders : [],
      });
    } catch (e) {
      console.error('Failed to fetch trades and pending orders:', e);
    }
  },
}));
