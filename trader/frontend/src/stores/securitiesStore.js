import { create } from 'zustand';
import { api } from '../api/client';

export const useSecuritiesStore = create((set, get) => ({
  // Securities data
  securities: [],
  sparklines: {},

  // Filters and sorting
  securityFilter: 'all',
  industryFilter: 'all',
  searchQuery: '',
  minScore: 0,
  sortBy: 'priority_score',
  sortDesc: true,

  // Loading states
  loading: {
    scores: false,
    refreshData: false,
    securitySave: false,
  },

  // Actions
  fetchSecurities: async () => {
    try {
      const securities = await api.fetchSecurities();
      set({ securities });
    } catch (e) {
      console.error('Failed to fetch securities:', e);
    }
  },

  fetchSparklines: async () => {
    try {
      const sparklines = await api.fetchSparklines();
      set({ sparklines });
    } catch (e) {
      console.error('Failed to fetch sparklines:', e);
    }
  },

  setSecurityFilter: (filter) => set({ securityFilter: filter }),
  setIndustryFilter: (filter) => set({ industryFilter: filter }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setMinScore: (score) => set({ minScore: score }),
  setSortBy: (field, desc = true) => set({ sortBy: field, sortDesc: desc }),

  getFilteredSecurities: () => {
    const { securities, securityFilter, industryFilter, searchQuery, minScore, sortBy, sortDesc } = get();

    let filtered = [...securities];

    // Filter by country
    if (securityFilter !== 'all') {
      filtered = filtered.filter(s => s.country === securityFilter);
    }

    // Filter by industry
    if (industryFilter !== 'all') {
      filtered = filtered.filter(s => s.industry === industryFilter);
    }

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(s =>
        s.symbol?.toLowerCase().includes(query) ||
        s.name?.toLowerCase().includes(query)
      );
    }

    // Filter by minimum score
    if (minScore > 0) {
      filtered = filtered.filter(s => (s.priority_score || 0) >= minScore);
    }

    // Sort
    filtered.sort((a, b) => {
      const aVal = a[sortBy] ?? 0;
      const bVal = b[sortBy] ?? 0;
      if (sortDesc) {
        return bVal > aVal ? 1 : bVal < aVal ? -1 : 0;
      }
      return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
    });

    return filtered;
  },

  refreshScore: async (isin) => {
    set({ loading: { ...get().loading, scores: true } });
    try {
      await api.refreshScore(isin);
      await get().fetchSecurities();
    } catch (e) {
      console.error('Failed to refresh score:', e);
    } finally {
      set({ loading: { ...get().loading, scores: false } });
    }
  },

  refreshAllScores: async () => {
    set({ loading: { ...get().loading, scores: true } });
    try {
      await api.refreshAllScores();
      await get().fetchSecurities();
    } catch (e) {
      console.error('Failed to refresh all scores:', e);
    } finally {
      set({ loading: { ...get().loading, scores: false } });
    }
  },
}));
