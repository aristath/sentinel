import { create } from 'zustand';
import { notifications } from '@mantine/notifications';
import { api } from '../api/client';
import { handleEvent, clearAllDebounces } from './eventHandlers';

export const useAppStore = create((set, get) => ({
  // System status
  status: {},
  tradernet: { connected: false },
  tradernetConnectionStatus: null,
  markets: {},

  // Planner status
  plannerStatus: null,

  // Job status tracking
  runningJobs: {},     // Map: jobId -> { jobType, status, description, startedAt, progress }
  completedJobs: {},   // Map: jobId -> { jobType, status, description, completedAt, duration }

  // Recommendations
  recommendations: null,

  // Unified event stream
  eventStreamSource: null,
  eventStreamReconnectAttempts: 0,
  eventStreamConnecting: false,

  // Polling fallback
  pollingIntervalId: null,
  sseRetryIntervalId: null,
  isPollingMode: false,
  maxSseFailures: 5, // After 5 failures, switch to polling

  // UI State
  activeTab: 'next-actions',
  message: '',
  messageType: 'success',

  // Modal states
  showAddSecurityModal: false,
  showEditSecurityModal: false,
  showSecurityChart: false,
  showSettingsModal: false,
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

  openSecurityChart: (symbol, isin) => set({
    showSecurityChart: true,
    selectedSecuritySymbol: symbol,
    selectedSecurityIsin: isin,
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

  // Planner status update (called by event handler)
  updatePlannerStatus: (status) => {
    set({ plannerStatus: status });
  },

  // Job status management (called by event handlers)
  addRunningJob: (job) => {
    const { jobId, jobType, status, description, startedAt } = job;
    set((state) => ({
      runningJobs: {
        ...state.runningJobs,
        [jobId]: {
          jobId,
          jobType,
          status,
          description,
          startedAt,
          progress: null,
        },
      },
    }));
  },

  updateJobProgress: (jobId, progress) => {
    set((state) => {
      const job = state.runningJobs[jobId];
      if (!job) return state;

      return {
        runningJobs: {
          ...state.runningJobs,
          [jobId]: {
            ...job,
            progress,
          },
        },
      };
    });
  },

  completeJob: (jobId, completion) => {
    const { status, error, duration } = completion;

    set((state) => {
      const job = state.runningJobs[jobId];
      if (!job) return state;

      // Move from running to completed
      const { [jobId]: completedJob, ...remainingRunning } = state.runningJobs;

      const completedJobData = {
        ...completedJob,
        status,
        error,
        duration,
        completedAt: Date.now(),
      };

      // Clear completed job after 4 seconds (linger with checkmark)
      setTimeout(() => {
        set((state) => {
          // eslint-disable-next-line no-unused-vars
          const { [jobId]: _, ...remaining } = state.completedJobs;
          return { completedJobs: remaining };
        });
      }, 4000);

      return {
        runningJobs: remainingRunning,
        completedJobs: {
          ...state.completedJobs,
          [jobId]: completedJobData,
        },
      };
    });
  },

  // Polling fallback mechanism
  startPolling: () => {
    const { pollingIntervalId, isPollingMode } = get();

    // Prevent duplicate polling
    if (pollingIntervalId || isPollingMode) {
      return;
    }

    console.log('Starting polling mode (SSE unavailable)');
    set({ isPollingMode: true });

    // Poll critical data every 10 seconds
    const intervalId = setInterval(async () => {
      try {
        // Fetch app store data
        await get().fetchAll();

        // Fetch other stores' data
        const { usePortfolioStore } = await import('./portfolioStore');
        const { useSecuritiesStore } = await import('./securitiesStore');
        const { useTradesStore } = await import('./tradesStore');

        await Promise.all([
          usePortfolioStore.getState().fetchAllocation(),
          usePortfolioStore.getState().fetchCashBreakdown(),
          useSecuritiesStore.getState().fetchSecurities(),
          useTradesStore.getState().fetchTrades(),
        ]);
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 10000);

    set({ pollingIntervalId: intervalId });

    // Try to reconnect to SSE every 60 seconds
    const retryIntervalId = setInterval(() => {
      console.log('Attempting to reconnect to SSE...');
      get().attemptSseReconnect();
    }, 60000);

    set({ sseRetryIntervalId: retryIntervalId });
  },

  stopPolling: () => {
    const { pollingIntervalId, sseRetryIntervalId } = get();

    if (pollingIntervalId) {
      clearInterval(pollingIntervalId);
      set({ pollingIntervalId: null });
    }

    if (sseRetryIntervalId) {
      clearInterval(sseRetryIntervalId);
      set({ sseRetryIntervalId: null });
    }

    set({ isPollingMode: false });
    console.log('Stopped polling mode');
  },

  attemptSseReconnect: () => {
    const { eventStreamSource } = get();

    // Close existing failed connection if any
    if (eventStreamSource) {
      eventStreamSource.close();
    }

    // Reset reconnect attempts for fresh start
    set({ eventStreamReconnectAttempts: 0 });

    // Try to start SSE again
    // Use the logFile from logsStore if needed
    get().startEventStream();
  },

  // Unified event stream
  startEventStream: () => {
    const { eventStreamSource, eventStreamConnecting, isPollingMode } = get();

    // Prevent concurrent connection attempts
    if (eventStreamConnecting) {
      return;
    }

    set({ eventStreamConnecting: true });

    if (eventStreamSource) {
      eventStreamSource.close();
    }

    // Event stream without log file watching (logs use HTTP polling instead)
    const url = '/api/events/stream';
    const eventSource = new EventSource(url);
    set({ eventStreamSource: eventSource, eventStreamConnecting: false });

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleEvent(data);
      } catch (e) {
        console.error('Failed to parse event stream message:', e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('Event stream error:', error);

      // Close the connection and reset connecting flag
      eventSource.close();
      set({ eventStreamConnecting: false });

      // Get current attempts for delay calculation
      const currentAttempts = get().eventStreamReconnectAttempts;
      const maxFailures = get().maxSseFailures;

      // If we've failed too many times, switch to polling mode
      if (currentAttempts >= maxFailures && !isPollingMode) {
        console.warn(`SSE failed ${currentAttempts} times. Switching to polling mode.`);
        set({ eventStreamReconnectAttempts: currentAttempts + 1 });
        get().startPolling();
        return;
      }

      // Otherwise, reconnect with exponential backoff (max 30 seconds)
      const delay = Math.min(1000 * Math.pow(2, currentAttempts), 30000);
      setTimeout(() => {
        // Read fresh state to avoid stale closure
        const freshAttempts = get().eventStreamReconnectAttempts;
        set({ eventStreamReconnectAttempts: freshAttempts + 1 });
        get().startEventStream();
      }, delay);
    };

    // Reset reconnect attempts on successful connection
    eventSource.addEventListener('open', () => {
      console.log('SSE connection established');
      set({ eventStreamReconnectAttempts: 0 });

      // If we were in polling mode, stop polling
      if (isPollingMode) {
        console.log('SSE reconnected successfully. Stopping polling mode.');
        get().stopPolling();
      }
    });
  },

  stopEventStream: () => {
    const { eventStreamSource } = get();
    if (eventStreamSource) {
      eventStreamSource.close();
      set({ eventStreamSource: null, eventStreamReconnectAttempts: 0 });
    }
    // Stop polling if active
    get().stopPolling();
    // Clear all pending debounced event handlers
    clearAllDebounces();
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
