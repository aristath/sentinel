/**
 * Geographic Allocation Chart Component
 * Displays SVG doughnut chart and allows editing geographic weights
 * Weight scale: -1 (avoid) to +1 (prioritize), 0 = neutral
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

        <div class="flex justify-center mb-3">
          <svg viewBox="0 0 100 100" class="w-32 h-32">
            <!-- Background circle -->
            <circle cx="50" cy="50" r="40" fill="none" stroke="#374151" stroke-width="16"/>

            <!-- Dynamic segments based on active geographies -->
            <template x-for="(geo, index) in (geographicAllocations || [])" :key="geo.name">
              <circle cx="50" cy="50" r="40" fill="none"
                      :stroke="getGeoColor(geo.name)"
                      stroke-width="16"
                      :stroke-dasharray="circumference"
                      :stroke-dashoffset="getOffset(index)"
                      :transform="'rotate(' + getRotation(index) + ' 50 50)'"
                      class="doughnut-chart__segment"/>
            </template>
          </svg>
        </div>

        <!-- View Mode - Only show active geographies (with stocks) -->
        <div x-show="!$store.app.editingGeo" class="space-y-1.5">
          <template x-for="geo in (geographicAllocations || []).filter(g => $store.app.activeGeographies && $store.app.activeGeographies.includes(g.name))" :key="geo.name">
            <div class="flex items-center justify-between text-sm">
              <span class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full" :style="'background-color: ' + getGeoColor(geo.name)"></span>
                <span class="text-gray-300" x-text="geo.name"></span>
              </span>
              <span class="flex items-center gap-2">
                <span class="font-mono text-gray-400" x-text="(geo.current_pct * 100).toFixed(1) + '%'"></span>
                <span class="text-xs px-1.5 py-0.5 rounded font-mono"
                      :class="getWeightBadgeClass(geo.target_pct)"
                      x-text="formatWeight(geo.target_pct)"></span>
              </span>
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
 * Alpine.js component for SVG doughnut chart
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
    circumference: 2 * Math.PI * 40,

    get geographicAllocations() {
      const allocation = this.$store.app.allocation;
      if (!allocation || !allocation.geographic) return [];
      return Array.isArray(allocation.geographic) ? allocation.geographic : [];
    },

    getGeoColor(name) {
      return geoColors[name] || '#6B7280';
    },

    getOffset(index) {
      const geo = this.geographicAllocations;
      if (!geo || !Array.isArray(geo) || !geo[index]) return this.circumference;
      return this.circumference * (1 - (geo[index].current_pct || 0));
    },

    getRotation(index) {
      const geo = this.geographicAllocations;
      if (!geo || !Array.isArray(geo)) return -90;
      let cumulative = 0;
      for (let i = 0; i < index; i++) {
        cumulative += (geo[i]?.current_pct || 0);
      }
      return -90 + (cumulative * 360);
    },

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
