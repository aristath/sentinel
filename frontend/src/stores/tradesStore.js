/**
 * Trades State Store (Zustand)
 *
 * Manages executed trades and pending orders data.
 * Provides methods to fetch trades and pending orders from the backend.
 *
 * Features:
 * - Executed trades history
 * - Pending orders (orders submitted but not yet executed)
 * - Batch fetching for efficiency
 */
import { create } from 'zustand';
import { api } from '../api/client';

/**
 * Trades store created with Zustand
 *
 * @type {Function} useTradesStore - Hook to access trades store state and actions
 */
export const useTradesStore = create((set) => ({
  // ============================================================================
  // State
  // ============================================================================

  /**
   * Array of executed trades
   * @type {Array<Object>}
   */
  trades: [],

  /**
   * Array of pending orders (orders submitted but not yet executed)
   * @type {Array<Object>}
   */
  pendingOrders: [],

  // ============================================================================
  // Actions
  // ============================================================================

  /**
   * Fetches executed trades from the backend
   *
   * Updates the trades array with the latest trade history.
   */
  fetchTrades: async () => {
    try {
      const trades = await api.fetchTrades();
      set({ trades });
    } catch (e) {
      console.error('Failed to fetch trades:', e);
    }
  },

  /**
   * Fetches pending orders from the backend
   *
   * Updates the pendingOrders array with orders that have been submitted
   * but not yet executed by the broker.
   */
  fetchPendingOrders: async () => {
    try {
      const response = await api.fetchPendingOrders();
      // Check for success flag and pending_orders array in response
      if (response.success && response.pending_orders) {
        set({ pendingOrders: response.pending_orders });
      }
    } catch (e) {
      console.error('Failed to fetch pending orders:', e);
    }
  },

  /**
   * Fetches both trades and pending orders in parallel
   *
   * More efficient than calling fetchTrades and fetchPendingOrders separately.
   * Used for initial data loading.
   */
  fetchAll: async () => {
    try {
      // Fetch both in parallel for efficiency
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
