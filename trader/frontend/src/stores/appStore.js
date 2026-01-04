import { create } from 'zustand';
import { notifications } from '@mantine/notifications';
import { api } from '../api/client';

export const useAppStore = create((set, get) => ({
  // System status
  status: {},
  tradernet: { connected: false },
  tradernetConnectionStatus: null,
  markets: {},

  // Planner status
  plannerStatus: null,
  plannerStatusEventSource: null,

  // Recommendations
  recommendations: null,
  recommendationEventSource: null,

  // UI State
  activeTab: 'next-actions',
  message: '',
  messageType: 'success',

  // Modal states
  showAddSecurityModal: false,
  showEditSecurityModal: false,
  showSecurityChart: false,
  showSettingsModal: false,
  showUniverseManagementModal: false,
  showBucketHealthModal: false,
  showPlannerManagementModal: false,

  closeSecurityChartModal: () => set({
    showSecurityChart: false,
    selectedSecuritySymbol: null,
    selectedSecurityIsin: null,
  }),

  // Selected items
  selectedSecuritySymbol: null,
  selectedSecurityIsin: null,
  editingSecurity: null,
  selectedBucket: null,
  selectedPlannerId: '',

  // Loading states
  loading: {
    recommendations: false,
    scores: false,
    sync: false,
    historical: false,
    execute: false,
    countrySave: false,
    industrySave: false,
    securitySave: false,
    refreshData: false,
    logs: false,
    tradernetTest: false,
  },

  // Actions
  setActiveTab: (tab) => set({ activeTab: tab }),

  showMessage: (message, type = 'success') => {
    set({ message, messageType: type });
    notifications.show({
      title: type === 'error' ? 'Error' : type === 'success' ? 'Success' : 'Info',
      message,
      color: type === 'error' ? 'red' : type === 'success' ? 'green' : 'blue',
      autoClose: 3000,
    });
    setTimeout(() => set({ message: '', messageType: 'success' }), 3000);
  },

  // Modal actions
  openAddSecurityModal: () => set({ showAddSecurityModal: true }),
  closeAddSecurityModal: () => set({ showAddSecurityModal: false }),

  openEditSecurityModal: (security) => set({
    showEditSecurityModal: true,
    editingSecurity: security,
    selectedSecurityIsin: security?.isin,
  }),
  closeEditSecurityModal: () => set({
    showEditSecurityModal: false,
    editingSecurity: null,
    selectedSecurityIsin: null,
  }),

  openSettingsModal: () => set({ showSettingsModal: true }),
  closeSettingsModal: () => set({ showSettingsModal: false }),

  openUniverseManagementModal: () => set({ showUniverseManagementModal: true }),
  closeUniverseManagementModal: () => set({ showUniverseManagementModal: false }),

  openSecurityChart: (symbol, isin) => set({
    showSecurityChart: true,
    selectedSecuritySymbol: symbol,
    selectedSecurityIsin: isin,
  }),

  openBucketHealthModal: (bucket) => set({
    showBucketHealthModal: true,
    selectedBucket: bucket,
  }),
  closeBucketHealthModal: () => set({
    showBucketHealthModal: false,
    selectedBucket: null,
  }),

  openPlannerManagementModal: () => set({ showPlannerManagementModal: true }),
  closePlannerManagementModal: () => set({ showPlannerManagementModal: false }),

  // Data fetching
  fetchStatus: async () => {
    try {
      const status = await api.fetchStatus();
      set({ status });
    } catch (e) {
      console.error('Failed to fetch status:', e);
    }
  },

  fetchTradernet: async () => {
    try {
      const tradernet = await api.fetchTradernet();
      set({ tradernet });
    } catch (e) {
      console.error('Failed to fetch tradernet status:', e);
    }
  },

  fetchMarkets: async () => {
    try {
      const data = await api.fetchMarkets();
      set({ markets: data.markets || {} });
    } catch (e) {
      console.error('Failed to fetch market status:', e);
    }
  },

  fetchRecommendations: async () => {
    set({ loading: { ...get().loading, recommendations: true } });
    try {
      const recommendations = await api.fetchRecommendations();
      set({ recommendations });
    } catch (e) {
      console.error('Failed to fetch recommendations:', e);
      set({ recommendations: null });
    } finally {
      set({ loading: { ...get().loading, recommendations: false } });
    }
  },

  executeRecommendation: async () => {
    set({ loading: { ...get().loading, execute: true } });
    try {
      const result = await api.executeRecommendation();
      get().showMessage(`Executed: ${result.quantity} ${result.symbol} @ €${result.price}`, 'success');
      await get().fetchRecommendations();
    } catch (e) {
      get().showMessage('Failed to execute trade', 'error');
    } finally {
      set({ loading: { ...get().loading, execute: false } });
    }
  },

  testTradernetConnection: async () => {
    set({
      loading: { ...get().loading, tradernetTest: true },
      tradernetConnectionStatus: null,
    });
    try {
      const result = await api.testTradernetConnection();
      const connected = result.connected || false;
      set({ tradernetConnectionStatus: connected });
      if (connected) {
        get().showMessage('Tradernet connection successful', 'success');
      } else {
        get().showMessage(`Tradernet connection failed: ${result.message || 'check credentials'}`, 'error');
      }
    } catch (e) {
      console.error('Error testing Tradernet connection:', e);
      set({ tradernetConnectionStatus: false });
      get().showMessage(`Failed to test Tradernet connection: ${e.message}`, 'error');
    } finally {
      set({ loading: { ...get().loading, tradernetTest: false } });
    }
  },

  regenerateSequences: async () => {
    try {
      await api.regenerateSequences();
      get().showMessage('Sequences regenerated. New sequences will be generated on next batch run.', 'success');
      await get().fetchRecommendations();
    } catch (e) {
      console.error('Failed to regenerate sequences:', e);
      get().showMessage('Failed to regenerate sequences', 'error');
    }
  },

  // SSE streams
  startPlannerStatusStream: () => {
    const { plannerStatusEventSource } = get();
    if (plannerStatusEventSource) {
      plannerStatusEventSource.close();
    }

    const eventSource = new EventSource('/api/planning/stream');
    set({ plannerStatusEventSource: eventSource });

    eventSource.onmessage = (event) => {
      try {
        const status = JSON.parse(event.data);
        set({ plannerStatus: status });
      } catch (e) {
        console.error('Failed to parse planner status event:', e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('Planner status SSE stream error:', error);
    };
  },

  stopPlannerStatusStream: () => {
    const { plannerStatusEventSource } = get();
    if (plannerStatusEventSource) {
      plannerStatusEventSource.close();
      set({ plannerStatusEventSource: null });
    }
  },

  startRecommendationStream: () => {
    const { recommendationEventSource } = get();
    if (recommendationEventSource) {
      recommendationEventSource.close();
    }

    const eventSource = new EventSource('/api/planning/stream');
    set({ recommendationEventSource: eventSource });

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.invalidated) {
          get().fetchRecommendations();
        }
      } catch (e) {
        console.error('Failed to parse recommendation event:', e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('Recommendation SSE stream error:', error);
    };
  },

  stopRecommendationStream: () => {
    const { recommendationEventSource } = get();
    if (recommendationEventSource) {
      recommendationEventSource.close();
      set({ recommendationEventSource: null });
    }
  },

  // Fetch all initial data
  fetchAll: async () => {
    await Promise.all([
      get().fetchStatus(),
      get().fetchTradernet(),
      get().fetchMarkets(),
      get().fetchRecommendations(),
    ]);
  },
}));
