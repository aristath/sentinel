/**
 * Sparkline Charts - Renders mini charts in stock table
 * Uses TradingView Lightweight Charts library
 */
const SparklineCharts = {
  charts: new Map(),  // symbol -> chart instance
  initialized: false,
  renderQueued: false,

  init() {
    // Wait for Alpine to be ready
    if (typeof Alpine === 'undefined') {
      document.addEventListener('alpine:init', () => this.setupWatcher());
    } else {
      this.setupWatcher();
    }
  },

  setupWatcher() {
    // Use Alpine effect to watch for data changes
    Alpine.effect(() => {
      const store = Alpine.store('app');
      if (!store) return;

      const sparklines = store.sparklines;
      const stocks = store.stocks;

      // Check if we have data to render
      if (sparklines && Object.keys(sparklines).length > 0 && stocks && stocks.length > 0) {
        // Queue render to avoid multiple renders in same tick
        if (!this.renderQueued) {
          this.renderQueued = true;
          requestAnimationFrame(() => {
            this.renderQueued = false;
            this.renderAll();
          });
        }
      }
    });
  },

  renderAll() {
    const containers = document.querySelectorAll('.sparkline-container');
    const store = Alpine.store('app');

    if (!store || !store.sparklines) return;

    containers.forEach(container => {
      const symbol = container.dataset.symbol;
      if (!symbol) return;

      const hasPosition = container.dataset.hasPosition === 'true';
      const data = store.sparklines[symbol];

      // Skip if no data or insufficient points
      if (!data || data.length < 2) {
        container.innerHTML = '<span class="text-gray-600 text-xs">-</span>';
        return;
      }

      // Skip if already rendered for this symbol
      if (this.charts.has(symbol) && container.querySelector('canvas')) {
        return;
      }

      this.renderChart(container, symbol, data, hasPosition);
    });
  },

  renderChart(container, symbol, data, hasPosition) {
    // Clean up existing chart
    if (this.charts.has(symbol)) {
      try {
        this.charts.get(symbol).remove();
      } catch (e) {
        // Chart may already be removed
      }
      this.charts.delete(symbol);
    }

    // Clear container
    container.innerHTML = '';

    try {
      const chart = LightweightCharts.createChart(container, {
        width: 80,
        height: 32,
        layout: {
          background: { type: 'solid', color: 'transparent' },
          textColor: 'transparent',
          attributionLogo: false,
        },
        grid: {
          vertLines: { visible: false },
          horzLines: { visible: false },
        },
        rightPriceScale: { visible: false },
        leftPriceScale: { visible: false },
        timeScale: { visible: false },
        handleScroll: false,
        handleScale: false,
        crosshair: { mode: 0 },
      });

      if (hasPosition) {
        // Baseline chart: green above starting price, red below
        // Use first data point as baseline
        const baselineValue = data[0].value;

        const series = chart.addBaselineSeries({
          baseValue: { type: 'price', price: baselineValue },
          topLineColor: '#10b981',     // green-500
          topFillColor1: 'rgba(16, 185, 129, 0.4)',
          topFillColor2: 'rgba(16, 185, 129, 0.1)',
          bottomLineColor: '#ef4444',   // red-500
          bottomFillColor1: 'rgba(239, 68, 68, 0.1)',
          bottomFillColor2: 'rgba(239, 68, 68, 0.4)',
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        series.setData(data);
      } else {
        // Area chart: blue
        const series = chart.addAreaSeries({
          lineColor: '#3b82f6',          // blue-500
          topColor: 'rgba(59, 130, 246, 0.4)',
          bottomColor: 'rgba(59, 130, 246, 0.1)',
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        series.setData(data);
      }

      chart.timeScale().fitContent();
      this.charts.set(symbol, chart);
    } catch (e) {
      console.error(`Failed to render sparkline for ${symbol}:`, e);
      container.innerHTML = '<span class="text-gray-600 text-xs">-</span>';
    }
  },

  // Clean up charts when component is destroyed
  cleanup() {
    this.charts.forEach((chart, symbol) => {
      try {
        chart.remove();
      } catch (e) {
        // Ignore
      }
    });
    this.charts.clear();
  }
};

// Initialize
SparklineCharts.init();
