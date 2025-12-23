/**
 * Geographic Allocation Component
 * Displays geographic weights and allows editing
 * Weight scale: -1 (avoid) to +1 (prioritize), 0 = neutral
 * View mode shows deviation from calculated target allocation
 */
class GeoChart extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3" x-data="geoChartComponent()">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xs text-gray-400 uppercase tracking-wide">Geographic Weights</h2>
          <button x-show="!$store.app.editingGeo"
                  @click="$store.app.startEditGeo()"
                  class="text-xs text-blue-400 hover:text-blue-300 transition-colors">
            Edit Weights
          </button>
        </div>

        <!-- View Mode - Show deviation from target allocation -->
        <div x-show="!$store.app.editingGeo" class="space-y-2">
          <template x-for="geo in (geographicAllocations || []).filter(g => $store.app.activeGeographies && $store.app.activeGeographies.includes(g.name))" :key="geo.name">
            <div>
              <div class="flex items-center justify-between text-sm mb-1">
                <span class="flex items-center gap-2">
                  <span class="w-2.5 h-2.5 rounded-full" :style="'background-color: ' + getGeoColor(geo.name)"></span>
                  <span class="text-gray-300" x-text="geo.name"></span>
                </span>
                <span class="flex items-center gap-2">
                  <span class="font-mono text-gray-400" x-text="(geo.current_pct * 100).toFixed(1) + '%'"></span>
                  <span class="text-xs px-1.5 py-0.5 rounded font-mono"
                        :class="getDeviationBadgeClass(getDeviation(geo.name, geo.current_pct))"
                        x-text="formatDeviation(getDeviation(geo.name, geo.current_pct))"></span>
                </span>
              </div>
              <!-- Deviation bar -->
              <div class="h-1.5 bg-gray-700 rounded-full relative overflow-hidden">
                <div class="absolute top-0 bottom-0 left-1/2 w-px bg-gray-500 z-10"></div>
                <div class="absolute top-0 bottom-0 rounded-full transition-all"
                     :class="getDeviationBarColor(geo.name, getDeviation(geo.name, geo.current_pct))"
                     :style="getDeviationBarStyle(getDeviation(geo.name, geo.current_pct))">
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- Edit Mode - Weight sliders for active geographies -->
        <div x-show="$store.app.editingGeo" x-transition class="space-y-3">
          <!-- Weight Scale Legend -->
          <div class="flex justify-between text-xs text-gray-500">
            <span class="text-red-400">-1 Avoid</span>
            <span class="text-gray-400">0 Neutral</span>
            <span class="text-green-400">+1 Prioritize</span>
          </div>

          <!-- Dynamic Geo Sliders - only for active geographies -->
          <template x-for="name in (($store.app.activeGeographies || []).sort())" :key="name">
            <div class="space-y-1">
              <div class="flex items-center justify-between text-sm">
                <span class="flex items-center gap-2">
                  <span class="w-2.5 h-2.5 rounded-full" :style="'background-color: ' + getGeoColor(name)"></span>
                  <span class="text-gray-300" x-text="name"></span>
                </span>
                <span class="text-xs px-1.5 py-0.5 rounded font-mono"
                      :class="getWeightBadgeClass($store.app.geoTargets[name] || 0)"
                      x-text="formatWeight($store.app.geoTargets[name] || 0)"></span>
              </div>
              <input type="range" min="-1" max="1" step="0.01"
                     :value="$store.app.geoTargets[name] || 0"
                     @input="$store.app.adjustGeoSlider(name, parseFloat($event.target.value))"
                     class="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer">
            </div>
          </template>

          <!-- Buttons -->
          <div class="flex gap-2 pt-2">
            <button @click="$store.app.cancelEditGeo()"
                    class="flex-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded transition-colors">
              Cancel
            </button>
            <button @click="$store.app.saveGeoTargets()"
                    :disabled="$store.app.loading.geoSave"
                    class="flex-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded transition-colors disabled:opacity-50">
              <span x-show="$store.app.loading.geoSave" class="inline-block animate-spin mr-1">&#9696;</span>
              Save
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

/**
 * Alpine.js component for geographic allocation
 */
function geoChartComponent() {
  const geoColors = {
    'EU': '#3B82F6',
    'ASIA': '#EF4444',
    'US': '#22C55E',
    'GREECE': '#8B5CF6',
    'UK': '#F59E0B',
    'LATAM': '#EC4899',
    'AFRICA': '#14B8A6'
  };

  return {
    get geographicAllocations() {
      const allocation = this.$store.app.allocation;
      if (!allocation || !allocation.geographic) return [];
      return Array.isArray(allocation.geographic) ? allocation.geographic : [];
    },

    getGeoColor(name) {
      return geoColors[name] || '#6B7280';
    },

    // Convert weights to target percentages
    getTargetPcts() {
      const weights = this.$store.app.geoTargets || {};
      const activeGeos = this.$store.app.activeGeographies || [];

      // Only consider active geographies
      const shifted = {};
      let total = 0;
      for (const name of activeGeos) {
        const weight = weights[name] || 0;
        shifted[name] = weight + 1; // -1→0, 0→1, +1→2
        total += shifted[name];
      }

      // Normalize to percentages
      const targets = {};
      for (const [name, val] of Object.entries(shifted)) {
        targets[name] = total > 0 ? val / total : 0;
      }
      return targets;
    },

    // Calculate deviation: current% - target%
    getDeviation(name, currentPct) {
      const targets = this.getTargetPcts();
      const targetPct = targets[name] || 0;
      return currentPct - targetPct;
    },

    // Format deviation as percentage string
    formatDeviation(deviation) {
      const pct = (deviation * 100).toFixed(1);
      return (deviation >= 0 ? '+' : '') + pct + '%';
    },

    // Badge class for deviation value
    getDeviationBadgeClass(deviation) {
      if (Math.abs(deviation) < 0.02) return 'bg-gray-700 text-gray-400'; // Within 2%
      return deviation > 0 ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400';
    },

    // Bar color based on whether deviation aligns with weight intent
    getDeviationBarColor(name, deviation) {
      const weight = this.$store.app.geoTargets?.[name] || 0;
      // Good: deviation direction matches weight intent
      // Overweight + positive weight = good (we wanted more, we have more)
      // Underweight + negative weight = good (we wanted less, we have less)
      const isAligned = (deviation > 0 && weight > 0) || (deviation < 0 && weight < 0) || Math.abs(deviation) < 0.02;
      return isAligned ? 'bg-green-500' : 'bg-red-500';
    },

    // Bar style for deviation visualization
    getDeviationBarStyle(deviation) {
      // Scale: ±20% deviation = full half bar
      const maxDev = 0.20;
      const pct = Math.min(Math.abs(deviation), maxDev) / maxDev * 50;

      if (deviation >= 0) {
        return `width: ${pct}%; left: 50%;`;
      } else {
        return `width: ${pct}%; right: 50%;`;
      }
    },

    // Edit mode helpers (unchanged)
    formatWeight(weight) {
      if (weight === 0 || weight === undefined) return '0';
      return (weight > 0 ? '+' : '') + weight.toFixed(2);
    },

    getWeightBadgeClass(weight) {
      if (weight > 0.1) return 'bg-green-900/50 text-green-400';
      if (weight < -0.1) return 'bg-red-900/50 text-red-400';
      return 'bg-gray-700 text-gray-400';
    }
  };
}

customElements.define('geo-chart', GeoChart);
