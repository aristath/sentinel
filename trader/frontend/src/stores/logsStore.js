import { create } from 'zustand';
import { api } from '../api/client';

export const useLogsStore = create((set, get) => ({
  entries: [],
  selectedLogFile: 'arduino-trader.log',
  availableLogFiles: [],
  filterLevel: null,
  searchQuery: '',
  lineCount: 100,
  showErrorsOnly: false,
  autoRefresh: true,
  refreshInterval: 5000,
  loading: false,
  refreshTimer: null,
  totalLines: 0,
  returnedLines: 0,

  fetchAvailableLogFiles: async () => {
    try {
      const data = await api.fetchAvailableLogFiles();
      set({ availableLogFiles: data.files || [] });
    } catch (e) {
      console.error('Failed to fetch available log files:', e);
    }
  },

  fetchLogs: async () => {
    const { selectedLogFile, filterLevel, searchQuery, lineCount, showErrorsOnly } = get();
    set({ loading: true });

    try {
      let data;
      if (showErrorsOnly) {
        data = await api.fetchErrorLogs(selectedLogFile, lineCount);
      } else {
        data = await api.fetchLogs(selectedLogFile, lineCount, filterLevel, searchQuery || null);
      }

      set({
        entries: data.entries || [],
        totalLines: data.total_lines || 0,
        returnedLines: data.returned_lines || 0,
        loading: false,
      });
    } catch (e) {
      console.error('Failed to fetch logs:', e);
      set({ loading: false });
    }
  },

  startAutoRefresh: () => {
    const { refreshTimer, refreshInterval } = get();
    if (refreshTimer) {
      clearInterval(refreshTimer);
    }

    const timer = setInterval(() => {
      get().fetchLogs();
    }, refreshInterval);

    set({ refreshTimer: timer });
  },

  stopAutoRefresh: () => {
    const { refreshTimer } = get();
    if (refreshTimer) {
      clearInterval(refreshTimer);
      set({ refreshTimer: null });
    }
  },

  setSelectedLogFile: (file) => {
    set({ selectedLogFile: file });
    get().fetchLogs();
  },

  setFilterLevel: (level) => {
    set({ filterLevel: level === 'all' ? null : level });
    get().fetchLogs();
  },

  setSearchQuery: (query) => {
    set({ searchQuery: query });
    // Debounce is handled by the component
  },

  setLineCount: (count) => {
    set({ lineCount: Math.max(50, Math.min(1000, count || 100)) });
    get().fetchLogs();
  },

  setShowErrorsOnly: (show) => {
    set({ showErrorsOnly: show });
    get().fetchLogs();
  },

  setAutoRefresh: (enabled) => {
    set({ autoRefresh: enabled });
    if (enabled) {
      get().startAutoRefresh();
    } else {
      get().stopAutoRefresh();
    }
  },
}));

