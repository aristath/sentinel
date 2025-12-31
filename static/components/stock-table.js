/**
 * Stock Table Component
 * Displays the security universe with filtering, sorting, and position data
 */
class StockTable extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3" x-data="securityTableComponent()">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xs text-gray-300 uppercase tracking-wide">Security Universe</h2>
          <div class="flex gap-2">
            <button @click="$store.app.openUniverseManagementModal()"
                    class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded transition-colors">
              Manage Universe
            </button>
            <button @click="$store.app.showAddStockModal = true"
                    class="px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white text-xs rounded transition-colors">
              + Add Stock
            </button>
          </div>
        </div>

        <!-- Filter Bar -->
        <div class="flex flex-col sm:flex-row gap-2 mb-3">
          <input type="text"
                 x-model="$store.app.searchQuery"
                 placeholder="Search symbol or name..."
                 class="flex-1 px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
          <div class="flex gap-2">
            <select x-model="$store.app.securityFilter"
                    class="px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
              <option value="all">All Countries</option>
              <template x-for="country in ($store.app.countries || [])" :key="country">
                <option :value="country" x-text="country"></option>
              </template>
            </select>
            <select x-model="$store.app.industryFilter"
                    class="px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
              <option value="all">All Sectors</option>
              <template x-for="ind in ($store.app.industries || [])" :key="ind">
                <option :value="ind" x-text="ind"></option>
              </template>
            </select>
            <select x-model="$store.app.minScore"
                    class="px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
              <option value="0">Any Score</option>
              <option value="0.3">Score >= 0.3</option>
              <option value="0.5">Score >= 0.5</option>
              <option value="0.7">Score >= 0.7</option>
            </select>
          </div>
        </div>

        <!-- Results count -->
        <div class="text-xs text-gray-300 mb-2" x-show="$store.app.securitys.length > 0">
          <span x-text="$store.app.filteredStocks.length"></span> of
          <span x-text="$store.app.securitys.length"></span> securitys
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead class="text-gray-300 uppercase text-left border-b border-gray-700">
              <tr>
                <th @click="$store.app.sortStocks('symbol')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 sticky left-0 bg-gray-800 z-10">
                  Symbol
                  <span x-show="$store.app.sortBy === 'symbol'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th class="py-2 px-1">Chart</th>
                <th @click="$store.app.sortStocks('name')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300">
                  Company
                  <span x-show="$store.app.sortBy === 'name'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('country')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300">
                  Country
                  <span x-show="$store.app.sortBy === 'country'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('fullExchangeName')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300">
                  Exchange
                  <span x-show="$store.app.sortBy === 'fullExchangeName'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('industry')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300">
                  Sector
                  <span x-show="$store.app.sortBy === 'industry'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('position_value')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 text-right">
                  Value
                  <span x-show="$store.app.sortBy === 'position_value'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('total_score')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 text-right">
                  Score
                  <span x-show="$store.app.sortBy === 'total_score'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('priority_multiplier')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 text-center">
                  Mult
                  <span x-show="$store.app.sortBy === 'priority_multiplier'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th class="py-2 px-2 text-center" title="Buy/Sell status">B/S</th>
                <th @click="$store.app.sortStocks('priority_score')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 text-right">
                  Priority
                  <span x-show="$store.app.sortBy === 'priority_score'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th class="py-2 px-2 text-center">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-800">
              <template x-for="security in ($store.app.filteredStocks || [])" :key="security.symbol">
                <tr class="hover:bg-gray-800/50"
                    :class="getPositionAlert(security.symbol) ? (getPositionAlert(security.symbol).severity === 'critical' ? 'border-l-4 border-red-500' : 'border-l-4 border-yellow-500') : ''">
                  <td class="py-1.5 px-2 font-mono text-blue-400 sticky left-0 bg-gray-800">
                    <button @click.stop="$store.app.showStockChart = true; $store.app.selectedStockSymbol = security.symbol; $store.app.selectedStockIsin = security.isin"
                            class="hover:underline cursor-pointer"
                            title="View chart">
                      <span x-text="security.symbol"></span>
                    </button>
                  </td>
                  <td class="py-1.5 px-1">
                    <security-sparkline
                         :symbol="security.symbol"
                         :has-position="security.position_value > 0 ? 'true' : 'false'">
                    </security-sparkline>
                  </td>
                  <td class="py-1.5 px-2 text-gray-300 truncate max-w-32" x-text="security.name"></td>
                  <td class="py-1.5 px-2 text-gray-300 truncate max-w-24" x-text="security.country || '-'"></td>
                  <td class="py-1.5 px-2 text-gray-300 truncate max-w-24" x-text="security.fullExchangeName || '-'"></td>
                  <td class="py-1.5 px-2 text-gray-300 truncate max-w-24" x-text="security.industry || '-'"></td>
                  <td class="py-1.5 px-2 text-right font-mono"
                      :class="getPositionAlertClass(security.symbol)">
                    <div class="flex items-center justify-end gap-2">
                      <span x-text="security.position_value ? formatCurrency(security.position_value) : '-'"></span>
                      <template x-if="getPositionAlert(security.symbol)">
                        <span class="text-xs"
                              :class="getPositionAlert(security.symbol).severity === 'critical' ? 'text-red-400' : 'text-yellow-400'"
                              :title="'Position concentration: ' + (getPositionAlert(security.symbol).current_pct * 100).toFixed(1) + '% (Limit: ' + (getPositionAlert(security.symbol).limit_pct * 100).toFixed(0) + '%)'"
                              x-text="getPositionAlert(security.symbol).severity === 'critical' ? '🔴' : '⚠️'"></span>
                      </template>
                    </div>
                  </td>
                  <td class="py-1.5 px-2 text-right">
                    <span class="font-mono px-1.5 py-0.5 rounded"
                          :class="getScoreClass(security.total_score)"
                          x-text="formatScore(security.total_score)"></span>
                  </td>
                  <td class="py-1.5 px-2 text-center">
                    <input type="number"
                           class="w-12 px-1 py-0.5 bg-gray-900 border border-gray-600 rounded text-center text-xs text-gray-300 focus:border-blue-500 focus:outline-none"
                           :value="security.priority_multiplier || 1"
                           min="0.1"
                           max="3"
                           step="0.1"
                           @click.stop
                           @change="$store.app.updateMultiplier(security.isin, $event.target.value)"
                           title="Priority multiplier (0.1-3.0)">
                  </td>
                  <td class="py-1.5 px-2 text-center">
                    <div class="flex justify-center gap-1">
                      <span x-show="security.allow_buy"
                            class="w-2.5 h-2.5 rounded-full bg-green-500"
                            title="Buy enabled"></span>
                      <span x-show="security.allow_sell"
                            class="w-2.5 h-2.5 rounded-full bg-red-500"
                            title="Sell enabled"></span>
                      <span x-show="!security.allow_buy && !security.allow_sell"
                            class="text-gray-400">-</span>
                    </div>
                  </td>
                  <td class="py-1.5 px-2 text-right">
                    <span class="font-mono px-1.5 py-0.5 rounded"
                          :class="getPriorityClass(security.priority_score)"
                          x-text="formatPriority(security.priority_score)"></span>
                  </td>
                  <td class="py-1.5 px-2 text-center" @click.stop>
                    <div class="flex justify-center gap-1">
                      <button @click="$store.app.openEditStock(security)"
                              class="p-1 text-gray-300 hover:text-blue-400 transition-colors"
                              title="Edit security">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                      </button>
                      <button @click="$store.app.refreshSingleScore(security.isin)"
                              class="p-1 text-gray-300 hover:text-green-400 transition-colors"
                              title="Refresh score">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M21 2v6h-6"/>
                          <path d="M3 12a9 9 0 0 1 15-6.7L21 8"/>
                          <path d="M3 22v-6h6"/>
                          <path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>
                        </svg>
                      </button>
                      <button @click="$store.app.removeStock(security.isin)"
                              class="p-1 text-gray-300 hover:text-red-400 transition-colors"
                              title="Remove from universe">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M3 6h18"/>
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                          <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <!-- Empty states -->
        <div x-show="$store.app.filteredStocks.length === 0 && $store.app.securitys.length > 0"
             class="text-center py-6 text-gray-300 text-sm">
          No securitys match your filters
        </div>
        <div x-show="$store.app.securitys.length === 0"
             class="text-center py-6 text-gray-300 text-sm">
          No securitys in universe
        </div>
      </div>
    `;
  }
}

/**
 * Alpine.js component for table interactions
 */
function securityTableComponent() {
  return {
    init() {
      this.$watch('$store.app.minScore', (val) => {
        this.$store.app.minScore = parseFloat(val) || 0;
      });
    }
  };
}

/**
 * Helper functions for position alerts
 */
function getPositionAlert(symbol) {
  if (!window.Alpine || !window.Alpine.store || !window.Alpine.store('app')) {
    return null;
  }
  const alerts = window.Alpine.store('app').alerts || [];
  return alerts.find(a => a.type === 'position' && a.name === symbol) || null;
}

function getPositionAlertClass(symbol) {
  const alert = getPositionAlert(symbol);
  if (!alert) {
    // Default: check if security has position value
    const security = (window.Alpine?.store('app')?.securitys || []).find(s => s.symbol === symbol);
    return security?.position_value ? 'text-green-400' : 'text-gray-400';
  }
  // Highlight row with border color based on severity
  return alert.severity === 'critical'
    ? 'text-red-400'
    : 'text-yellow-400';
}

// Make available globally
window.getPositionAlert = getPositionAlert;
window.getPositionAlertClass = getPositionAlertClass;

customElements.define('security-table', StockTable);
