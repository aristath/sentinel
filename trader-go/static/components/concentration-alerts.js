/**
 * Concentration Alerts Component
 * Displays alerts when portfolio allocations approach hard concentration limits
 */
class ConcentrationAlerts extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data="{ dismissedAlerts: [] }" x-show="$store.app.alerts && $store.app.alerts.length > 0">
        <div class="space-y-2">
          <template x-for="alert in $store.app.alerts.filter(a => !dismissedAlerts.includes(a.type + ':' + a.name))" :key="alert.type + ':' + alert.name">
            <div class="flex items-center justify-between p-3 rounded-lg border-2 transition-all"
                 :class="alert.severity === 'critical' ? 'bg-red-900/20 border-red-500/50' : 'bg-yellow-900/20 border-yellow-500/50'">
              <div class="flex items-center gap-3 flex-1">
                <div class="flex-shrink-0">
                  <span class="text-lg" x-text="alert.severity === 'critical' ? '🔴' : '⚠️'"></span>
                </div>
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-semibold"
                       :class="alert.severity === 'critical' ? 'text-red-300' : 'text-yellow-300'"
                       x-text="getAlertTitle(alert)"></div>
                  <div class="text-xs text-gray-300 mt-0.5"
                       x-text="getAlertMessage(alert)"></div>
                </div>
                <div class="flex-shrink-0 text-right">
                  <div class="text-sm font-mono font-bold"
                       :class="alert.severity === 'critical' ? 'text-red-400' : 'text-yellow-400'"
                       x-text="(alert.current_pct * 100).toFixed(1) + '%'"></div>
                  <div class="text-xs text-gray-300"
                       x-text="'Limit: ' + (alert.limit_pct * 100).toFixed(0) + '%'"></div>
                </div>
              </div>
              <button @click="dismissedAlerts.push(alert.type + ':' + alert.name)"
                      class="ml-3 text-gray-300 hover:text-gray-200 transition-colors"
                      title="Dismiss alert">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 6L6 18M6 6l12 12"/>
                </svg>
              </button>
            </div>
          </template>
        </div>
      </div>
    `;
  }
}

/**
 * Helper functions for alert display
 */
function getAlertTitle(alert) {
  const typeLabels = {
    country: 'Country Concentration',
    sector: 'Sector Concentration',
    position: 'Position Concentration'
  };
  return `${typeLabels[alert.type] || alert.type}: ${alert.name}`;
}

function getAlertMessage(alert) {
  const pct = (alert.current_pct * 100).toFixed(1);
  const limit = (alert.limit_pct * 100).toFixed(0);
  const threshold = (alert.alert_threshold_pct * 100).toFixed(0);

  if (alert.severity === 'critical') {
    return `At ${pct}% of portfolio, approaching ${limit}% hard limit. Consider reducing exposure.`;
  } else {
    return `At ${pct}% of portfolio (${threshold}% alert threshold). Monitor closely.`;
  }
}

// Make helper functions available globally
window.getAlertTitle = getAlertTitle;
window.getAlertMessage = getAlertMessage;

customElements.define('concentration-alerts', ConcentrationAlerts);
