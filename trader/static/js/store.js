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
    buckets: [],  // [{id: 'core', name: 'Core', type: 'core', status: 'active', ...}]
    bucketBalances: {},  // {bucket_id: {EUR: 1000, USD: 500, ...}}
    selectedBucket: null,  // Currently selected bucket for health modal
    tradernet: { connected: false },
    tradernetConnectionStatus: null,  // null, true, or false
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
    showBucketHealthModal: false,
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
      tradernetTest: false
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

    // Add Security Form
    newSecurity: { identifier: '' },
    addingSecurity: false,

    // Planner Management
    planners: [],                          // List of all planner configs
    plannerBuckets: [],                    // List of buckets for assignment
    selectedPlannerId: '',                 // Currently selected planner ID
    plannerFormMode: 'none',               // 'none', 'edit', 'create'
    plannerForm: {                         // Form data
      id: '',
      name: '',
      toml: '',
      bucket_id: null
    },
    showPlannerManagementModal: false,     // Modal visibility
    plannerLoading: false,                 // Loading state
    plannerError: null,                    // Validation/save errors
    showPlannerHistory: false,             // History viewer visibility
    plannerHistory: [],                    // Version history entries
    plannerHistoryLoading: false,          // History loading state
    showPlannerDiffModal: false,           // Diff modal visibility
    plannerDiffHtml: '',                   // Rendered diff HTML

    // Universe/Bucket Management
    newUniverseName: '',
    creatingUniverse: false,
    loadingBuckets: false,
    cashTransfer: {
      fromBucket: '',
      toBucket: '',
      amount: '',
      currency: 'EUR',
      description: ''
    },
    transferringCash: false,

    // Fetch All Data
    async fetchAll() {
      await Promise.all([
        this.fetchStatus(),
        this.fetchAllocation(),
        this.fetchCashBreakdown(),
        this.fetchSecurities(),
        this.fetchTrades(),
        this.fetchBuckets(),
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

    async fetchBuckets() {
      try {
        this.loadingBuckets = true;
        this.buckets = await API.fetchBuckets();

        // Fetch balances for all buckets
        const balances = await API.fetchAllBucketBalances();
        this.bucketBalances = balances;

        this.loadingBuckets = false;
      } catch (e) {
        console.error('Failed to fetch buckets:', e);
        this.loadingBuckets = false;
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
        const response = await fetch('/api/system/markets');
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
      const eventSource = new EventSource('/api/planning/stream');
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
      const eventSource = new EventSource('/api/planning/stream');
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
      // Handle string settings (like credentials)
      const stringSettings = ['tradernet_api_key', 'tradernet_api_secret', 'trading_mode', 'display_mode'];
      if (stringSettings.includes(key)) {
        try {
          await API.updateSetting(key, value);
          this.settings[key] = value;
          this.showMessage(`Setting "${key}" updated`, 'success');
        } catch (e) {
          this.showMessage(`Failed to update ${key}`, 'error');
        }
        return;
      }

      // Handle numeric settings
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

    async testTradernetConnection() {
      console.log('testTradernetConnection called');
      this.loading.tradernetTest = true;
      this.tradernetConnectionStatus = null;
      try {
        console.log('Calling API.testTradernetConnection()');
        const result = await API.testTradernetConnection();
        console.log('API result:', result);
        this.tradernetConnectionStatus = result.connected || false;
        if (this.tradernetConnectionStatus) {
          this.showMessage('Tradernet connection successful', 'success');
        } else {
          this.showMessage(`Tradernet connection failed: ${result.message || 'check credentials'}`, 'error');
        }
      } catch (e) {
        console.error('Error testing Tradernet connection:', e);
        this.tradernetConnectionStatus = false;
        this.showMessage(`Failed to test Tradernet connection: ${e.message}`, 'error');
      } finally {
        this.loading.tradernetTest = false;
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

    // TEST Currency Inline Editing
    startEditTestCash(currentAmount) {
      const newAmount = prompt(
        'Enter TEST currency amount (EUR equivalent):',
        currentAmount.toString()
      );

      if (newAmount !== null) {
        const amount = parseFloat(newAmount);
        if (isNaN(amount) || amount < 0) {
          alert('Please enter a valid non-negative number');
          return;
        }

        this.saveTestCash(amount);
      }
    },

    async saveTestCash(amount) {
      try {
        await api.updateSetting('virtual_test_cash', amount);

        // Refresh cash breakdown to show updated TEST amount
        await this.fetchCashBreakdown();

        // Refresh recommendations (they'll be recalculated with new cash)
        await this.fetchRecommendations();

        console.log(`TEST currency updated to ${amount}`);
      } catch (error) {
        console.error('Failed to update TEST cash:', error);
        alert('Failed to update TEST cash. Please try again.');
      }
    },

    // Security Management
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
        this.showMessage('Security added successfully', 'success');
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
        bucket_id: security.bucket_id || 'core',  // Universe/bucket assignment
        min_lot: security.min_lot || 1,
        allow_buy: security.allow_buy !== false,  // Default true
        allow_sell: !!security.allow_sell,   // Default false (SQLite stores as 0/1)
        min_portfolio_target: (security.min_portfolio_target != null && security.min_portfolio_target !== '') ? security.min_portfolio_target : null,
        max_portfolio_target: (security.max_portfolio_target != null && security.max_portfolio_target !== '') ? security.max_portfolio_target : null
      };
      this.showEditSecurityModal = true;
    },

    closeEditSecurity() {
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
          bucket_id: this.editingSecurity.bucket_id || 'core',
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
        this.showMessage('Security updated successfully', 'success');
        this.closeEditSecurity();
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

    // Planner Management
    async openPlannerManagement() {
      this.showPlannerManagementModal = true;
      this.plannerFormMode = 'none';
      this.selectedPlannerId = '';
      this.plannerError = null;
      await Promise.all([
        this.fetchPlanners(),
        this.fetchPlannerBuckets()
      ]);
    },

    async fetchPlannerBuckets() {
      try {
        this.plannerBuckets = await API.fetchBuckets();
      } catch (e) {
        console.error('Failed to fetch buckets:', e);
        this.plannerBuckets = [];
      }
    },

    async fetchPlanners() {
      this.plannerLoading = true;
      try {
        this.planners = await API.fetchPlanners();
      } catch (e) {
        this.plannerError = e.message || 'Failed to fetch planners';
        console.error('Failed to fetch planners:', e);
      } finally {
        this.plannerLoading = false;
      }
    },

    async loadSelectedPlanner() {
      if (!this.selectedPlannerId) {
        this.plannerFormMode = 'none';
        return;
      }
      this.plannerLoading = true;
      this.plannerError = null;
      try {
        const planner = await API.fetchPlannerById(this.selectedPlannerId);
        this.plannerForm = {
          id: planner.id,
          name: planner.name,
          toml: planner.toml_config,
          bucket_id: planner.bucket_id
        };
        this.plannerFormMode = 'edit';
      } catch (e) {
        this.plannerError = e.message || 'Failed to load planner';
        console.error('Failed to load planner:', e);
      } finally {
        this.plannerLoading = false;
      }
    },

    startCreatePlanner() {
      this.selectedPlannerId = '';
      this.plannerForm = {
        id: '',
        name: '',
        toml: '# New planner configuration\n',
        bucket_id: null
      };
      this.plannerFormMode = 'create';
      this.plannerError = null;
    },

    loadPlannerTemplate(templateName) {
      const templates = {
        conservative: {
          name: 'Conservative Strategy',
          toml: `[planner]
name = "Conservative Strategy"
description = "Low-risk, value-focused investment strategy"

[[calculators]]
name = "value"
type = "value"
weight = 2.0

[[calculators]]
name = "quality"
type = "quality"
weight = 1.5

[[calculators]]
name = "low_volatility"
type = "low_volatility"
weight = 1.0

[[patterns]]
name = "diversification"
type = "diversification"
min_holdings = 15
max_concentration = 0.15

[[generators]]
name = "incremental"
type = "incremental"
max_depth = 3
`
        },
        balanced: {
          name: 'Balanced Growth',
          toml: `[planner]
name = "Balanced Growth"
description = "Balanced approach combining growth and value"

[[calculators]]
name = "momentum"
type = "momentum"
weight = 1.5

[[calculators]]
name = "value"
type = "value"
weight = 1.5

[[calculators]]
name = "growth"
type = "growth"
weight = 1.0

[[patterns]]
name = "sector_balance"
type = "sector_balance"
max_sector_weight = 0.30

[[generators]]
name = "combinatorial"
type = "combinatorial"
max_depth = 5
max_candidates = 10
`
        },
        aggressive: {
          name: 'Aggressive Growth',
          toml: `[planner]
name = "Aggressive Growth"
description = "High-growth, momentum-driven strategy"

[[calculators]]
name = "momentum"
type = "momentum"
weight = 2.5

[[calculators]]
name = "growth"
type = "growth"
weight = 2.0

[[calculators]]
name = "small_cap_premium"
type = "size"
weight = 1.0

[[patterns]]
name = "high_conviction"
type = "concentration"
min_holdings = 8
max_concentration = 0.25

[[generators]]
name = "opportunistic"
type = "opportunistic"
max_depth = 7
enable_combinatorial = true
`
        }
      };

      const template = templates[templateName];
      if (template) {
        this.plannerForm.name = template.name;
        this.plannerForm.toml = template.toml;
        this.showMessage(`Loaded ${template.name} template`, 'success');
      }
    },

    async savePlanner() {
      this.plannerLoading = true;
      this.plannerError = null;
      try {
        // Validate TOML first
        const validation = await API.validatePlannerToml(this.plannerForm.toml);
        if (!validation.valid) {
          this.plannerError = validation.error;
          this.plannerLoading = false;
          return;
        }

        if (this.plannerFormMode === 'create') {
          await API.createPlanner({
            name: this.plannerForm.name,
            toml_config: this.plannerForm.toml,
            bucket_id: this.plannerForm.bucket_id
          });
          this.showMessage('Planner created successfully', 'success');
        } else {
          await API.updatePlanner(this.plannerForm.id, {
            name: this.plannerForm.name,
            toml_config: this.plannerForm.toml,
            bucket_id: this.plannerForm.bucket_id || ''
          });
          this.showMessage('Planner updated successfully', 'success');
        }

        // Reload planners list
        await this.fetchPlanners();

        // Reset form
        this.plannerFormMode = 'none';
        this.selectedPlannerId = '';
      } catch (e) {
        this.plannerError = e.message || 'Failed to save planner';
        console.error('Failed to save planner:', e);
      } finally {
        this.plannerLoading = false;
      }
    },

    async deletePlanner() {
      if (!confirm('Are you sure you want to delete this planner configuration?')) {
        return;
      }
      this.plannerLoading = true;
      this.plannerError = null;
      try {
        await API.deletePlanner(this.plannerForm.id);
        this.showMessage('Planner deleted successfully', 'success');
        await this.fetchPlanners();
        this.plannerFormMode = 'none';
        this.selectedPlannerId = '';
      } catch (e) {
        this.plannerError = e.message || 'Failed to delete planner';
        console.error('Failed to delete planner:', e);
      } finally {
        this.plannerLoading = false;
      }
    },

    async applyPlannerConfig() {
      if (!this.plannerForm.id || !this.plannerForm.bucket_id) {
        this.plannerError = 'Cannot apply: planner has no associated bucket';
        return;
      }
      this.plannerLoading = true;
      this.plannerError = null;
      try {
        const result = await API.applyPlanner(this.plannerForm.id);

        // Clear old sequences so new ones are generated with updated config
        await API.regenerateSequences();

        this.showMessage(
          `Planner applied and sequences regenerated for bucket ${result.bucket_id}`,
          'success'
        );
      } catch (e) {
        this.plannerError = e.message || 'Failed to apply planner';
        console.error('Failed to apply planner:', e);
      } finally {
        this.plannerLoading = false;
      }
    },

    async togglePlannerHistory() {
      this.showPlannerHistory = !this.showPlannerHistory;
      if (this.showPlannerHistory && this.plannerHistory.length === 0) {
        await this.fetchPlannerHistory();
      }
    },

    async fetchPlannerHistory() {
      if (!this.plannerForm.id) return;
      this.plannerHistoryLoading = true;
      try {
        this.plannerHistory = await API.fetchPlannerHistory(this.plannerForm.id);
      } catch (e) {
        console.error('Failed to fetch planner history:', e);
        this.plannerHistory = [];
      } finally {
        this.plannerHistoryLoading = false;
      }
    },

    restorePlannerVersion(historyEntry) {
      if (!confirm(`Restore configuration from ${new Date(historyEntry.saved_at).toLocaleString()}?`)) {
        return;
      }
      // Update form with historical values
      this.plannerForm.name = historyEntry.name;
      this.plannerForm.toml = historyEntry.toml_config;
      this.showMessage('Historical version loaded. Click Save to apply.', 'success');
      this.showPlannerHistory = false;
    },

    showPlannerDiff(historyEntry) {
      // Show diff between historical version and current version
      if (!window.createDiffViewer) {
        this.showMessage('Diff viewer not available', 'error');
        return;
      }

      const oldText = historyEntry.toml_config || '';
      const newText = this.plannerForm.toml || '';
      const oldLabel = `${historyEntry.name} (${new Date(historyEntry.saved_at).toLocaleString()})`;
      const newLabel = 'Current version';

      const diffHtml = window.createDiffViewer(oldText, newText, oldLabel, newLabel);

      // Store diff HTML to be displayed in modal
      this.plannerDiffHtml = diffHtml;
      this.showPlannerDiffModal = true;
    },

    closePlannerDiff() {
      this.showPlannerDiffModal = false;
      this.plannerDiffHtml = '';
    },

    closePlannerManagement() {
      this.showPlannerManagementModal = false;
      this.plannerFormMode = 'none';
      this.selectedPlannerId = '';
      this.plannerError = null;
      this.showPlannerHistory = false;
      this.plannerHistory = [];
    },

    // Bucket/Universe Management
    async createUniverse() {
      if (!this.newUniverseName.trim()) {
        this.showMessage('Please enter a universe name', 'error');
        return;
      }

      this.creatingUniverse = true;
      try {
        await API.createBucket({
          name: this.newUniverseName.trim(),
          type: 'satellite'
        });
        this.showMessage('Universe created successfully', 'success');
        this.newUniverseName = '';
        await this.fetchBuckets();
      } catch (e) {
        console.error('Failed to create universe:', e);
        this.showMessage(`Failed to create universe: ${e.message}`, 'error');
      }
      this.creatingUniverse = false;
    },

    async retireUniverse(bucketId) {
      if (!confirm('Are you sure you want to retire this universe? This action cannot be undone.')) {
        return;
      }

      try {
        await API.retireBucket(bucketId);
        this.showMessage('Universe retired successfully', 'success');
        await this.fetchBuckets();
        if (this.selectedBucket && this.selectedBucket.id === bucketId) {
          this.closeBucketHealth();
        }
      } catch (e) {
        console.error('Failed to retire universe:', e);
        this.showMessage(`Failed to retire universe: ${e.message}`, 'error');
      }
    },

    openBucketHealth(bucket) {
      this.selectedBucket = bucket;
      this.showBucketHealthModal = true;
    },

    closeBucketHealth() {
      this.showBucketHealthModal = false;
      this.selectedBucket = null;
      // Reset cash transfer form
      this.cashTransfer = {
        fromBucket: '',
        toBucket: '',
        amount: '',
        currency: 'EUR',
        description: ''
      };
    },

    async executeCashTransfer() {
      if (!this.cashTransfer.fromBucket || !this.cashTransfer.toBucket || !this.cashTransfer.amount) {
        this.showMessage('Please fill in all required fields', 'error');
        return;
      }

      if (this.cashTransfer.fromBucket === this.cashTransfer.toBucket) {
        this.showMessage('Source and destination must be different', 'error');
        return;
      }

      this.transferringCash = true;
      try {
        await API.transferCash({
          from_bucket: this.cashTransfer.fromBucket,
          to_bucket: this.cashTransfer.toBucket,
          amount: parseFloat(this.cashTransfer.amount),
          currency: this.cashTransfer.currency,
          description: this.cashTransfer.description || null
        });
        this.showMessage('Cash transfer completed successfully', 'success');
        // Reset form
        this.cashTransfer = {
          fromBucket: '',
          toBucket: '',
          amount: '',
          currency: 'EUR',
          description: ''
        };
        await this.fetchBuckets();
      } catch (e) {
        console.error('Failed to transfer cash:', e);
        this.showMessage(`Failed to transfer cash: ${e.message}`, 'error');
      }
      this.transferringCash = false;
    },

    getSecurityCountForBucket(bucketId) {
      return this.securities.filter(s => (s.bucket_id || 'core') === bucketId).length;
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
