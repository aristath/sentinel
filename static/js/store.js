/**
 * Arduino Trader - Alpine.js Store
 * Centralized state management for the application
 */

document.addEventListener('alpine:init', () => {
  Alpine.store('app', {
    // Data
    status: {},
    allocation: {
      country: [],
      industry: [],
      total_value: 0,
      cash_balance: 0
    },
    alerts: [],  // Concentration limit alerts
    cashBreakdown: [],  // [{currency: 'EUR', amount: 1000}, ...]
    securities: [],
    trades: [],
    tradernet: { connected: false },
    markets: {},  // {EU: {open: bool, ...}, US: {...}, ASIA: {...}}
    recommendations: null,  // Unified recommendations: {depth: int, steps: [], total_score_improvement: float, final_available_cash: float}
    plannerStatus: null,  // {has_sequences: bool, total_sequences: int, evaluated_count: int, is_planning: bool, is_finished: bool, progress_percentage: float}
    // Default settings - will be overwritten by fetchSettings()
    settings: {
      optimizer_blend: 0.5,
      optimizer_target_return: 0.11,
      transaction_cost_fixed: 2.0,
      transaction_cost_percent: 0.002,
      min_cash_reserve: 500.0,
    },
    tradingMode: 'research',  // 'live' or 'research'
    sparklines: {},  // {symbol: [{time, value}, ...]}

    // Logs State
    logs: {
      entries: [],
      selectedLogFile: 'arduino-trader.log',
      availableLogFiles: [],
      filterLevel: null,  // null = all, or 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
      searchQuery: '',
      lineCount: 100,
      showErrorsOnly: false,
      autoRefresh: true,
      refreshInterval: 5000,  // 5 seconds
      totalLines: 0,
      returnedLines: 0,
      logPath: '',
      lastRefresh: null,
      loading: false,
      refreshTimer: null
    },

    // UI State - Tabs
    activeTab: 'next-actions',  // 'next-actions', 'diversification', 'security-universe', 'recent-trades', or 'logs'

    // UI State - Filters
    securityFilter: 'all',
    industryFilter: 'all',
    searchQuery: '',
    minScore: 0,
    sortBy: 'priority_score',
    sortDesc: true,
    showAddSecurityModal: false,
    showEditSecurityModal: false,
    showSecurityChart: false,
    showSettingsModal: false,
    showUniverseManagementModal: false,
    selectedSecuritySymbol: null,
    selectedSecurityIsin: null,
    editingSecurity: null,
    executingSymbol: null,
    executingSellSymbol: null,
    executingStep: null,
    message: '',
    messageType: 'success',

    // Loading States
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
      universeSuggestions: false
    },

    // SSE connections
    plannerStatusEventSource: null,
    recommendationEventSource: null,

    // Edit Mode States
    editingCountry: false,
    countryTargets: {},
    countries: [],
    editingIndustry: false,
    industryTargets: {},

    // Add Stock Form
    newSecurity: { identifier: '' },
    addingSecurity: false,

    // Universe Management
    universeSuggestions: {
      candidatesToAdd: [],
      securitiesToPrune: []
    },
    addingFromSuggestion: {},  // Track per-symbol: { 'AAPL.US': true }
    pruningFromSuggestion: {},  // Track per-symbol: { 'XYZ.US': true }

    // Fetch All Data
    async fetchAll() {
      await Promise.all([
        this.fetchStatus(),
        this.fetchAllocation(),
        this.fetchCashBreakdown(),
        this.fetchSecurities(),
        this.fetchTrades(),
        this.fetchTradernet(),
        this.fetchMarkets(),
        this.fetchCountries(),
        this.fetchRecommendations(),
        this.fetchSettings(),
        this.fetchSparklines()
      ]);
    },

    // Data Fetching (delegated to API layer)
    async fetchStatus() {
      try {
        this.status = await API.fetchStatus();
      } catch (e) {
        console.error('Failed to fetch status:', e);
      }
    },

    async fetchAllocation() {
      try {
        const data = await API.fetchAllocation();
        this.allocation = {
          country: data.country || [],
          industry: data.industry || [],
          total_value: data.total_value || 0,
          cash_balance: data.cash_balance || 0
        };
        this.alerts = data.alerts || [];
      } catch (e) {
        console.error('Failed to fetch allocation:', e);
      }
    },

    async fetchCashBreakdown() {
      try {
        const response = await fetch('/api/portfolio/cash-breakdown');
        const data = await response.json();
        this.cashBreakdown = data.balances || [];
      } catch (e) {
        console.error('Failed to fetch cash breakdown:', e);
      }
    },

    async fetchSecurities() {
      try {
        const securities = await API.fetchSecurities();

        // Frontend validation: check if allocation shows value but securities don't have positions
        // This catches edge cases where API validation might have missed something
        // Only check if allocation has already been loaded (avoid race conditions with parallel fetchAll)
        const allocationLoaded = this.allocation &&
                                 this.allocation.total_value !== undefined;
        const hasAllocationValue = allocationLoaded && this.allocation.total_value > 0;
        const hasSecurityPositions = securities.some(s => s.position_value > 0);

        // If allocation shows value but securities don't, cache might be stale
        // Only retry once to avoid infinite loops (use a flag to prevent retry loops)
        if (hasAllocationValue && !hasSecurityPositions && securities.length > 0 && !this._securitiesRetryFlag) {
          this._securitiesRetryFlag = true; // Prevent infinite retries
          console.warn('Position data mismatch detected in frontend, retrying fetch');
          // Wait a brief moment for any async cache invalidation to complete
          await new Promise(resolve => setTimeout(resolve, 100));
          const freshSecurities = await API.fetchSecurities();
          // Only use fresh data if it actually has positions
          if (freshSecurities.some(s => s.position_value > 0)) {
            this.securities = freshSecurities;
            this._securitiesRetryFlag = false; // Reset flag on success
            return;
          }
          // If still no positions, log warning but use what we have
          console.warn('Position data still missing after retry - may need manual refresh');
          this._securitiesRetryFlag = false; // Reset flag
        }

        this.securities = securities;
        this._securitiesRetryFlag = false; // Reset flag on normal path
      } catch (e) {
        console.error('Failed to fetch securities:', e);
        this._securitiesRetryFlag = false; // Reset flag on error
      }
    },

    async fetchTrades() {
      try {
        this.trades = await API.fetchTrades();
      } catch (e) {
        console.error('Failed to fetch trades:', e);
      }
    },

    async fetchTradernet() {
      try {
        this.tradernet = await API.fetchTradernet();
      } catch (e) {
        console.error('Failed to fetch tradernet status:', e);
      }
    },

    async fetchMarkets() {
      try {
        const response = await fetch('/api/status/markets');
        const data = await response.json();
        this.markets = data.markets || {};
      } catch (e) {
        console.error('Failed to fetch market status:', e);
      }
    },

    async fetchCountries() {
      try {
        const data = await API.fetchTargets();
        this.countries = Object.keys(data.country || {});
        this.countryTargets = {};
        for (const [name, weight] of Object.entries(data.country || {})) {
          this.countryTargets[name] = weight;
        }
      } catch (e) {
        console.error('Failed to fetch countries:', e);
      }
    },

    async fetchRecommendations() {
      this.loading.recommendations = true;
      try {
        // Unified recommendations endpoint - returns optimal sequence from holistic planner
        const data = await API.fetchRecommendations();
        this.recommendations = data;
      } catch (e) {
        console.error('Failed to fetch recommendations:', e);
        this.recommendations = null;
      }
      this.loading.recommendations = false;
    },

    startPlannerStatusStream() {
      // Close existing connection if any
      if (this.plannerStatusEventSource) {
        this.plannerStatusEventSource.close();
        this.plannerStatusEventSource = null;
      }

      // Connect to SSE stream for planner status updates
      const eventSource = new EventSource('/api/planner/status/stream');
      this.plannerStatusEventSource = eventSource;

      eventSource.onmessage = (event) => {
        try {
          const status = JSON.parse(event.data);
          this.plannerStatus = status;
        } catch (e) {
          console.error('Failed to parse planner status event:', e);
        }
      };

      eventSource.onerror = (error) => {
        console.error('Planner status SSE stream error:', error);
        // EventSource will automatically reconnect on error
      };
    },

    stopPlannerStatusStream() {
      if (this.plannerStatusEventSource) {
        this.plannerStatusEventSource.close();
        this.plannerStatusEventSource = null;
      }
    },

    startRecommendationStream() {
      // Close existing connection if any
      if (this.recommendationEventSource) {
        this.recommendationEventSource.close();
        this.recommendationEventSource = null;
      }

      // Connect to SSE stream for recommendation updates
      const eventSource = new EventSource('/api/trades/recommendations/stream');
      this.recommendationEventSource = eventSource;

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // When recommendations are invalidated, refresh them
          if (data.invalidated) {
            this.fetchRecommendations();
          }
        } catch (e) {
          console.error('Failed to parse recommendation event:', e);
        }
      };

      eventSource.onerror = (error) => {
        console.error('Recommendation SSE stream error:', error);
        // EventSource will automatically reconnect on error
      };
    },

    stopRecommendationStream() {
      if (this.recommendationEventSource) {
        this.recommendationEventSource.close();
        this.recommendationEventSource = null;
      }
    },

    async executeRecommendation() {
      this.loading.execute = true;
      try {
        const result = await API.executeRecommendation();
        this.showMessage(`Executed: ${result.quantity} ${result.symbol} @ €${result.price}`, 'success');
        // Refresh recommendations after execution
        await this.fetchRecommendations();
        await this.fetchAll();
      } catch (e) {
        this.showMessage('Failed to execute trade', 'error');
      }
      this.loading.execute = false;
    },

    async fetchSettings() {
      try {
        this.settings = await API.fetchSettings();
        // Extract trading_mode from settings (it's a string, not a number)
        if (this.settings.trading_mode) {
          this.tradingMode = this.settings.trading_mode;
        }
      } catch (e) {
        console.error('Failed to fetch settings:', e);
      }
    },

    async fetchSparklines() {
      try {
        this.sparklines = await API.fetchSparklines();
      } catch (e) {
        console.error('Failed to fetch sparklines:', e);
      }
    },


    async updateSetting(key, value) {
      const numValue = parseFloat(value);
      if (isNaN(numValue)) return;
      try {
        await API.updateSetting(key, numValue);
        this.settings[key] = numValue;
        this.showMessage(`Setting "${key}" updated`, 'success');
      } catch (e) {
        this.showMessage(`Failed to update ${key}`, 'error');
      }
    },

    async regenerateSequences() {
      try {
        const response = await API.regenerateSequences();
        this.showMessage('Sequences regenerated. New sequences will be generated on next batch run.', 'success');
        // Refresh recommendations to show updated state
        await this.fetchRecommendations();
      } catch (e) {
        this.showMessage('Failed to regenerate sequences', 'error');
      }
    },

    async updateJobSetting(key, value) {
      const numValue = parseFloat(value);
      if (isNaN(numValue)) return;
      try {
        await API.updateSetting(key, numValue);
        this.settings[key] = numValue;
        // Reschedule jobs after updating job setting
        await API.rescheduleJobs();
        this.showMessage('Job schedule updated', 'success');
      } catch (e) {
        this.showMessage(`Failed to update job schedule`, 'error');
      }
    },


    // Deprecated - recommendations now execute automatically
    // async executeRecommendation(symbol) {
    //   this.loading.execute = true;
    //   this.executingSymbol = symbol;
    //   try {
    //     const result = await API.executeRecommendation(symbol);
    //     this.showMessage(`Executed: ${result.quantity} ${symbol} @ €${result.price}`, 'success');
    //     await this.fetchAll();
    //   } catch (e) {
    //     this.showMessage('Failed to execute trade', 'error');
    //   }
    //   this.executingSymbol = null;
    //   this.loading.execute = false;
    // },

    // async executeSellRecommendation(symbol) {
    //   this.loading.execute = true;
    //   this.executingSellSymbol = symbol;
    //   try {
    //     const result = await API.executeSellRecommendation(symbol);
    //     this.showMessage(`Sold: ${result.quantity} ${symbol} @ €${result.price}`, 'success');
    //     await this.fetchAll();
    //   } catch (e) {
    //     this.showMessage('Failed to execute sell', 'error');
    //   }
    //   this.executingSellSymbol = null;
    //   this.loading.execute = false;
    // },

    // Computed Properties
    get industries() {
      const set = new Set();
      this.securities.forEach(s => {
        if (s.industry) {
          s.industry.split(',').forEach(ind => {
            const trimmed = ind.trim();
            if (trimmed) set.add(trimmed);
          });
        }
      });
      return Array.from(set).sort();
    },

    get activeCountries() {
      // Return group names from allocation data (groups are what the optimizer uses)
      if (this.allocation && this.allocation.country) {
        return this.allocation.country.map(c => c.name).sort();
      }
      // Fallback: return individual countries if no group data
      const countries = new Set(this.securities.map(s => s.country).filter(Boolean));
      return Array.from(countries).sort();
    },

    get activeIndustries() {
      // Return group names from allocation data (groups are what the optimizer uses)
      if (this.allocation && this.allocation.industry) {
        return this.allocation.industry.map(i => i.name).sort();
      }
      // Fallback: return individual industries if no group data
      const inds = new Set();
      this.securities.forEach(s => {
        if (s.industry) {
          s.industry.split(',').forEach(i => inds.add(i.trim()));
        }
      });
      return Array.from(inds).sort();
    },

    get filteredSecurities() {
      let filtered = this.securities;

      if (this.securityFilter !== 'all') {
        filtered = filtered.filter(s => s.country === this.securityFilter);
      }

      if (this.industryFilter !== 'all') {
        filtered = filtered.filter(s => {
          if (!s.industry) return false;
          const industries = s.industry.split(',').map(i => i.trim());
          return industries.includes(this.industryFilter);
        });
      }

      if (this.searchQuery) {
        const q = this.searchQuery.toLowerCase();
        filtered = filtered.filter(s =>
          s.symbol.toLowerCase().includes(q) ||
          s.name.toLowerCase().includes(q)
        );
      }

      if (this.minScore > 0) {
        filtered = filtered.filter(s => (s.total_score || 0) >= this.minScore);
      }

      return filtered.sort((a, b) => {
        let aVal = a[this.sortBy];
        let bVal = b[this.sortBy];

        if (aVal == null) aVal = this.sortDesc ? -Infinity : Infinity;
        if (bVal == null) bVal = this.sortDesc ? -Infinity : Infinity;

        if (typeof aVal === 'string' && typeof bVal === 'string') {
          return this.sortDesc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
        }

        return this.sortDesc ? bVal - aVal : aVal - bVal;
      });
    },

    sortSecurities(field) {
      if (this.sortBy === field) {
        this.sortDesc = !this.sortDesc;
      } else {
        this.sortBy = field;
        this.sortDesc = true;
      }
    },

    // Actions
    async refreshScores() {
      this.loading.scores = true;
      try {
        const data = await API.refreshAllScores();
        this.showMessage(data.message, 'success');
        await this.fetchSecurities();
      } catch (e) {
        this.showMessage('Failed to refresh scores', 'error');
      }
      this.loading.scores = false;
    },

    async refreshSingleScore(isin) {
      try {
        await API.refreshScore(isin);
        await this.fetchSecurities();
      } catch (e) {
        this.showMessage('Failed to refresh score', 'error');
      }
    },

    async refreshSecurityData(isin) {
      if (!isin) return;
      this.loading.refreshData = true;
      try {
        const response = await fetch(`/api/securities/${encodeURIComponent(isin)}/refresh-data`, {
          method: 'POST'
        });
        const data = await response.json();
        if (response.ok) {
          this.showMessage(`Data refresh completed for ${data.symbol || isin}`, 'success');
          await this.fetchSecurities();
        } else {
          this.showMessage(data.detail || 'Data refresh failed', 'error');
        }
      } catch (e) {
        this.showMessage('Failed to refresh data', 'error');
      }
      this.loading.refreshData = false;
    },

    async syncPrices() {
      this.loading.sync = true;
      try {
        const data = await API.syncPrices();
        this.showMessage(data.message, 'success');
      } catch (e) {
        this.showMessage('Failed to sync prices', 'error');
      }
      this.loading.sync = false;
    },

    async syncHistorical() {
      this.loading.historical = true;
      try {
        const data = await API.syncHistorical();
        this.showMessage(data.message, 'success');
      } catch (e) {
        this.showMessage('Failed to sync historical data', 'error');
      }
      this.loading.historical = false;
    },

    async resetCache() {
      try {
        await API.resetCache();
        this.showMessage('Caches cleared', 'success');
        await this.fetchAll();
      } catch (e) {
        this.showMessage('Failed to clear caches', 'error');
      }
    },

    // Country Allocation
    startEditCountry() {
      this.countryTargets = {};
      this.activeCountries.forEach(country => {
        this.countryTargets[country] = 0;
      });
      if (this.allocation.country) {
        this.allocation.country.forEach(c => {
          this.countryTargets[c.name] = c.target_pct || 0;
        });
      }
      this.editingCountry = true;
    },

    cancelEditCountry() {
      this.editingCountry = false;
    },

    adjustCountrySlider(changed, newValue) {
      this.countryTargets[changed] = newValue;
    },

    async saveCountryTargets() {
      this.loading.countrySave = true;
      try {
        await API.saveCountryTargets({ ...this.countryTargets });
        this.showMessage('Country weights updated', 'success');
        this.editingCountry = false;
        await this.fetchAllocation();
        await this.fetchSecurities();
      } catch (e) {
        this.showMessage('Failed to save weights', 'error');
      }
      this.loading.countrySave = false;
    },

    // Industry Allocation
    startEditIndustry() {
      this.industryTargets = {};
      this.activeIndustries.forEach(ind => {
        this.industryTargets[ind] = 0;
      });
      if (this.allocation.industry) {
        this.allocation.industry.forEach(ind => {
          this.industryTargets[ind.name] = ind.target_pct || 0;
        });
      }
      this.editingIndustry = true;
    },

    cancelEditIndustry() {
      this.editingIndustry = false;
    },

    adjustIndustrySlider(changed, newValue) {
      this.industryTargets[changed] = newValue;
    },

    async saveIndustryTargets() {
      this.loading.industrySave = true;
      try {
        await API.saveIndustryTargets({ ...this.industryTargets });
        this.showMessage('Industry weights updated', 'success');
        this.editingIndustry = false;
        await this.fetchAllocation();
        await this.fetchSecurities();
      } catch (e) {
        this.showMessage('Failed to save weights', 'error');
      }
      this.loading.industrySave = false;
    },

    // Stock Management
    resetNewSecurity() {
      this.newSecurity = { identifier: '' };
    },

    async addSecurity() {
      if (!this.newSecurity.identifier || !this.newSecurity.identifier.trim()) {
        this.showMessage('Identifier is required', 'error');
        return;
      }
      this.addingSecurity = true;
      try {
        const payload = {
          identifier: this.newSecurity.identifier.trim().toUpperCase()
        };
        await API.addSecurityByIdentifier(payload);
        this.showMessage('Stock added successfully', 'success');
        this.showAddSecurityModal = false;
        this.resetNewSecurity();
        await this.fetchSecurities();
      } catch (e) {
        const errorMessage = e.message || 'Failed to add security';
        this.showMessage(errorMessage, 'error');
      }
      this.addingSecurity = false;
    },

    async removeSecurity(isin) {
      const security = this.securities.find(s => s.isin === isin);
      const displaySymbol = security ? security.symbol : isin;
      if (!confirm(`Remove ${displaySymbol} from the universe?`)) return;
      try {
        await API.deleteSecurity(isin);
        this.showMessage(`${displaySymbol} removed`, 'success');
        await this.fetchSecurities();
      } catch (e) {
        this.showMessage('Failed to remove security', 'error');
      }
    },

    // Universe Management
    async openUniverseManagementModal() {
      this.showUniverseManagementModal = true;
      await this.fetchUniverseSuggestions();
    },

    async fetchUniverseSuggestions() {
      this.loading.universeSuggestions = true;
      try {
        const data = await API.fetchUniverseSuggestions();
        this.universeSuggestions = {
          candidatesToAdd: data.candidates_to_add || [],
          securitiesToPrune: data.securities_to_prune || []
        };
      } catch (e) {
        this.showMessage('Failed to fetch universe suggestions', 'error');
        console.error('Failed to fetch universe suggestions:', e);
      }
      this.loading.universeSuggestions = false;
    },

    async addSecurityFromSuggestion(isin) {
      this.addingFromSuggestion[isin] = true;
      try {
        await API.addSecurityFromSuggestion(isin);
        const candidate = this.universeSuggestions.candidatesToAdd.find(c => c.isin === isin);
        const displaySymbol = candidate ? candidate.symbol : isin;
        this.showMessage(`${displaySymbol} added to universe`, 'success');
        // Remove from candidates list
        this.universeSuggestions.candidatesToAdd = this.universeSuggestions.candidatesToAdd.filter(
          c => c.isin !== isin
        );
        // Refresh securities list
        await this.fetchSecurities();
      } catch (e) {
        const errorMessage = e.message || 'Failed to add security';
        this.showMessage(errorMessage, 'error');
      }
      this.addingFromSuggestion[isin] = false;
    },

    async pruneStockFromSuggestion(isin) {
      this.pruningFromSuggestion[isin] = true;
      try {
        await API.pruneSecurityFromSuggestion(isin);
        const security = this.universeSuggestions.securitiesToPrune.find(s => s.isin === isin);
        const displaySymbol = security ? security.symbol : isin;
        this.showMessage(`${displaySymbol} pruned from universe`, 'success');
        // Remove from prune list
        this.universeSuggestions.securitiesToPrune = this.universeSuggestions.securitiesToPrune.filter(
          s => s.isin !== isin
        );
        // Refresh securities list
        await this.fetchSecurities();
      } catch (e) {
        const errorMessage = e.message || 'Failed to prune security';
        this.showMessage(errorMessage, 'error');
      }
      this.pruningFromSuggestion[isin] = false;
    },

    openEditSecurity(security) {
      this.editingSecurity = {
        originalIsin: security.isin,  // Track original ISIN for API calls
        originalSymbol: security.symbol,  // Track original symbol for rename detection
        symbol: security.symbol,
        isin: security.isin,
        yahoo_symbol: security.yahoo_symbol || '',
        name: security.name,
        country: security.country || '',
        fullExchangeName: security.fullExchangeName || '',
        industry: security.industry || '',
        min_lot: security.min_lot || 1,
        allow_buy: security.allow_buy !== false,  // Default true
        allow_sell: !!security.allow_sell,   // Default false (SQLite stores as 0/1)
        min_portfolio_target: (security.min_portfolio_target != null && security.min_portfolio_target !== '') ? security.min_portfolio_target : null,
        max_portfolio_target: (security.max_portfolio_target != null && security.max_portfolio_target !== '') ? security.max_portfolio_target : null
      };
      this.showEditSecurityModal = true;
    },

    closeEditStock() {
      this.showEditSecurityModal = false;
      this.editingSecurity = null;
    },

    async saveStock() {
      if (!this.editingSecurity) return;

      this.loading.securitySave = true;
      try {
        const payload = {
          name: this.editingSecurity.name,
          yahoo_symbol: this.editingSecurity.yahoo_symbol || null,
          min_lot: parseInt(this.editingSecurity.min_lot) || 1,
          allow_buy: this.editingSecurity.allow_buy,
          allow_sell: this.editingSecurity.allow_sell,
          min_portfolio_target: (this.editingSecurity.min_portfolio_target != null && this.editingSecurity.min_portfolio_target !== '') ? parseFloat(this.editingSecurity.min_portfolio_target) : null,
          max_portfolio_target: (this.editingSecurity.max_portfolio_target != null && this.editingSecurity.max_portfolio_target !== '') ? parseFloat(this.editingSecurity.max_portfolio_target) : null
        };

        // Include new_symbol if symbol was changed
        if (this.editingSecurity.symbol !== this.editingSecurity.originalSymbol) {
          payload.new_symbol = this.editingSecurity.symbol.toUpperCase();
        }

        await API.updateSecurity(this.editingSecurity.originalIsin, payload);
        this.showMessage('Stock updated successfully', 'success');
        this.closeEditStock();
        await this.fetchSecurities();
        await this.fetchAllocation();
      } catch (e) {
        this.showMessage('Failed to update security', 'error');
      }
      this.loading.securitySave = false;
    },

    async updateMultiplier(isin, value) {
      const multiplier = Math.max(0.1, Math.min(3.0, parseFloat(value) || 1.0));
      try {
        await API.updateSecurity(isin, { priority_multiplier: multiplier });
        const security = this.securities.find(s => s.isin === isin);
        if (security) security.priority_multiplier = multiplier;
        await this.fetchSecurities();
      } catch (e) {
        this.showMessage('Failed to update multiplier', 'error');
      }
    },

    // Trading Mode
    async toggleTradingMode() {
      try {
        const result = await API.toggleTradingMode();
        this.tradingMode = result.trading_mode;
        const modeLabel = result.trading_mode === 'research' ? 'Research' : 'Live';
        this.showMessage(`Trading mode set to ${modeLabel}`, 'success');
      } catch (e) {
        console.error('Failed to toggle trading mode:', e);
        this.showMessage('Failed to toggle trading mode', 'error');
      }
    },

    // Logs
    async fetchAvailableLogFiles() {
      try {
        const result = await API.fetchAvailableLogFiles();
        if (result.status === 'ok') {
          this.logs.availableLogFiles = result.log_files || [];
        }
      } catch (e) {
        console.error('Failed to fetch available log files:', e);
      }
    },

    async fetchLogs() {
      if (this.logs.loading) return;
      this.logs.loading = true;

      try {
        let result;
        if (this.logs.showErrorsOnly) {
          result = await API.fetchErrorLogs(this.logs.selectedLogFile, this.logs.lineCount);
        } else {
          result = await API.fetchLogs(
            this.logs.selectedLogFile,
            this.logs.lineCount,
            this.logs.filterLevel,
            this.logs.searchQuery || null
          );
        }

        if (result.status === 'ok') {
          this.logs.entries = result.logs || [];
          this.logs.totalLines = result.total_lines || result.total_error_lines || 0;
          this.logs.returnedLines = result.returned_lines || 0;
          this.logs.logPath = result.log_path || result.log_file || '';
          this.logs.lastRefresh = new Date();
        } else {
          this.logs.entries = [];
          this.showMessage(result.message || 'Failed to fetch logs', 'error');
        }
      } catch (e) {
        console.error('Failed to fetch logs:', e);
        this.logs.entries = [];
        this.showMessage('Failed to fetch logs', 'error');
      } finally {
        this.logs.loading = false;
      }
    },

    startLogsAutoRefresh() {
      if (this.logs.refreshTimer) return; // Already running
      if (!this.logs.autoRefresh) return;

      // Fetch immediately
      this.fetchLogs();

      // Set up interval
      this.logs.refreshTimer = setInterval(() => {
        if (this.activeTab === 'logs' && this.logs.autoRefresh) {
          this.fetchLogs();
        }
      }, this.logs.refreshInterval);
    },

    stopLogsAutoRefresh() {
      if (this.logs.refreshTimer) {
        clearInterval(this.logs.refreshTimer);
        this.logs.refreshTimer = null;
      }
    },

    // Watch for tab changes to start/stop auto-refresh
    watchActiveTab() {
      // This will be called when activeTab changes
      if (this.activeTab === 'logs') {
        // Load available log files if not loaded
        if (this.logs.availableLogFiles.length === 0) {
          this.fetchAvailableLogFiles();
        }
        this.startLogsAutoRefresh();
      } else {
        this.stopLogsAutoRefresh();
      }
    },

    // Utilities
    showMessage(msg, type) {
      this.message = msg;
      this.messageType = type;
      setTimeout(() => { this.message = ''; }, 5000);
    }
  });
});
