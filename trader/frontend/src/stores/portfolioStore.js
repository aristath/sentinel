import { create } from 'zustand';
import { api } from '../api/client';

export const usePortfolioStore = create((set, get) => ({
  // Portfolio data
  allocation: {
    country: [],
    industry: [],
    total_value: 0,
    cash_balance: 0,
  },
  alerts: [],
  cashBreakdown: [],

  // Countries and industries
  countries: [],
  countryTargets: {},
  editingCountry: false,
  activeCountries: [],

  industries: [],
  industryTargets: {},
  editingIndustry: false,
  activeIndustries: [],

  // Loading states
  loading: {
    countrySave: false,
    industrySave: false,
  },

  // Actions
  fetchAllocation: async () => {
    try {
      const data = await api.fetchAllocation();
      set({
        allocation: {
          country: data.country || [],
          industry: data.industry || [],
          total_value: data.total_value || 0,
          cash_balance: data.cash_balance || 0,
        },
        alerts: data.alerts || [],
      });
    } catch (e) {
      console.error('Failed to fetch allocation:', e);
    }
  },

  fetchCashBreakdown: async () => {
    try {
      const data = await api.fetchCashBreakdown();
      set({ cashBreakdown: data.balances || [] });
    } catch (e) {
      console.error('Failed to fetch cash breakdown:', e);
    }
  },

  fetchTargets: async () => {
    try {
      const data = await api.fetchTargets();
      const countries = Object.keys(data.country || {});
      const industries = Object.keys(data.industry || {});
      const countryTargets = {};
      const industryTargets = {};

      for (const [name, weight] of Object.entries(data.country || {})) {
        countryTargets[name] = weight;
      }
      for (const [name, weight] of Object.entries(data.industry || {})) {
        industryTargets[name] = weight;
      }

      set({
        countries,
        countryTargets,
        industries,
        industryTargets,
        activeCountries: countries,
        activeIndustries: industries,
      });
    } catch (e) {
      console.error('Failed to fetch targets:', e);
    }
  },

  startEditCountry: () => set({ editingCountry: true }),
  cancelEditCountry: () => set({ editingCountry: false }),
  adjustCountrySlider: (name, value) => {
    const { countryTargets } = get();
    set({ countryTargets: { ...countryTargets, [name]: value } });
  },
  saveCountryTargets: async () => {
    set({ loading: { ...get().loading, countrySave: true } });
    try {
      await api.saveCountryTargets(get().countryTargets);
      await get().fetchTargets();
      await get().fetchAllocation();
      set({ editingCountry: false });
      // Notification will be shown via appStore.showMessage if needed
    } catch (e) {
      console.error('Failed to save country targets:', e);
      throw e; // Re-throw so components can handle it
    } finally {
      set({ loading: { ...get().loading, countrySave: false } });
    }
  },

  startEditIndustry: () => set({ editingIndustry: true }),
  cancelEditIndustry: () => set({ editingIndustry: false }),
  adjustIndustrySlider: (name, value) => {
    const { industryTargets } = get();
    set({ industryTargets: { ...industryTargets, [name]: value } });
  },
  saveIndustryTargets: async () => {
    set({ loading: { ...get().loading, industrySave: true } });
    try {
      await api.saveIndustryTargets(get().industryTargets);
      await get().fetchTargets();
      await get().fetchAllocation();
      set({ editingIndustry: false });
      // Notification will be shown via appStore.showMessage if needed
    } catch (e) {
      console.error('Failed to save industry targets:', e);
      throw e; // Re-throw so components can handle it
    } finally {
      set({ loading: { ...get().loading, industrySave: false } });
    }
  },
}));
