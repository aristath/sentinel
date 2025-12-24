/**
 * Allocation Radar Chart Component
 * Displays geographic and industry allocations as radar charts
 * Shows target vs current allocation for easy deviation visualization
 * 
 * Attributes:
 * - type: "geographic" | "industry" | "both" (default: "both")
 */
class AllocationRadar extends HTMLElement {
  connectedCallback() {
    const type = this.getAttribute('type') || 'both';
    const uniqueId = Math.random().toString(36).substring(2, 9);
    const geoCanvasId = `geo-radar-chart-${uniqueId}`;
    const industryCanvasId = `industry-radar-chart-${uniqueId}`;
    
    // Store IDs for use in Alpine component
    this.dataset.geoCanvasId = geoCanvasId;
    this.dataset.industryCanvasId = industryCanvasId;
    this.dataset.chartType = type;

    let html = `<div x-data="allocationRadarComponent('${geoCanvasId}', '${industryCanvasId}', '${type}')" x-init="initCharts()">`;
    
    // Geographic Radar
    if (type === 'geographic' || type === 'both') {
      html += `
        <!-- Geographic Radar -->
        <div ${type === 'both' ? 'class="mb-4"' : ''}>
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-xs text-gray-500 font-medium">Geographic</h3>
            <button @click="$store.app.startEditGeo()"
                    class="text-xs text-blue-400 hover:text-blue-300 transition-colors">
              Edit Weights
            </button>
          </div>
          <div class="relative w-full" style="aspect-ratio: 1;">
            <canvas id="${geoCanvasId}"></canvas>
          </div>
        </div>`;
    }

    // Industry Radar
    if (type === 'industry' || type === 'both') {
      html += `
        <!-- Industry Radar -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-xs text-gray-500 font-medium">Industry</h3>
            <button @click="$store.app.startEditIndustry()"
                    class="text-xs text-blue-400 hover:text-blue-300 transition-colors">
              Edit Weights
            </button>
          </div>
          <div class="relative w-full" style="aspect-ratio: 1;">
            <canvas id="${industryCanvasId}"></canvas>
          </div>
        </div>`;
    }

    html += `
        <!-- Edit Mode Overlays -->
        <div x-show="$store.app.editingGeo" x-transition
             class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div class="bg-gray-800 border border-gray-700 rounded-lg p-4 w-full max-w-md" @click.stop>
            <h3 class="text-sm font-medium text-gray-200 mb-3">Edit Geographic Weights</h3>
            <geo-chart></geo-chart>
          </div>
        </div>

        <div x-show="$store.app.editingIndustry" x-transition
             class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div class="bg-gray-800 border border-gray-700 rounded-lg p-4 w-full max-w-md" @click.stop>
            <h3 class="text-sm font-medium text-gray-200 mb-3">Edit Industry Weights</h3>
            <industry-chart></industry-chart>
          </div>
        </div>
      </div>`;
    
    this.innerHTML = html;
  }
}

/**
 * Alpine.js component for radar charts
 */
function allocationRadarComponent(geoCanvasId, industryCanvasId, chartType) {
  return {
    geoChart: null,
    industryChart: null,
    chartsInitialized: false,
    geoCanvasId: geoCanvasId,
    industryCanvasId: industryCanvasId,
    chartType: chartType,

    initCharts() {
      // Check if Chart.js is available
      if (typeof Chart === 'undefined') {
        console.error('Chart.js is not loaded. Please ensure chart.umd.min.js is loaded before this component.');
        return;
      }

      // Wait for Alpine and data to be ready
      this.$nextTick(() => {
        // Try to initialize charts if data is available
        this.tryInitializeCharts();

        // Watch for allocation changes
        this.$watch('$store.app.allocation', () => {
          this.updateCharts();
        });

        // Watch for active geographies to become available
        this.$watch('$store.app.activeGeographies', () => {
          if (!this.chartsInitialized) {
            this.tryInitializeCharts();
          } else {
            this.updateCharts();
          }
        });

        // Watch for active industries to become available
        this.$watch('$store.app.activeIndustries', () => {
          if (!this.chartsInitialized) {
            this.tryInitializeCharts();
          } else {
            this.updateCharts();
          }
        });
      });
    },

    tryInitializeCharts() {
      // Check if we have the necessary data
      const hasGeoData = (this.$store.app.activeGeographies || []).length > 0 &&
                         (this.$store.app.allocation?.geographic || []).length > 0;
      const hasIndustryData = (this.$store.app.activeIndustries || []).length > 0 &&
                             (this.$store.app.allocation?.industry || []).length > 0;

      if (hasGeoData && (this.chartType === 'geographic' || this.chartType === 'both')) {
        this.createGeoChart();
      }

      if (hasIndustryData && (this.chartType === 'industry' || this.chartType === 'both')) {
        this.createIndustryChart();
      }

      // Mark as initialized if at least one chart was created
      if ((hasGeoData && (this.chartType === 'geographic' || this.chartType === 'both')) ||
          (hasIndustryData && (this.chartType === 'industry' || this.chartType === 'both'))) {
        this.chartsInitialized = true;
      }
    },

    getTargetPcts(weights, activeItems) {
      // Convert weights (-1 to +1) to percentages
      const shifted = {};
      let total = 0;
      for (const name of activeItems) {
        const weight = weights[name] || 0;
        shifted[name] = weight + 1; // -1→0, 0→1, +1→2
        total += shifted[name];
      }
      const targets = {};
      for (const [name, val] of Object.entries(shifted)) {
        targets[name] = total > 0 ? val / total : 0;
      }
      return targets;
    },

    createGeoChart() {
      // Check Chart.js availability
      if (typeof Chart === 'undefined') {
        console.error('Chart.js is not loaded');
        return;
      }

      const canvas = document.getElementById(this.geoCanvasId);
      if (!canvas) {
        console.warn('Geo radar chart canvas not found');
        return;
      }

      // Destroy existing chart if it exists
      if (this.geoChart) {
        this.geoChart.destroy();
        this.geoChart = null;
      }

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        console.error('Could not get 2D context from canvas');
        return;
      }

      const activeGeos = this.$store.app.activeGeographies || [];
      const allocation = this.$store.app.allocation?.geographic || [];

      if (activeGeos.length === 0) {
        console.warn('No active geographies available for chart');
        return;
      }

      if (!Array.isArray(allocation) || allocation.length === 0) {
        console.warn('No geographic allocation data available');
        return;
      }

      // Get current allocations
      const currentData = activeGeos.map(geo => {
        const item = allocation.find(a => a.name === geo);
        return item ? item.current_pct * 100 : 0;
      });

      // Get target allocations
      const weights = {};
      allocation.forEach(a => { weights[a.name] = a.target_pct || 0; });
      const targetPcts = this.getTargetPcts(weights, activeGeos);
      const targetData = activeGeos.map(geo => (targetPcts[geo] || 0) * 100);

      // Calculate max value from both datasets for auto-scaling
      const allValues = [...targetData, ...currentData];
      const maxValue = allValues.length > 0 ? Math.max(...allValues) : 100;

      this.geoChart = new Chart(ctx, {
        type: 'radar',
        data: {
          labels: activeGeos,
          datasets: [
            {
              label: 'Target',
              data: targetData,
              borderColor: 'rgba(59, 130, 246, 0.8)',
              borderWidth: 2,
              borderDash: [5, 5],
              backgroundColor: 'transparent',
              pointBackgroundColor: 'rgba(59, 130, 246, 0.8)',
              pointRadius: 3,
            },
            {
              label: 'Current',
              data: currentData,
              borderColor: 'rgba(34, 197, 94, 0.8)',
              borderWidth: 2,
              backgroundColor: 'rgba(34, 197, 94, 0.2)',
              pointBackgroundColor: 'rgba(34, 197, 94, 0.8)',
              pointRadius: 3,
            }
          ]
        },
        options: this.getChartOptions(maxValue)
      });
    },

    createIndustryChart() {
      // Check Chart.js availability
      if (typeof Chart === 'undefined') {
        console.error('Chart.js is not loaded');
        return;
      }

      const canvas = document.getElementById(this.industryCanvasId);
      if (!canvas) {
        console.warn('Industry radar chart canvas not found');
        return;
      }

      // Destroy existing chart if it exists
      if (this.industryChart) {
        this.industryChart.destroy();
        this.industryChart = null;
      }

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        console.error('Could not get 2D context from canvas');
        return;
      }

      const activeIndustries = this.$store.app.activeIndustries || [];
      const allocation = this.$store.app.allocation?.industry || [];

      if (activeIndustries.length === 0) {
        console.warn('No active industries available for chart');
        return;
      }

      if (!Array.isArray(allocation) || allocation.length === 0) {
        console.warn('No industry allocation data available');
        return;
      }

      // Get current allocations
      const currentData = activeIndustries.map(ind => {
        const item = allocation.find(a => a.name === ind);
        return item ? item.current_pct * 100 : 0;
      });

      // Get target allocations
      const weights = {};
      allocation.forEach(a => { weights[a.name] = a.target_pct || 0; });
      const targetPcts = this.getTargetPcts(weights, activeIndustries);
      const targetData = activeIndustries.map(ind => (targetPcts[ind] || 0) * 100);

      // Calculate max value from both datasets for auto-scaling
      const allValues = [...targetData, ...currentData];
      const maxValue = allValues.length > 0 ? Math.max(...allValues) : 100;

      this.industryChart = new Chart(ctx, {
        type: 'radar',
        data: {
          labels: activeIndustries,
          datasets: [
            {
              label: 'Target',
              data: targetData,
              borderColor: 'rgba(59, 130, 246, 0.8)',
              borderWidth: 2,
              borderDash: [5, 5],
              backgroundColor: 'transparent',
              pointBackgroundColor: 'rgba(59, 130, 246, 0.8)',
              pointRadius: 3,
            },
            {
              label: 'Current',
              data: currentData,
              borderColor: 'rgba(34, 197, 94, 0.8)',
              borderWidth: 2,
              backgroundColor: 'rgba(34, 197, 94, 0.2)',
              pointBackgroundColor: 'rgba(34, 197, 94, 0.8)',
              pointRadius: 3,
            }
          ]
        },
        options: this.getChartOptions(maxValue)
      });
    },

    getChartOptions(suggestedMax = 100) {
      // Add 25% padding above the max value for better visual spacing
      const paddedMax = suggestedMax > 0 ? Math.ceil(suggestedMax * 1.25) : 100;
      
      return {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 1,
        plugins: {
          legend: {
            display: true,
            position: 'bottom',
            labels: {
              color: '#9CA3AF',
              font: { size: 10 },
              boxWidth: 12,
              padding: 8
            }
          }
        },
        scales: {
          r: {
            beginAtZero: true,
            suggestedMax: paddedMax,
            ticks: {
              stepSize: 25,
              color: '#6B7280',
              font: { size: 9 },
              backdropColor: 'transparent'
            },
            grid: {
              color: '#374151'
            },
            angleLines: {
              color: '#374151'
            },
            pointLabels: {
              color: '#D1D5DB',
              font: { size: 10 }
            }
          }
        }
      };
    },

    updateCharts() {
      // Update or create geo chart
      if (this.chartType === 'geographic' || this.chartType === 'both') {
        const activeGeos = this.$store.app.activeGeographies || [];
        const geoAllocation = this.$store.app.allocation?.geographic || [];

        if (activeGeos.length > 0 && Array.isArray(geoAllocation) && geoAllocation.length > 0) {
        if (this.geoChart) {
          // Update existing chart
          const currentData = activeGeos.map(geo => {
            const item = geoAllocation.find(a => a.name === geo);
            return item ? item.current_pct * 100 : 0;
          });

          const weights = {};
          geoAllocation.forEach(a => { weights[a.name] = a.target_pct || 0; });
          const targetPcts = this.getTargetPcts(weights, activeGeos);
          const targetData = activeGeos.map(geo => (targetPcts[geo] || 0) * 100);

          // Calculate max value from both datasets for auto-scaling
          const allValues = [...targetData, ...currentData];
          const maxValue = allValues.length > 0 ? Math.max(...allValues) : 100;
          const paddedMax = maxValue > 0 ? Math.ceil(maxValue * 1.25) : 100;

          this.geoChart.data.labels = activeGeos;
          this.geoChart.data.datasets[0].data = targetData;
          this.geoChart.data.datasets[1].data = currentData;
          this.geoChart.options.scales.r.suggestedMax = paddedMax;
          this.geoChart.update('none');
        } else {
          // Chart doesn't exist yet, create it
          this.createGeoChart();
        }
      }
      }

      // Update or create industry chart
      if (this.chartType === 'industry' || this.chartType === 'both') {
        const activeIndustries = this.$store.app.activeIndustries || [];
        const industryAllocation = this.$store.app.allocation?.industry || [];

        if (activeIndustries.length > 0 && Array.isArray(industryAllocation) && industryAllocation.length > 0) {
        if (this.industryChart) {
          // Update existing chart
          const currentData = activeIndustries.map(ind => {
            const item = industryAllocation.find(a => a.name === ind);
            return item ? item.current_pct * 100 : 0;
          });

          const weights = {};
          industryAllocation.forEach(a => { weights[a.name] = a.target_pct || 0; });
          const targetPcts = this.getTargetPcts(weights, activeIndustries);
          const targetData = activeIndustries.map(ind => (targetPcts[ind] || 0) * 100);

          // Calculate max value from both datasets for auto-scaling
          const allValues = [...targetData, ...currentData];
          const maxValue = allValues.length > 0 ? Math.max(...allValues) : 100;
          const paddedMax = maxValue > 0 ? Math.ceil(maxValue * 1.25) : 100;

          this.industryChart.data.labels = activeIndustries;
          this.industryChart.data.datasets[0].data = targetData;
          this.industryChart.data.datasets[1].data = currentData;
          this.industryChart.options.scales.r.suggestedMax = paddedMax;
          this.industryChart.update('none');
        } else {
          // Chart doesn't exist yet, create it
          this.createIndustryChart();
        }
      }
      }
    }
  };
}

customElements.define('allocation-radar', AllocationRadar);
