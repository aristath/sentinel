/**
 * Industry Allocation Component
 * Displays industry weights and allows editing
 * Weight scale: -1 (avoid) to +1 (prioritize), 0 = neutral
 */
class IndustryChart extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="card" x-data="industryChartComponent()">
        <div class="card__header">
          <h2 class="card__title">Industry Weights</h2>
          <button x-show="!$store.app.editingIndustry"
                  @click="$store.app.startEditIndustry()"
                  class="card__action card__action--purple">
            Edit Weights
          </button>
        </div>

        <!-- View Mode - Show weights as horizontal bars -->
        <div x-show="!$store.app.editingIndustry">
          <template x-for="ind in $store.app.allocation.industry.filter(i => $store.app.activeIndustries.includes(i.name))" :key="ind.name">
            <div class="weight-item">
              <div class="weight-item__header">
                <span x-text="ind.name"></span>
                <span class="weight-item__value"
                      :class="getWeightClass(ind.target_pct)"
                      x-text="formatWeight(ind.target_pct)"></span>
              </div>
              <div class="weight-bar">
                <div class="weight-bar__track">
                  <div class="weight-bar__center"></div>
                  <div class="weight-bar__fill"
                       :class="ind.target_pct >= 0 ? 'weight-bar__fill--positive' : 'weight-bar__fill--negative'"
                       :style="'width: ' + (Math.abs(ind.target_pct || 0) * 50) + '%; ' +
                               (ind.target_pct >= 0 ? 'left: 50%' : 'right: 50%')">
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- Edit Mode - Weight sliders for active industries -->
        <div x-show="$store.app.editingIndustry" x-transition>
          <!-- Weight Scale Legend -->
          <div class="weight-legend">
            <span class="weight-legend__item weight-legend__item--negative">-1 Avoid</span>
            <span class="weight-legend__item weight-legend__item--neutral">0 Neutral</span>
            <span class="weight-legend__item weight-legend__item--positive">+1 Prioritize</span>
          </div>

          <template x-for="name in $store.app.activeIndustries.sort()" :key="name">
            <div class="slider-control">
              <div class="slider-control__header">
                <span x-text="name"></span>
                <span class="slider-control__value"
                      :class="getWeightClass($store.app.industryTargets[name] || 0)"
                      x-text="formatWeight($store.app.industryTargets[name] || 0)"></span>
              </div>
              <input type="range" min="-1" max="1" step="0.01"
                     :value="$store.app.industryTargets[name] || 0"
                     @input="$store.app.adjustIndustrySlider(name, parseFloat($event.target.value))"
                     class="slider slider--weight slider--purple">
            </div>
          </template>

          <!-- Buttons -->
          <div class="button-row">
            <button @click="$store.app.cancelEditIndustry()" class="btn btn--secondary">
              Cancel
            </button>
            <button @click="$store.app.saveIndustryTargets()"
                    :disabled="$store.app.loading.industrySave"
                    class="btn btn--purple">
              <span x-show="$store.app.loading.industrySave" class="btn__spinner">&#9696;</span>
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
    /**
     * Format weight value for display (+0.50, -0.25, 0)
     */
    formatWeight(weight) {
      if (weight === 0 || weight === undefined) return '0';
      const sign = weight > 0 ? '+' : '';
      return sign + weight.toFixed(2);
    },

    /**
     * Get CSS class for weight value
     */
    getWeightClass(weight) {
      if (weight > 0.1) return 'weight--positive';
      if (weight < -0.1) return 'weight--negative';
      return 'weight--neutral';
    }
  };
}

customElements.define('industry-chart', IndustryChart);
