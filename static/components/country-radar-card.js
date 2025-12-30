/**
 * Country Radar Card Component
 * Card wrapper for country allocation radar chart
 */
class CountryRadarCard extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3" x-data>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xs text-gray-300 uppercase tracking-wide">Country Allocation</h2>
          <template x-if="getCountryAlerts().length > 0">
            <span class="text-xs px-2 py-0.5 rounded font-medium"
                  :class="getCountryAlerts().some(a => a.severity === 'critical') ? 'bg-red-900/50 text-red-400' : 'bg-yellow-900/50 text-yellow-400'"
                  x-text="getCountryAlerts().length + ' alert' + (getCountryAlerts().length > 1 ? 's' : '')"></span>
          </template>
        </div>
        <allocation-radar type="country"></allocation-radar>
        <!-- Country Alerts -->
        <template x-if="getCountryAlerts().length > 0">
          <div class="mt-3 pt-3 border-t border-gray-700 space-y-2">
            <template x-for="alert in getCountryAlerts()" :key="alert.name">
              <div class="flex items-center justify-between text-xs p-2 rounded"
                   :class="alert.severity === 'critical' ? 'bg-red-900/20 border border-red-500/30' : 'bg-yellow-900/20 border border-yellow-500/30'">
                <div class="flex items-center gap-2">
                  <span x-text="alert.severity === 'critical' ? '🔴' : '⚠️'"></span>
                  <span class="font-medium"
                        :class="alert.severity === 'critical' ? 'text-red-300' : 'text-yellow-300'"
                        x-text="alert.name"></span>
                </div>
                <div class="text-right">
                  <div class="font-mono font-semibold"
                       :class="alert.severity === 'critical' ? 'text-red-400' : 'text-yellow-400'"
                       x-text="(alert.current_pct * 100).toFixed(1) + '%'"></div>
                  <div class="text-gray-500 text-xs"
                       x-text="'Limit: ' + (alert.limit_pct * 100).toFixed(0) + '%'"></div>
                </div>
              </div>
            </template>
          </div>
        </template>
      </div>
    `;
  }
}

/**
 * Helper function to get country alerts
 */
function getCountryAlerts() {
  if (!window.Alpine || !window.Alpine.store || !window.Alpine.store('app')) {
    return [];
  }
  const alerts = window.Alpine.store('app').alerts || [];
  return alerts.filter(a => a.type === 'country');
}

// Make available globally
window.getCountryAlerts = getCountryAlerts;

customElements.define('country-radar-card', CountryRadarCard);
