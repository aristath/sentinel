/**
 * Settings Modal Component
 * Application settings in a modal dialog
 */
class SettingsModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showSettingsModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-4"
           x-transition
           @click="$store.app.showSettingsModal = false">
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-md max-h-[90vh] overflow-y-auto" @click.stop>
          <div class="flex items-center justify-between p-4 border-b border-gray-700 sticky top-0 bg-gray-800">
            <h2 class="text-lg font-semibold text-gray-100">Settings</h2>
            <button @click="$store.app.showSettingsModal = false"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <div class="p-4 space-y-4">
            <!-- Trading Parameters Section -->
            <div class="border-b border-gray-700 pb-4">
              <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Trading Parameters</h3>

              <!-- Min Trade Size -->
              <div class="flex items-center justify-between mb-3">
                <div>
                  <span class="text-sm text-gray-300">Min Trade Size</span>
                  <p class="text-xs text-gray-500">Minimum EUR for a buy order</p>
                </div>
                <div class="flex items-center gap-1">
                  <span class="text-gray-400">EUR</span>
                  <input type="number"
                         :value="$store.app.settings.min_trade_size"
                         @change="$store.app.updateSetting('min_trade_size', $event.target.value)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                </div>
              </div>

              <!-- Min Hold Days -->
              <div class="flex items-center justify-between mb-3">
                <div>
                  <span class="text-sm text-gray-300">Min Hold Days</span>
                  <p class="text-xs text-gray-500">Minimum days before selling</p>
                </div>
                <div class="flex items-center gap-1">
                  <input type="number"
                         :value="$store.app.settings.min_hold_days"
                         @change="$store.app.updateSetting('min_hold_days', $event.target.value)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  <span class="text-gray-400">days</span>
                </div>
              </div>

              <!-- Sell Cooldown Days -->
              <div class="flex items-center justify-between mb-3">
                <div>
                  <span class="text-sm text-gray-300">Sell Cooldown</span>
                  <p class="text-xs text-gray-500">Days between sells of same stock</p>
                </div>
                <div class="flex items-center gap-1">
                  <input type="number"
                         :value="$store.app.settings.sell_cooldown_days"
                         @change="$store.app.updateSetting('sell_cooldown_days', $event.target.value)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  <span class="text-gray-400">days</span>
                </div>
              </div>

              <!-- Max Loss Threshold -->
              <div class="flex items-center justify-between mb-3">
                <div>
                  <span class="text-sm text-gray-300">Max Loss Threshold</span>
                  <p class="text-xs text-gray-500">Don't sell if loss exceeds this</p>
                </div>
                <div class="flex items-center gap-1">
                  <input type="number"
                         step="0.01"
                         :value="($store.app.settings.max_loss_threshold * 100).toFixed(0)"
                         @change="$store.app.updateSetting('max_loss_threshold', $event.target.value / 100)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  <span class="text-gray-400">%</span>
                </div>
              </div>

              <!-- Min Sell Value -->
              <div class="flex items-center justify-between">
                <div>
                  <span class="text-sm text-gray-300">Min Sell Value</span>
                  <p class="text-xs text-gray-500">Minimum EUR value to sell</p>
                </div>
                <div class="flex items-center gap-1">
                  <span class="text-gray-400">EUR</span>
                  <input type="number"
                         :value="$store.app.settings.min_sell_value"
                         @change="$store.app.updateSetting('min_sell_value', $event.target.value)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                </div>
              </div>
            </div>

            <!-- Scoring Parameters Section -->
            <div class="border-b border-gray-700 pb-4">
              <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Scoring Parameters</h3>

              <!-- Target Annual Return -->
              <div class="flex items-center justify-between mb-3">
                <div>
                  <span class="text-sm text-gray-300">Target Annual Return</span>
                  <p class="text-xs text-gray-500">Optimal CAGR for scoring</p>
                </div>
                <div class="flex items-center gap-1">
                  <input type="number"
                         step="1"
                         :value="($store.app.settings.target_annual_return * 100).toFixed(0)"
                         @change="$store.app.updateSetting('target_annual_return', $event.target.value / 100)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  <span class="text-gray-400">%</span>
                </div>
              </div>

              <!-- Market Avg P/E -->
              <div class="flex items-center justify-between">
                <div>
                  <span class="text-sm text-gray-300">Market Avg P/E</span>
                  <p class="text-xs text-gray-500">Reference P/E for valuation</p>
                </div>
                <div class="flex items-center gap-1">
                  <input type="number"
                         step="0.1"
                         :value="$store.app.settings.market_avg_pe"
                         @change="$store.app.updateSetting('market_avg_pe', $event.target.value)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                </div>
              </div>
            </div>

            <!-- System Actions Section -->
            <div class="space-y-3">
              <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">System</h3>

              <!-- Cache Reset -->
              <div class="flex items-center justify-between">
                <span class="text-sm text-gray-300">Caches</span>
                <button @click="$store.app.resetCache()"
                        class="px-3 py-1.5 bg-gray-600 hover:bg-gray-500 text-white text-xs rounded transition-colors">
                  Reset
                </button>
              </div>

              <!-- Sync Historical -->
              <div class="flex items-center justify-between">
                <span class="text-sm text-gray-300">Historical Data</span>
                <button @click="$store.app.syncHistorical()"
                        :disabled="$store.app.loading.historical"
                        class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded transition-colors disabled:opacity-50">
                  <span x-show="$store.app.loading.historical" class="inline-block animate-spin mr-1">&#9696;</span>
                  <span x-text="$store.app.loading.historical ? 'Syncing...' : 'Sync'"></span>
                </button>
              </div>

              <!-- System Restart -->
              <div class="flex items-center justify-between">
                <span class="text-sm text-gray-300">System</span>
                <button @click="if(confirm('Reboot the system?')) API.restartSystem()"
                        class="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs rounded transition-colors">
                  Restart
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('settings-modal', SettingsModal);
