/**
 * Security Chart Modal Component
 * Displays security price history in a modal using Lightweight Charts
 */

/**
 * Alpine.js component for security chart
 */
function securityChartComponent() {
  return {
    selectedRange: '10Y',
    selectedSource: 'yahoo',
    loading: false,
    error: null,
    chartData: null,
    chart: null,
    lineSeries: null,
    symbol: null,
    isin: null,
    securityName: null,

    init() {
      // Watch for symbol changes from store (for display)
      this.$watch('$store.app.selectedStockSymbol', (symbol) => {
        if (symbol) {
          this.symbol = symbol;
          // Find security name from store
          const securities = this.$store.app.securities || [];
          const security = securities.find(s => s.symbol === symbol);
          this.securityName = security ? security.name : null;
        }
      });

      // Watch for ISIN changes from store (for API calls)
      this.$watch('$store.app.selectedSecurityIsin', (isin) => {
        if (isin) {
          this.isin = isin;
          this.loadChart();
        }
      });

      // Load chart when modal opens
      this.$watch('$store.app.showSecurityChart', (show) => {
        if (show && this.isin) {
          this.loadChart();
        } else if (!show) {
          this.closeChart();
        }
      });
    },

    async loadChart() {
      if (!this.isin) return;

      this.loading = true;
      this.error = null;

      try {
        const data = await API.fetchSecurityChart(this.isin, this.selectedRange, this.selectedSource);

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
        console.error('Failed to load security chart:', err);
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
      const container = document.getElementById('security-chart-container');
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
          attributionLogo: false,
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
        height: 384,
      });

      // Add line series
      this.lineSeries = this.chart.addLineSeries({
        color: '#10b981', // green-500
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
          this.chart.applyOptions({ width, height: Math.max(height, 300) });
        }
      });
      resizeObserver.observe(container);
    },

    closeChart() {
      if (this.chart) {
        this.chart.remove();
        this.chart = null;
        this.lineSeries = null;
      }
      this.chartData = null;
      this.error = null;
      this.symbol = null;
      this.isin = null;
      this.securityName = null;
    },
  };
}

class SecurityChartModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data="securityChartComponent()"
           x-show="$store.app.showSecurityChart"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
           x-transition>
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col" @click.stop>
          <div class="flex items-center justify-between p-4 border-b border-gray-700">
            <div>
              <h2 class="text-lg font-semibold text-gray-100" x-text="symbol || 'Security Chart'"></h2>
              <p class="text-xs text-gray-300" x-show="securityName" x-text="securityName"></p>
            </div>
            <button @click="$store.app.showSecurityChart = false; closeChart()"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <div class="p-4 flex-1 overflow-auto">
            <!-- Controls -->
            <div class="flex items-center justify-between mb-4">
              <div class="flex gap-2">
                <select x-model="selectedRange"
                        @change="loadChart()"
                        class="px-2 py-1 bg-gray-900 border border-gray-600 rounded text-xs text-gray-100 focus:border-blue-500 focus:outline-none">
                  <option value="1M">1M</option>
                  <option value="3M">3M</option>
                  <option value="6M">6M</option>
                  <option value="1Y">1Y</option>
                  <option value="5Y">5Y</option>
                  <option value="10Y">10Y</option>
                </select>
              </div>
            </div>

            <!-- Loading state -->
            <div x-show="loading" class="flex items-center justify-center h-96 text-gray-300 text-sm">
              <span class="animate-spin">&#9696;</span>
              <span class="ml-2">Loading chart data...</span>
            </div>

            <!-- Error state -->
            <div x-show="error && !loading" class="text-red-400 text-sm p-4" x-text="error"></div>

            <!-- Chart container -->
            <div x-show="!loading && !error" id="security-chart-container" class="h-96"></div>

            <!-- Empty state -->
            <div x-show="!loading && !error && (!chartData || chartData.length === 0)"
                 class="flex items-center justify-center h-96 text-gray-300 text-sm">
              No data available for this security
            </div>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('security-chart-modal', SecurityChartModal);
