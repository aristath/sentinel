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

    let html = `<div x-data="allocationRadarComponent('${type}')" x-init="init()">`;
    
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
          <radar-chart
            x-ref="geoRadarChart"
            x-effect="if (geoLabels.length && geoTargetData.length && geoCurrentData.length) updateGeoChart()">
          </radar-chart>
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
          <radar-chart
            x-ref="industryRadarChart"
            x-effect="if (industryLabels.length && industryTargetData.length && industryCurrentData.length) updateIndustryChart()">
          </radar-chart>
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
function allocationRadarComponent(chartType) {
  return {
    chartType: chartType,
    updateTimer: null,
    previousGeoData: null,
    previousIndustryData: null,

    // Computed properties for geographic data
    get geoLabels() {
      return Array.from(this.$store.app.activeGeographies || []);
    },

    get geoCurrentData() {
      const activeGeos = this.geoLabels;
      const allocation = this.$store.app.allocation?.geographic || [];
      
      if (activeGeos.length === 0 || allocation.length === 0) {
        return [];
      }

      return activeGeos.map(geo => {
        const item = allocation.find(a => a.name === geo);
        return item ? item.current_pct * 100 : 0;
      });
    },

    get geoTargetData() {
      const activeGeos = this.geoLabels;
      const allocation = this.$store.app.allocation?.geographic || [];
      
      if (activeGeos.length === 0 || allocation.length === 0) {
        return [];
      }

      const weights = {};
      allocation.forEach(a => { weights[a.name] = a.target_pct || 0; });
      const targetPcts = this.getTargetPcts(weights, activeGeos);
      return activeGeos.map(geo => (targetPcts[geo] || 0) * 100);
    },

    get geoMaxValue() {
      const allValues = [...this.geoTargetData, ...this.geoCurrentData];
      return allValues.length > 0 ? Math.max(...allValues) : 100;
    },

    // Computed properties for industry data
    get industryLabels() {
      return Array.from(this.$store.app.activeIndustries || []);
    },

    get industryCurrentData() {
      const activeIndustries = this.industryLabels;
      const allocation = this.$store.app.allocation?.industry || [];
      
      if (activeIndustries.length === 0 || allocation.length === 0) {
        return [];
      }

      return activeIndustries.map(ind => {
        const item = allocation.find(a => a.name === ind);
        return item ? item.current_pct * 100 : 0;
      });
    },

    get industryTargetData() {
      const activeIndustries = this.industryLabels;
      const allocation = this.$store.app.allocation?.industry || [];
      
      if (activeIndustries.length === 0 || allocation.length === 0) {
        return [];
      }

      const weights = {};
      allocation.forEach(a => { weights[a.name] = a.target_pct || 0; });
      const targetPcts = this.getTargetPcts(weights, activeIndustries);
      return activeIndustries.map(ind => (targetPcts[ind] || 0) * 100);
    },

    get industryMaxValue() {
      const allValues = [...this.industryTargetData, ...this.industryCurrentData];
      return allValues.length > 0 ? Math.max(...allValues) : 100;
    },

    init() {
      // Watch for data changes and trigger updates
      this.$watch('$store.app.allocation', () => {
        this.$nextTick(() => this.updateCharts());
      }, { deep: false });

      this.$watch('$store.app.activeGeographies', () => {
        this.$nextTick(() => this.updateCharts());
      }, { deep: false });

      this.$watch('$store.app.activeIndustries', () => {
        this.$nextTick(() => this.updateCharts());
      }, { deep: false });
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

    hasDataChanged(newData, previousData) {
      if (!previousData) return true;
      if (newData.labels.length !== previousData.labels.length) return true;
      if (JSON.stringify(newData.labels) !== JSON.stringify(previousData.labels)) return true;
      if (JSON.stringify(newData.currentData) !== JSON.stringify(previousData.currentData)) return true;
      if (JSON.stringify(newData.targetData) !== JSON.stringify(previousData.targetData)) return true;
      return false;
    },

    updateGeoChart() {
      // Update geographic radar chart when data changes
      if (this.chartType !== 'geographic' && this.chartType !== 'both') {
        return;
      }
      
      this.$nextTick(() => {
        const chart = this.$refs.geoRadarChart;
        if (chart && typeof chart.updateData === 'function') {
          const labels = this.geoLabels;
          const targetData = this.geoTargetData;
          const currentData = this.geoCurrentData;
          const maxValue = this.geoMaxValue;
          
          if (labels.length > 0 && targetData.length > 0 && currentData.length > 0) {
            chart.updateData(labels, targetData, currentData, maxValue);
          }
        }
      });
    },

    updateIndustryChart() {
      // Update industry radar chart when data changes
      if (this.chartType !== 'industry' && this.chartType !== 'both') {
        return;
      }
      
      this.$nextTick(() => {
        const chart = this.$refs.industryRadarChart;
        if (chart && typeof chart.updateData === 'function') {
          const labels = this.industryLabels;
          const targetData = this.industryTargetData;
          const currentData = this.industryCurrentData;
          const maxValue = this.industryMaxValue;
          
          if (labels.length > 0 && targetData.length > 0 && currentData.length > 0) {
            chart.updateData(labels, targetData, currentData, maxValue);
          }
        }
      });
    },

    updateCharts() {
      // Debounce updates
      if (this.updateTimer) {
        clearTimeout(this.updateTimer);
      }

      this.updateTimer = setTimeout(() => {
        this.updateGeoChart();
        this.updateIndustryChart();
        this.updateTimer = null;
      }, 150);
    }
  };
}

customElements.define('allocation-radar', AllocationRadar);
