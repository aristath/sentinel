/**
 * Industry Allocation Component
 * Displays industry weights and allows editing
 * Weight scale: -1 (avoid) to +1 (prioritize), 0 = neutral
 * View mode shows deviation from calculated target allocation
 */
class IndustryChart extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="pt-4 mt-2 border-t border-gray-700" x-data="industryChartComponent()">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-xs text-gray-300 font-medium">Industry Groups</h3>
          <button x-show="!$store.app.editingIndustry"
                  @click="$store.app.startEditIndustry()"
                  class="text-xs text-purple-400 hover:text-purple-300 transition-colors">
            Edit Weights
          </button>
        </div>

        <!-- View Mode - Show deviation from target allocation -->
        <div x-show="!$store.app.editingIndustry" class="space-y-2">
          <template x-for="ind in (industryAllocations || [])" :key="ind.name">
            <div>
              <div class="flex items-center justify-between text-sm mb-1">
                <span class="text-gray-300 truncate" x-text="ind.name"></span>
                <span class="flex items-center gap-2 flex-shrink-0 ml-2">
                  <span class="font-mono text-gray-300 text-xs" x-text="(ind.current_pct * 100).toFixed(1) + '%'"></span>
                  <span class="text-xs px-1.5 py-0.5 rounded font-mono"
                        :class="getDeviationBadgeClass(getDeviation(ind.name, ind.current_pct))"
                        x-text="formatDeviation(getDeviation(ind.name, ind.current_pct))"></span>
                </span>
              </div>
              <!-- Deviation bar -->
              <div class="h-1.5 bg-gray-700 rounded-full relative overflow-hidden">
                <div class="absolute top-0 bottom-0 left-1/2 w-px bg-gray-500 z-10"></div>
                <div class="absolute top-0 bottom-0 rounded-full transition-all"
                     :class="getDeviationBarColor(ind.name, getDeviation(ind.name, ind.current_pct))"
                     :style="getDeviationBarStyle(getDeviation(ind.name, ind.current_pct))">
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- Edit Mode - Weight sliders for active industries -->
        <div x-show="$store.app.editingIndustry" x-transition class="space-y-3">
          <!-- Weight Scale Legend -->
          <div class="flex justify-between text-xs text-gray-300">
            <span class="text-red-400">-1 Avoid</span>
            <span class="text-gray-400">0 Neutral</span>
            <span class="text-green-400">+1 Prioritize</span>
          </div>

          <template x-for="name in (($store.app.activeIndustries || []).sort())" :key="name">
            <div class="space-y-1">
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-300 truncate" x-text="name"></span>
                <span class="text-xs px-1.5 py-0.5 rounded font-mono ml-2 flex-shrink-0"
                      :class="getWeightBadgeClass($store.app.industryTargets[name] || 0)"
                      x-text="formatWeight($store.app.industryTargets[name] || 0)"></span>
              </div>
              <input type="range" min="-1" max="1" step="0.01"
                     :value="$store.app.industryTargets[name] || 0"
                     @input="$store.app.adjustIndustrySlider(name, parseFloat($event.target.value))"
                     class="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer">
            </div>
          </template>

          <!-- Buttons -->
          <div class="flex gap-2 pt-2">
            <button @click="$store.app.cancelEditIndustry()"
                    class="flex-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded transition-colors">
              Cancel
            </button>
            <button @click="$store.app.saveIndustryTargets()"
                    :disabled="$store.app.loading.industrySave"
                    class="flex-1 px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs rounded transition-colors disabled:opacity-50">
              <span x-show="$store.app.loading.industrySave" class="inline-block animate-spin mr-1">&#9696;</span>
              Save
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

/**
 * Alpine.js component for industry chart helpers
 */
function industryChartComponent() {
  return {
    get industryAllocations() {
      const allocation = this.$store.app.allocation;
      if (!allocation || !allocation.industry) return [];
      return Array.isArray(allocation.industry) ? allocation.industry : [];
    },

    // Convert weights to target percentages
    getTargetPcts() {
      const weights = this.$store.app.industryTargets || {};
      const activeIndustries = this.$store.app.activeIndustries || [];

      // Only consider active industries
      const shifted = {};
      let total = 0;
      for (const name of activeIndustries) {
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

    // Badge class for deviation value - using colors that exist in CSS
    getDeviationBadgeClass(deviation) {
      if (Math.abs(deviation) < 0.02) return 'bg-gray-700 text-gray-300'; // At target
      return deviation > 0
        ? 'bg-red-900 text-red-400'    // Overweight
        : 'bg-blue-900 text-blue-400'; // Underweight
    },

    // Bar color - using colors that exist in CSS
    getDeviationBarColor(name, deviation) {
      if (Math.abs(deviation) < 0.02) return 'bg-gray-500'; // At target
      return deviation > 0 ? 'bg-red-500' : 'bg-blue-500';
    },

    // Bar style for deviation visualization
    getDeviationBarStyle(deviation) {
      // Scale: ±50% deviation = full half bar
      const maxDev = 0.50;
      const pct = Math.min(Math.abs(deviation), maxDev) / maxDev * 50;

      if (deviation >= 0) {
        // Positive: bar extends RIGHT from center
        return `width: ${pct}%; left: 50%; right: auto;`;
      } else {
        // Negative: bar extends LEFT from center
        return `width: ${pct}%; right: 50%; left: auto;`;
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
      return 'bg-gray-700 text-gray-300';
    }
  };
}

customElements.define('industry-chart', IndustryChart);
