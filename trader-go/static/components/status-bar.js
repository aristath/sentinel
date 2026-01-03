/**
 * Status Bar Component
 * Displays system status, last sync time, and portfolio summary
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

        <!-- Portfolio Summary Row -->
        <div class="flex items-center justify-between text-xs text-gray-300">
          <div class="flex items-center gap-3 flex-wrap">
            <span>
              Total Value: <span class="text-green-400 font-mono" x-text="formatCurrency($store.app.allocation.total_value)"></span>
            </span>
            <span class="text-gray-400">|</span>
            <span>
              Cash: <span class="text-gray-300 font-mono" x-text="formatCurrency($store.app.allocation.cash_balance)"></span>
            </span>
            <template x-if="$store.app.cashBreakdown && $store.app.cashBreakdown.length > 0">
              <span class="text-gray-400">
                (<template x-for="(cb, index) in $store.app.cashBreakdown" :key="cb.currency">
                  <span>
                    <!-- TEST currency with green background and inline editing -->
                    <template x-if="cb.currency === 'TEST'">
                      <span class="bg-green-600 bg-opacity-20 px-1 rounded cursor-pointer"
                            @click="$store.app.startEditTestCash(cb.amount)"
                            title="Click to edit test cash (research mode only)">
                        <span x-text="cb.currency" class="text-green-400"></span>:
                        <span class="font-mono text-green-400" x-text="formatNumber(cb.amount, 2)"></span>
                      </span>
                    </template>

                    <!-- Regular currencies -->
                    <template x-if="cb.currency !== 'TEST'">
                      <span>
                        <span x-text="cb.currency"></span>:
                        <span class="font-mono" x-text="formatNumber(cb.amount, 2)"></span>
                      </span>
                    </template>

                    <span x-show="index < $store.app.cashBreakdown.length - 1">, </span>
                  </span>
                </template>)
              </span>
            </template>
            <span class="text-gray-400">|</span>
            <span>
              Positions: <span class="text-gray-300 font-mono" x-text="$store.app.status.active_positions || 0"></span>
            </span>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('status-bar', StatusBar);
