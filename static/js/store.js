/**
 * Arduino Trader - Alpine.js Store
 * Centralized state management for the application
 */

document.addEventListener('alpine:init', () => {
  Alpine.store('app', {
    // Data
    status: {},
    allocation: {
      geographic: [],
      industry: [],
      total_value: 0,
      cash_balance: 0
    },
    cashBreakdown: [],  // [{currency: 'EUR', amount: 1000}, ...]
    stocks: [],
    trades: [],
    tradernet: { connected: false },
    recommendations: [],
    sellRecommendations: [],
    settings: { min_trade_size: 400 },
    sparklines: {},  // {symbol: [{time, value}, ...]}

    // UI State - Filters
    stockFilter: 'all',
    industryFilter: 'all',
    searchQuery: '',
    minScore: 0,
    sortBy: 'priority_score',
    sortDesc: true,
    showAddStockModal: false,
    showEditStockModal: false,
    showStockChart: false,
    showSettingsModal: false,
    showFundingModal: false,
    selectedStockSymbol: null,
    editingStock: null,
    executingSymbol: null,
    executingSellSymbol: null,
    message: '',
    messageType: 'success',

    // Funding Modal State
    fundingTarget: null,
    fundingOptions: [],
    fundingData: null,
    loadingFundingOptions: false,
    executingFunding: false,
    seenFundingSignatures: [],
    hasMoreFundingOptions: false,
    loadingMoreFundingOptions: false,

    // Loading States
    loading: {
      recommendations: false,
      sellRecommendations: false,
      scores: false,
      sync: false,
      historical: false,
      execute: false,
      geoSave: false,
      industrySave: false,
      stockSave: false
    },

    // Edit Mode States
    editingGeo: false,
    geoTargets: {},
    geographies: [],
    editingIndustry: false,
    industryTargets: {},

    // Add Stock Form
    newStock: { symbol: '', name: '', geography: '', industry: '' },
    addingStock: false,

    // Fetch All Data
    async fetchAll() {
      await Promise.all([
        this.fetchStatus(),
        this.fetchAllocation(),
        this.fetchCashBreakdown(),
        this.fetchStocks(),
        this.fetchTrades(),
        this.fetchTradernet(),
        this.fetchGeographies(),
        this.fetchRecommendations(),
        this.fetchSellRecommendations(),
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
        this.allocation = await API.fetchAllocation();
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

    async fetchStocks() {
      try {
        this.stocks = await API.fetchStocks();
      } catch (e) {
        console.error('Failed to fetch stocks:', e);
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

    async fetchGeographies() {
      try {
        const data = await API.fetchTargets();
        this.geographies = Object.keys(data.geography || {});
        this.geoTargets = {};
        for (const [name, weight] of Object.entries(data.geography || {})) {
          this.geoTargets[name] = weight;
        }
        if (!this.newStock.geography && this.geographies.length > 0) {
          this.newStock.geography = this.geographies[0];
        }
      } catch (e) {
        console.error('Failed to fetch geographies:', e);
      }
    },

    async fetchRecommendations() {
      this.loading.recommendations = true;
      try {
        const data = await API.fetchRecommendations();
        this.recommendations = data.recommendations || [];
      } catch (e) {
        console.error('Failed to fetch recommendations:', e);
      }
      this.loading.recommendations = false;
    },

    async fetchSellRecommendations() {
      this.loading.sellRecommendations = true;
      try {
        const data = await API.fetchSellRecommendations();
        this.sellRecommendations = data.recommendations || [];
      } catch (e) {
        console.error('Failed to fetch sell recommendations:', e);
      }
      this.loading.sellRecommendations = false;
    },

    async fetchSettings() {
      try {
        this.settings = await API.fetchSettings();
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

    async updateMinTradeSize(value) {
      const numValue = parseFloat(value);
      if (isNaN(numValue) || numValue <= 0) return;
      try {
        await API.updateMinTradeSize(numValue);
        this.settings.min_trade_size = numValue;
        this.showMessage('Min trade size updated', 'success');
        await this.fetchRecommendations();
      } catch (e) {
        this.showMessage('Failed to update min trade size', 'error');
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

    async executeRecommendation(symbol) {
      this.loading.execute = true;
      this.executingSymbol = symbol;
      try {
        const result = await API.executeRecommendation(symbol);
        this.showMessage(`Executed: ${result.quantity} ${symbol} @ €${result.price}`, 'success');
        await this.fetchAll();
      } catch (e) {
        this.showMessage('Failed to execute trade', 'error');
      }
      this.executingSymbol = null;
      this.loading.execute = false;
    },

    async executeSellRecommendation(symbol) {
      this.loading.execute = true;
      this.executingSellSymbol = symbol;
      try {
        const result = await API.executeSellRecommendation(symbol);
        this.showMessage(`Sold: ${result.quantity} ${symbol} @ €${result.price}`, 'success');
        await this.fetchAll();
      } catch (e) {
        this.showMessage('Failed to execute sell', 'error');
      }
      this.executingSellSymbol = null;
      this.loading.execute = false;
    },

    // Funding Methods
    async openFundingModal(recommendation) {
      this.fundingTarget = recommendation;
      this.showFundingModal = true;
      this.loadingFundingOptions = true;
      this.fundingOptions = [];
      this.fundingData = null;
      this.seenFundingSignatures = [];
      this.hasMoreFundingOptions = false;

      try {
        const data = await API.getFundingOptions(recommendation.symbol);
        this.fundingData = data;
        this.fundingOptions = data.options || [];
        this.hasMoreFundingOptions = data.has_more || false;
        // Track seen signatures for pagination
        this.seenFundingSignatures = (data.options || []).map(opt => opt.signature);
      } catch (e) {
        console.error('Failed to fetch funding options:', e);
        this.showMessage('Failed to fetch funding options', 'error');
      }
      this.loadingFundingOptions = false;
    },

    async loadMoreFundingOptions() {
      if (!this.fundingTarget || this.loadingMoreFundingOptions) return;

      this.loadingMoreFundingOptions = true;
      try {
        const excludeList = this.seenFundingSignatures.join(',');
        const data = await API.getFundingOptions(this.fundingTarget.symbol, excludeList);
        const newOptions = data.options || [];

        // Add new options and track their signatures
        this.fundingOptions = [...this.fundingOptions, ...newOptions];
        newOptions.forEach(opt => this.seenFundingSignatures.push(opt.signature));
        this.hasMoreFundingOptions = data.has_more && newOptions.length > 0;
      } catch (e) {
        console.error('Failed to load more funding options:', e);
        this.showMessage('Failed to load more options', 'error');
      }
      this.loadingMoreFundingOptions = false;
    },

    closeFundingModal() {
      this.showFundingModal = false;
      this.fundingTarget = null;
      this.fundingOptions = [];
      this.fundingData = null;
      this.seenFundingSignatures = [];
      this.hasMoreFundingOptions = false;
    },

    async executeFunding(option) {
      if (!this.fundingTarget) return;

      this.executingFunding = true;
      try {
        const sells = option.sells.map(s => ({
          symbol: s.symbol,
          quantity: s.quantity
        }));

        const result = await API.executeFunding(this.fundingTarget.symbol, {
          strategy: option.strategy,
          sells: sells
        });

        if (result.status === 'success') {
          this.showMessage(
            `Funding complete: Sold ${result.sells.length} position(s), bought ${result.buy.quantity} ${result.buy.symbol}`,
            'success'
          );
        } else {
          this.showMessage(result.message || 'Partial success - check trades', 'warning');
        }

        this.closeFundingModal();
        await this.fetchAll();
      } catch (e) {
        console.error('Failed to execute funding:', e);
        this.showMessage('Failed to execute funding plan', 'error');
      }
      this.executingFunding = false;
    },

    // Computed Properties
    get industries() {
      const set = new Set();
      this.stocks.forEach(s => {
        if (s.industry) {
          s.industry.split(',').forEach(ind => {
            const trimmed = ind.trim();
            if (trimmed) set.add(trimmed);
          });
        }
      });
      return Array.from(set).sort();
    },

    get activeGeographies() {
      const geos = new Set(this.stocks.map(s => s.geography).filter(Boolean));
      return Array.from(geos).sort();
    },

    get activeIndustries() {
      const inds = new Set();
      this.stocks.forEach(s => {
        if (s.industry) {
          s.industry.split(',').forEach(i => inds.add(i.trim()));
        }
      });
      return Array.from(inds).sort();
    },

    get filteredStocks() {
      let filtered = this.stocks;

      if (this.stockFilter !== 'all') {
        filtered = filtered.filter(s => s.geography === this.stockFilter);
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

    sortStocks(field) {
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
        await this.fetchStocks();
      } catch (e) {
        this.showMessage('Failed to refresh scores', 'error');
      }
      this.loading.scores = false;
    },

    async refreshSingleScore(symbol) {
      try {
        await API.refreshScore(symbol);
        await this.fetchStocks();
      } catch (e) {
        this.showMessage('Failed to refresh score', 'error');
      }
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

    // Geographic Allocation
    startEditGeo() {
      this.geoTargets = {};
      this.activeGeographies.forEach(geo => {
        this.geoTargets[geo] = 0;
      });
      if (this.allocation.geographic) {
        this.allocation.geographic.forEach(g => {
          this.geoTargets[g.name] = g.target_pct || 0;
        });
      }
      this.editingGeo = true;
    },

    cancelEditGeo() {
      this.editingGeo = false;
    },

    adjustGeoSlider(changed, newValue) {
      this.geoTargets[changed] = newValue;
    },

    async saveGeoTargets() {
      this.loading.geoSave = true;
      try {
        await API.saveGeoTargets({ ...this.geoTargets });
        this.showMessage('Geographic weights updated', 'success');
        this.editingGeo = false;
        await this.fetchAllocation();
        await this.fetchStocks();
      } catch (e) {
        this.showMessage('Failed to save weights', 'error');
      }
      this.loading.geoSave = false;
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
        await this.fetchStocks();
      } catch (e) {
        this.showMessage('Failed to save weights', 'error');
      }
      this.loading.industrySave = false;
    },

    // Stock Management
    resetNewStock() {
      this.newStock = { symbol: '', name: '', geography: 'EU', industry: '' };
    },

    async addStock() {
      if (!this.newStock.symbol || !this.newStock.name) {
        this.showMessage('Symbol and name are required', 'error');
        return;
      }
      this.addingStock = true;
      try {
        const payload = {
          symbol: this.newStock.symbol.toUpperCase(),
          name: this.newStock.name,
          geography: this.newStock.geography
        };
        if (this.newStock.industry) {
          payload.industry = this.newStock.industry;
        }
        await API.createStock(payload);
        this.showMessage('Stock added successfully', 'success');
        this.showAddStockModal = false;
        this.resetNewStock();
        await this.fetchStocks();
      } catch (e) {
        this.showMessage('Failed to add stock', 'error');
      }
      this.addingStock = false;
    },

    async removeStock(symbol) {
      if (!confirm(`Remove ${symbol} from the universe?`)) return;
      try {
        await API.deleteStock(symbol);
        this.showMessage(`${symbol} removed`, 'success');
        await this.fetchStocks();
      } catch (e) {
        this.showMessage('Failed to remove stock', 'error');
      }
    },

    openEditStock(stock) {
      this.editingStock = {
        originalSymbol: stock.symbol,  // Track original for rename detection
        symbol: stock.symbol,
        yahoo_symbol: stock.yahoo_symbol || '',
        name: stock.name,
        geography: stock.geography,
        industry: stock.industry || '',
        min_lot: stock.min_lot || 1,
        allow_buy: stock.allow_buy !== false,  // Default true
        allow_sell: !!stock.allow_sell   // Default false (SQLite stores as 0/1)
      };
      this.showEditStockModal = true;
    },

    closeEditStock() {
      this.showEditStockModal = false;
      this.editingStock = null;
    },

    async saveStock() {
      if (!this.editingStock) return;

      this.loading.stockSave = true;
      try {
        const payload = {
          name: this.editingStock.name,
          yahoo_symbol: this.editingStock.yahoo_symbol || null,
          geography: this.editingStock.geography,
          industry: this.editingStock.industry || null,
          min_lot: parseInt(this.editingStock.min_lot) || 1,
          allow_buy: this.editingStock.allow_buy,
          allow_sell: this.editingStock.allow_sell
        };

        // Include new_symbol if symbol was changed
        if (this.editingStock.symbol !== this.editingStock.originalSymbol) {
          payload.new_symbol = this.editingStock.symbol.toUpperCase();
        }

        await API.updateStock(this.editingStock.originalSymbol, payload);
        this.showMessage('Stock updated successfully', 'success');
        this.closeEditStock();
        await this.fetchStocks();
        await this.fetchAllocation();
      } catch (e) {
        this.showMessage('Failed to update stock', 'error');
      }
      this.loading.stockSave = false;
    },

    async updateMultiplier(symbol, value) {
      const multiplier = Math.max(0.1, Math.min(3.0, parseFloat(value) || 1.0));
      try {
        await API.updateStock(symbol, { priority_multiplier: multiplier });
        const stock = this.stocks.find(s => s.symbol === symbol);
        if (stock) stock.priority_multiplier = multiplier;
        await this.fetchStocks();
      } catch (e) {
        this.showMessage('Failed to update multiplier', 'error');
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
