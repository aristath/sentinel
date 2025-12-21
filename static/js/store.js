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
    pnl: {
      pnl: null,
      pnl_pct: null,
      total_value: null,
      net_deposits: null,
      loading: false,
      error: null
    },

    // UI State - Filters
    stockFilter: 'all',
    industryFilter: 'all',
    searchQuery: '',
    minScore: 0,
    sortBy: 'priority_score',
    sortDesc: true,
    showRebalanceModal: false,
    showAddStockModal: false,
    showEditStockModal: false,
    editingStock: null,
    rebalancePreview: null,
    message: '',
    messageType: 'success',

    // Loading States
    loading: {
      rebalance: false,
      scores: false,
      sync: false,
      execute: false,
      geoSave: false,
      industrySave: false,
      stockSave: false
    },

    // Edit Mode States
    editingGeo: false,
    geoTargets: {},  // Dynamic - populated from API
    geographies: [],  // Available geography options
    editingIndustry: false,
    industryTargets: {},  // Dynamic - populated from API

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
        this.fetchPnl()
      ]);
    },

    // Fetch available geographies
    async fetchGeographies() {
      try {
        const res = await fetch('/api/allocation/targets');
        const data = await res.json();
        // Extract geography names and weights (stored as -1 to +1)
        this.geographies = Object.keys(data.geography || {});
        this.geoTargets = {};
        for (const [name, weight] of Object.entries(data.geography || {})) {
          this.geoTargets[name] = weight;  // Store weight directly
        }
        // Set default geography for new stock if not set
        if (!this.newStock.geography && this.geographies.length > 0) {
          this.newStock.geography = this.geographies[0];
        }
      } catch (e) {
        console.error('Failed to fetch geographies:', e);
      }
    },

    async fetchStatus() {
      try {
        const res = await fetch('/api/status');
        this.status = await res.json();
      } catch (e) {
        console.error('Failed to fetch status:', e);
      }
    },

    async fetchAllocation() {
      try {
        const res = await fetch('/api/trades/allocation');
        this.allocation = await res.json();
      } catch (e) {
        console.error('Failed to fetch allocation:', e);
      }
    },

    async fetchStocks() {
      try {
        const res = await fetch('/api/stocks');
        this.stocks = await res.json();
      } catch (e) {
        console.error('Failed to fetch stocks:', e);
      }
    },

    async fetchTrades() {
      try {
        const res = await fetch('/api/trades');
        this.trades = await res.json();
      } catch (e) {
        console.error('Failed to fetch trades:', e);
      }
    },

    async fetchTradernet() {
      try {
        const res = await fetch('/api/status/tradernet');
        this.tradernet = await res.json();
      } catch (e) {
        console.error('Failed to fetch tradernet status:', e);
      }
    },

    async fetchPnl() {
      this.pnl.loading = true;
      this.pnl.error = null;
      try {
        const res = await fetch('/api/portfolio/pnl');
        const data = await res.json();
        if (data.error) {
          this.pnl.error = data.error;
        } else {
          this.pnl.pnl = data.pnl;
          this.pnl.pnl_pct = data.pnl_pct;
          this.pnl.total_value = data.total_value;
          this.pnl.net_deposits = data.net_deposits;
          this.pnl.deposits_set = data.deposits_set;
          this.pnl.manual_deposits = data.manual_deposits;
          this.pnl.total_withdrawals = data.total_withdrawals;
        }
      } catch (e) {
        console.error('Failed to fetch P&L:', e);
        this.pnl.error = 'Failed to fetch P&L data';
      }
      this.pnl.loading = false;
    },

    async setManualDeposits(amount) {
      try {
        const res = await fetch('/api/portfolio/deposits', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount: parseFloat(amount) })
        });
        if (res.ok) {
          this.showMessage('Deposits updated', 'success');
          await this.fetchPnl();
        } else {
          this.showMessage('Failed to update deposits', 'error');
        }
      } catch (e) {
        this.showMessage('Failed to update deposits', 'error');
      }
    },

    // Get unique industries for filter dropdown (handles comma-separated)
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

    // Get active geographies (derived from actual stocks, not allocation targets)
    get activeGeographies() {
      const geos = new Set(this.stocks.map(s => s.geography).filter(Boolean));
      return Array.from(geos).sort();
    },

    // Get active industries (derived from actual stocks, not allocation targets)
    get activeIndustries() {
      const inds = new Set();
      this.stocks.forEach(s => {
        if (s.industry) {
          s.industry.split(',').forEach(i => inds.add(i.trim()));
        }
      });
      return Array.from(inds).sort();
    },

    // Filtered & Sorted Stocks
    get filteredStocks() {
      let filtered = this.stocks;

      // Region filter
      if (this.stockFilter !== 'all') {
        filtered = filtered.filter(s => s.geography === this.stockFilter);
      }

      // Industry filter (handles comma-separated industries)
      if (this.industryFilter !== 'all') {
        filtered = filtered.filter(s => {
          if (!s.industry) return false;
          const industries = s.industry.split(',').map(i => i.trim());
          return industries.includes(this.industryFilter);
        });
      }

      // Search filter
      if (this.searchQuery) {
        const q = this.searchQuery.toLowerCase();
        filtered = filtered.filter(s =>
          s.symbol.toLowerCase().includes(q) ||
          s.name.toLowerCase().includes(q)
        );
      }

      // Score threshold
      if (this.minScore > 0) {
        filtered = filtered.filter(s => (s.total_score || 0) >= this.minScore);
      }

      // Sort
      return filtered.sort((a, b) => {
        let aVal = a[this.sortBy];
        let bVal = b[this.sortBy];

        // Handle nulls/undefined
        if (aVal == null) aVal = this.sortDesc ? -Infinity : Infinity;
        if (bVal == null) bVal = this.sortDesc ? -Infinity : Infinity;

        // String comparison for text fields
        if (typeof aVal === 'string' && typeof bVal === 'string') {
          return this.sortDesc
            ? bVal.localeCompare(aVal)
            : aVal.localeCompare(bVal);
        }

        // Numeric comparison
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

    // Rebalance Actions
    async previewRebalance() {
      this.loading.rebalance = true;
      this.rebalancePreview = null;
      try {
        const res = await fetch('/api/trades/rebalance/preview', { method: 'POST' });
        this.rebalancePreview = await res.json();
      } catch (e) {
        this.showMessage('Failed to preview rebalance', 'error');
      }
      this.loading.rebalance = false;
    },

    async executeRebalance() {
      this.loading.execute = true;
      try {
        const res = await fetch('/api/trades/rebalance/execute', { method: 'POST' });
        const data = await res.json();
        this.showMessage(`Executed ${data.successful_trades} trades`, 'success');
        this.showRebalanceModal = false;
        await this.fetchAll();
      } catch (e) {
        this.showMessage('Failed to execute rebalance', 'error');
      }
      this.loading.execute = false;
    },

    // Score Actions
    async refreshScores() {
      this.loading.scores = true;
      try {
        const res = await fetch('/api/stocks/refresh-all', { method: 'POST' });
        const data = await res.json();
        this.showMessage(data.message, 'success');
        await this.fetchStocks();
      } catch (e) {
        this.showMessage('Failed to refresh scores', 'error');
      }
      this.loading.scores = false;
    },

    async refreshSingleScore(symbol) {
      try {
        await fetch(`/api/stocks/${symbol}/refresh`, { method: 'POST' });
        await this.fetchStocks();
      } catch (e) {
        this.showMessage('Failed to refresh score', 'error');
      }
    },

    // Price Sync
    async syncPrices() {
      this.loading.sync = true;
      try {
        const res = await fetch('/api/status/sync/prices', { method: 'POST' });
        const data = await res.json();
        this.showMessage(data.message, 'success');
      } catch (e) {
        this.showMessage('Failed to sync prices', 'error');
      }
      this.loading.sync = false;
    },

    // Geographic Allocation Editing (weight-based: -1 to +1)
    startEditGeo() {
      // Initialize all active geographies with default 0 (neutral)
      this.geoTargets = {};
      this.activeGeographies.forEach(geo => {
        this.geoTargets[geo] = 0;
      });
      // Override with saved weights from allocation data
      if (this.allocation.geographic) {
        this.allocation.geographic.forEach(g => {
          // target_pct now stores weight (-1 to +1), default to 0 (neutral)
          this.geoTargets[g.name] = g.target_pct || 0;
        });
      }
      this.editingGeo = true;
    },

    cancelEditGeo() {
      this.editingGeo = false;
    },

    adjustGeoSlider(changed, newValue) {
      // Simple direct assignment - no proportional adjustment needed
      this.geoTargets[changed] = newValue;
    },

    async saveGeoTargets() {
      this.loading.geoSave = true;
      try {
        // Send weights directly (already -1 to +1)
        const targets = { ...this.geoTargets };
        const res = await fetch('/api/allocation/targets/geography', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ targets })
        });
        if (res.ok) {
          this.showMessage('Geographic weights updated', 'success');
          this.editingGeo = false;
          await this.fetchAllocation();
          await this.fetchStocks();  // Refresh priority scores
        } else {
          this.showMessage('Failed to save weights', 'error');
        }
      } catch (e) {
        this.showMessage('Failed to save weights', 'error');
      }
      this.loading.geoSave = false;
    },

    // Industry Allocation Editing (weight-based: -1 to +1)
    startEditIndustry() {
      // Initialize all active industries with default 0 (neutral)
      this.industryTargets = {};
      this.activeIndustries.forEach(ind => {
        this.industryTargets[ind] = 0;
      });
      // Override with saved weights from allocation data
      if (this.allocation.industry) {
        this.allocation.industry.forEach(ind => {
          // target_pct now stores weight (-1 to +1), default to 0 (neutral)
          this.industryTargets[ind.name] = ind.target_pct || 0;
        });
      }
      this.editingIndustry = true;
    },

    cancelEditIndustry() {
      this.editingIndustry = false;
    },

    adjustIndustrySlider(changed, newValue) {
      // Simple direct assignment - no proportional adjustment needed
      this.industryTargets[changed] = newValue;
    },

    async saveIndustryTargets() {
      this.loading.industrySave = true;
      try {
        // Send weights directly (already -1 to +1)
        const targets = { ...this.industryTargets };
        const res = await fetch('/api/allocation/targets/industry', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ targets })
        });
        if (res.ok) {
          this.showMessage('Industry weights updated', 'success');
          this.editingIndustry = false;
          await this.fetchAllocation();
          await this.fetchStocks();  // Refresh priority scores
        } else {
          this.showMessage('Failed to save weights', 'error');
        }
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
        const res = await fetch('/api/stocks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          this.showMessage('Stock added successfully', 'success');
          this.showAddStockModal = false;
          this.resetNewStock();
          await this.fetchStocks();
        } else {
          const data = await res.json();
          this.showMessage(data.detail || 'Failed to add stock', 'error');
        }
      } catch (e) {
        this.showMessage('Failed to add stock', 'error');
      }
      this.addingStock = false;
    },

    async removeStock(symbol) {
      if (!confirm(`Remove ${symbol} from the universe?`)) return;
      try {
        const res = await fetch(`/api/stocks/${symbol}`, { method: 'DELETE' });
        if (res.ok) {
          this.showMessage(`${symbol} removed`, 'success');
          await this.fetchStocks();
        } else {
          this.showMessage('Failed to remove stock', 'error');
        }
      } catch (e) {
        this.showMessage('Failed to remove stock', 'error');
      }
    },

    // Edit Stock
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
        const payload = {
          name: this.editingStock.name,
          yahoo_symbol: this.editingStock.yahoo_symbol || null,
          geography: this.editingStock.geography,
          industry: this.editingStock.industry || null,
          min_lot: parseInt(this.editingStock.min_lot) || 1
        };

        const res = await fetch(`/api/stocks/${this.editingStock.symbol}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          this.showMessage('Stock updated successfully', 'success');
          this.closeEditStock();
          await this.fetchStocks();
          await this.fetchAllocation();
        } else {
          const data = await res.json();
          this.showMessage(data.detail || 'Failed to update stock', 'error');
        }
      } catch (e) {
        this.showMessage('Failed to update stock', 'error');
      }
      this.loading.stockSave = false;
    },

    // Update stock multiplier (inline editing)
    async updateMultiplier(symbol, value) {
      const multiplier = parseFloat(value) || 1.0;
      // Clamp between 0.1 and 3.0
      const clamped = Math.max(0.1, Math.min(3.0, multiplier));

      try {
        const res = await fetch(`/api/stocks/${symbol}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ priority_multiplier: clamped })
        });

        if (res.ok) {
          // Update local state
          const stock = this.stocks.find(s => s.symbol === symbol);
          if (stock) {
            stock.priority_multiplier = clamped;
          }
          await this.fetchStocks();  // Refresh to get updated priority scores
        } else {
          this.showMessage('Failed to update multiplier', 'error');
        }
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
