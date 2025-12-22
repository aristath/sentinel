/**
 * Industry Allocation Component
 * Displays industry weights and allows editing
 * Weight scale: -1 (avoid) to +1 (prioritize), 0 = neutral
 */
class IndustryChart extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3" x-data="industryChartComponent()">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xs text-gray-400 uppercase tracking-wide">Industry Weights</h2>
          <button x-show="!$store.app.editingIndustry"
                  @click="$store.app.startEditIndustry()"
                  class="text-xs text-purple-400 hover:text-purple-300 transition-colors">
            Edit Weights
          </button>
        </div>

        <!-- View Mode - Show weights as horizontal bars -->
        <div x-show="!$store.app.editingIndustry" class="space-y-2">
          <template x-for="ind in (industryAllocations || []).filter(i => $store.app.activeIndustries && $store.app.activeIndustries.includes(i.name))" :key="ind.name">
            <div>
              <div class="flex items-center justify-between text-sm mb-1">
                <span class="text-gray-300 truncate" x-text="ind.name"></span>
                <span class="text-xs px-1.5 py-0.5 rounded font-mono ml-2 flex-shrink-0"
                      :class="getWeightBadgeClass(ind.target_pct)"
                      x-text="formatWeight(ind.target_pct)"></span>
              </div>
              <div class="h-1.5 bg-gray-700 rounded-full relative">
                <div class="absolute top-0 bottom-0 left-1/2 w-px bg-gray-500"></div>
                <div class="absolute top-0 bottom-0 rounded-full transition-all"
                     :class="ind.target_pct >= 0 ? 'bg-green-500' : 'bg-red-500'"
                     :style="'width: ' + (Math.abs(ind.target_pct || 0) * 50) + '%; ' +
                             (ind.target_pct >= 0 ? 'left: 50%' : 'right: 50%')">
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- Edit Mode - Weight sliders for active industries -->
        <div x-show="$store.app.editingIndustry" x-transition class="space-y-3">
          <!-- Weight Scale Legend -->
          <div class="flex justify-between text-xs text-gray-500">
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

customElements.define('industry-chart', IndustryChart);
