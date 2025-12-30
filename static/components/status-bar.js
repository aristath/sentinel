/**
 * Status Bar Component
 * Displays system status, last sync time, and portfolio summary cards
 */
class StatusBar extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800/50 rounded space-y-3 p-3" x-data>
        <!-- System Status Row -->
        <div class="flex items-center justify-between text-xs text-gray-300">
          <div class="flex items-center gap-3">
            <span class="flex items-center gap-1.5">
              <span class="w-1.5 h-1.5 rounded-full"
                    :class="$store.app.status.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'"></span>
              <span x-text="$store.app.status.status === 'healthy' ? 'System Online' : 'System Offline'"></span>
            </span>
            <span class="text-gray-400">|</span>
            <span>
              Last sync: <span class="text-gray-300" x-text="$store.app.status.last_sync || 'Never'"></span>
            </span>
          </div>
        </div>

        <!-- Portfolio Summary Cards Row -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <!-- Total Value -->
          <div class="bg-gray-800 border border-gray-700 rounded p-3">
            <p class="text-xs text-gray-300 uppercase tracking-wide mb-1">Total Value</p>
            <p class="text-xl font-mono font-bold text-green-400" x-text="formatCurrency($store.app.allocation.total_value)"></p>
          </div>

          <!-- Cash Balance -->
          <div class="bg-gray-800 border border-gray-700 rounded p-3">
            <p class="text-xs text-gray-300 uppercase tracking-wide mb-1">Cash Balance</p>
            <p class="text-xl font-mono font-bold text-gray-100" x-text="formatCurrency($store.app.allocation.cash_balance)"></p>
            <div class="mt-1 space-y-0.5" x-show="$store.app.cashBreakdown && $store.app.cashBreakdown.length > 0">
              <template x-for="cb in $store.app.cashBreakdown" :key="cb.currency">
                <p class="text-xs font-mono text-gray-300">
                  <span x-text="cb.currency"></span>: <span x-text="formatNumber(cb.amount, 2)"></span>
                </p>
              </template>
            </div>
          </div>

          <!-- Active Positions -->
          <div class="bg-gray-800 border border-gray-700 rounded p-3">
            <p class="text-xs text-gray-300 uppercase tracking-wide mb-1">Active Positions</p>
            <p class="text-xl font-mono font-bold text-gray-100" x-text="$store.app.status.active_positions || 0"></p>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('status-bar', StatusBar);
