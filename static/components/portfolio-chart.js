/**
 * Portfolio Chart Component
 * Displays portfolio value over time using Lightweight Charts
 */

/**
 * Alpine.js component for portfolio chart
 */
function portfolioChartComponent() {
  return {
    selectedRange: 'all',
    loading: false,
    error: null,
    chartData: null,
    chart: null,
    lineSeries: null,

    async init() {
      await this.loadChart();
    },

    async loadChart() {
      this.loading = true;
      this.error = null;

      try {
        const data = await API.fetchPortfolioChart(this.selectedRange);
        
        if (!data || data.length === 0) {
          this.chartData = [];
          if (this.chart) {
            this.chart.remove();
            this.chart = null;
            this.lineSeries = null;
          }
          this.loading = false;
          return;
        }

        this.chartData = data;

        // Initialize or update chart
        await this.$nextTick();
        this.renderChart();
      } catch (err) {
        console.error('Failed to load portfolio chart:', err);
        this.error = 'Failed to load chart data';
        if (this.chart) {
          this.chart.remove();
          this.chart = null;
          this.lineSeries = null;
        }
      } finally {
        this.loading = false;
      }
    },

    renderChart() {
      const container = document.getElementById('portfolio-chart-container');
      if (!container) return;

      // Remove existing chart
      if (this.chart) {
        this.chart.remove();
      }

      // Create chart
      this.chart = LightweightCharts.createChart(container, {
        layout: {
          background: { color: '#1f2937' }, // gray-800
          textColor: '#9ca3af', // gray-400
        },
        grid: {
          vertLines: { color: '#374151' }, // gray-700
          horzLines: { color: '#374151' },
        },
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
        },
        width: container.clientWidth,
        height: 256,
      });

      // Add line series
      this.lineSeries = this.chart.addLineSeries({
        color: '#3b82f6', // blue-500
        lineWidth: 2,
        priceFormat: {
          type: 'price',
          precision: 2,
          minMove: 0.01,
        },
      });

      // Set data
      this.lineSeries.setData(this.chartData);

      // Fit content
      this.chart.timeScale().fitContent();

      // Handle resize
      const resizeObserver = new ResizeObserver(entries => {
        if (entries.length > 0) {
          const { width, height } = entries[0].contentRect;
          this.chart.applyOptions({ width, height: Math.max(height, 200) });
        }
      });
      resizeObserver.observe(container);
    },
  };
}

class PortfolioChart extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3" x-data="portfolioChartComponent()">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xs text-gray-400 uppercase tracking-wide">Portfolio Value</h2>
          <select x-model="selectedRange" 
                  @change="loadChart()"
                  class="px-2 py-1 bg-gray-900 border border-gray-600 rounded text-xs text-gray-100 focus:border-blue-500 focus:outline-none">
            <option value="1M">1M</option>
            <option value="3M">3M</option>
            <option value="6M">6M</option>
            <option value="1Y">1Y</option>
            <option value="all">All</option>
          </select>
        </div>

        <!-- Loading state -->
        <div x-show="loading" class="flex items-center justify-center h-64 text-gray-500 text-sm">
          <span class="animate-spin">&#9696;</span>
          <span class="ml-2">Loading chart data...</span>
        </div>

        <!-- Error state -->
        <div x-show="error && !loading" class="text-red-400 text-sm p-4" x-text="error"></div>

        <!-- Chart container -->
        <div x-show="!loading && !error" id="portfolio-chart-container" class="h-64"></div>

        <!-- Empty state -->
        <div x-show="!loading && !error && (!chartData || chartData.length === 0)" 
             class="flex items-center justify-center h-64 text-gray-500 text-sm">
          No data available for the selected range
        </div>
      </div>
    `;
  }
}

customElements.define('portfolio-chart', PortfolioChart);
