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
    stocks: [],
    trades: [],
    tradernet: { connected: false },
    recommendations: [],
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
    selectedStockSymbol: null,
    editingStock: null,
    executingSymbol: null,
    message: '',
    messageType: 'success',

    // Loading States
    loading: {
      recommendations: false,
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
        this.fetchStocks(),
        this.fetchTrades(),
        this.fetchTradernet(),
        this.fetchGeographies(),
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
        this.allocation = await API.fetchAllocation();
      } catch (e) {
        console.error('Failed to fetch allocation:', e);
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
        symbol: stock.symbol,
        yahoo_symbol: stock.yahoo_symbol || '',
        name: stock.name,
        geography: stock.geography,
        industry: stock.industry || '',
        min_lot: stock.min_lot || 1
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
        await API.updateStock(this.editingStock.symbol, {
          name: this.editingStock.name,
          yahoo_symbol: this.editingStock.yahoo_symbol || null,
          geography: this.editingStock.geography,
          industry: this.editingStock.industry || null,
          min_lot: parseInt(this.editingStock.min_lot) || 1
        });
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
