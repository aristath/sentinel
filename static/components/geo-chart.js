/**
 * Geographic Allocation Chart Component
 * Displays SVG doughnut chart and allows editing geographic weights
 * Weight scale: -1 (avoid) to +1 (prioritize), 0 = neutral
 */
class GeoChart extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="card" x-data="geoChartComponent()">
        <div class="card__header">
          <h2 class="card__title">Geographic Weights</h2>
          <button x-show="!$store.app.editingGeo"
                  @click="$store.app.startEditGeo()"
                  class="card__action">
            Edit Weights
          </button>
        </div>

        <div class="chart-container">
          <svg viewBox="0 0 100 100" class="doughnut-chart">
            <!-- Background circle -->
            <circle cx="50" cy="50" r="40" fill="none" stroke="#374151" stroke-width="16"/>

            <!-- Dynamic segments based on active geographies -->
            <template x-for="(geo, index) in $store.app.allocation.geographic" :key="geo.name">
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
        <div x-show="!$store.app.editingGeo" class="allocation-list">
          <template x-for="geo in $store.app.allocation.geographic.filter(g => $store.app.activeGeographies.includes(g.name))" :key="geo.name">
            <div class="allocation-item">
              <span class="allocation-item__label">
                <span class="allocation-item__dot"
                      :class="'allocation-item__dot--' + geo.name.toLowerCase()"></span>
                <span x-text="geo.name"></span>
              </span>
              <span class="allocation-item__value">
                <span x-text="(geo.current_pct * 100).toFixed(1)"></span>%
                <span class="weight-badge" :class="getWeightClass(geo.target_pct)"
                      x-text="formatWeight(geo.target_pct)"></span>
              </span>
            </div>
          </template>
        </div>

        <!-- Edit Mode - Weight sliders for active geographies -->
        <div x-show="$store.app.editingGeo" x-transition class="edit-mode">
          <!-- Weight Scale Legend -->
          <div class="weight-legend">
            <span class="weight-legend__item weight-legend__item--negative">-1 Avoid</span>
            <span class="weight-legend__item weight-legend__item--neutral">0 Neutral</span>
            <span class="weight-legend__item weight-legend__item--positive">+1 Prioritize</span>
          </div>

          <!-- Dynamic Geo Sliders - only for active geographies -->
          <template x-for="name in $store.app.activeGeographies.sort()" :key="name">
            <div class="slider-control">
              <div class="slider-control__header">
                <span class="allocation-item__label">
                  <span class="allocation-item__dot"
                        :class="'allocation-item__dot--' + name.toLowerCase()"></span>
                  <span x-text="name"></span>
                </span>
                <span class="slider-control__value"
                      :class="getWeightClass($store.app.geoTargets[name] || 0)"
                      x-text="formatWeight($store.app.geoTargets[name] || 0)"></span>
              </div>
              <input type="range" min="-1" max="1" step="0.01"
                     :value="$store.app.geoTargets[name] || 0"
                     @input="$store.app.adjustGeoSlider(name, parseFloat($event.target.value))"
                     class="slider slider--weight">
            </div>
          </template>

          <!-- Buttons -->
          <div class="button-row">
            <button @click="$store.app.cancelEditGeo()" class="btn btn--secondary">
              Cancel
            </button>
            <button @click="$store.app.saveGeoTargets()"
                    :disabled="$store.app.loading.geoSave"
                    class="btn btn--primary">
              <span x-show="$store.app.loading.geoSave" class="btn__spinner">&#9696;</span>
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
    // Circumference of circle with radius 40
    circumference: 2 * Math.PI * 40,

    /**
     * Get color for a geography
     */
    getGeoColor(name) {
      return geoColors[name] || '#6B7280';
    },

    /**
     * Get the stroke-dashoffset for a segment
     */
    getOffset(index) {
      const geo = this.$store.app.allocation.geographic;
      if (!geo || !geo[index]) {
        return this.circumference;
      }
      const pct = geo[index].current_pct || 0;
      return this.circumference * (1 - pct);
    },

    /**
     * Get the rotation for a segment (cumulative of previous segments)
     */
    getRotation(index) {
      const geo = this.$store.app.allocation.geographic;
      if (!geo) return -90;

      let cumulative = 0;
      for (let i = 0; i < index; i++) {
        cumulative += (geo[i]?.current_pct || 0);
      }
      return -90 + (cumulative * 360);
    },

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

customElements.define('geo-chart', GeoChart);
