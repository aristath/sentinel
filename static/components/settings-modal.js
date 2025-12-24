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
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-lg max-h-[90vh] overflow-y-auto" @click.stop>
          <div class="flex items-center justify-between p-4 border-b border-gray-700 sticky top-0 bg-gray-800">
            <h2 class="text-lg font-semibold text-gray-100">Settings</h2>
            <button @click="$store.app.showSettingsModal = false"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <div class="p-4 space-y-4">
            <!-- Trading Parameters Section -->
            <div class="border-b border-gray-700 pb-4">
              <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Trading Parameters</h3>

              <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                <!-- Min Trade Size -->
                <div>
                  <span class="text-sm text-gray-300">Min Trade Size</span>
                  <p class="text-xs text-gray-500">Minimum amount in EUR required to place a buy order</p>
                </div>
                <div class="flex items-center gap-1">
                  <span class="text-gray-400 text-sm">EUR</span>
                  <input type="number"
                         :value="$store.app.settings.min_trade_size"
                         @change="$store.app.updateSetting('min_trade_size', $event.target.value)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                </div>

                <!-- Min Hold Days -->
                <div>
                  <span class="text-sm text-gray-300">Min Hold Days</span>
                  <p class="text-xs text-gray-500">Stocks must be held for at least this many days before they can be sold</p>
                </div>
                <div class="flex items-center gap-1">
                  <input type="number"
                         :value="$store.app.settings.min_hold_days"
                         @change="$store.app.updateSetting('min_hold_days', $event.target.value)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  <span class="text-gray-400 text-sm">days</span>
                </div>

                <!-- Sell Cooldown Days -->
                <div>
                  <span class="text-sm text-gray-300">Sell Cooldown</span>
                  <p class="text-xs text-gray-500">After selling a stock, wait this many days before selling it again</p>
                </div>
                <div class="flex items-center gap-1">
                  <input type="number"
                         :value="$store.app.settings.sell_cooldown_days"
                         @change="$store.app.updateSetting('sell_cooldown_days', $event.target.value)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  <span class="text-gray-400 text-sm">days</span>
                </div>

                <!-- Max Loss Threshold -->
                <div>
                  <span class="text-sm text-gray-300">Max Loss Threshold</span>
                  <p class="text-xs text-gray-500">Never sell a position if the loss exceeds this percentage (protects against selling at the bottom)</p>
                </div>
                <div class="flex items-center gap-1">
                  <input type="number"
                         step="1"
                         :value="($store.app.settings.max_loss_threshold * 100).toFixed(0)"
                         @change="$store.app.updateSetting('max_loss_threshold', $event.target.value / 100)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  <span class="text-gray-400 text-sm">%</span>
                </div>

                <!-- Min Sell Value -->
                <div>
                  <span class="text-sm text-gray-300">Min Sell Value</span>
                  <p class="text-xs text-gray-500">Minimum value in EUR that a sell order must be worth</p>
                </div>
                <div class="flex items-center gap-1">
                  <span class="text-gray-400 text-sm">EUR</span>
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

              <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                <!-- Target Annual Return -->
                <div>
                  <span class="text-sm text-gray-300">Target Annual Return</span>
                  <p class="text-xs text-gray-500">Target yearly growth rate (CAGR = Compound Annual Growth Rate). Stocks near this return get higher scores</p>
                </div>
                <div class="flex items-center gap-1">
                  <input type="number"
                         step="1"
                         :value="($store.app.settings.target_annual_return * 100).toFixed(0)"
                         @change="$store.app.updateSetting('target_annual_return', $event.target.value / 100)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  <span class="text-gray-400 text-sm">%</span>
                </div>

                <!-- Market Avg P/E -->
                <div>
                  <span class="text-sm text-gray-300">Market Avg P/E</span>
                  <p class="text-xs text-gray-500">Average Price-to-Earnings ratio for the market. Stocks below this P/E are considered undervalued</p>
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

            <!-- LED Matrix Section -->
            <div class="border-b border-gray-700 pb-4">
              <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">LED Matrix</h3>

              <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                <!-- Ticker Speed -->
                <div>
                  <span class="text-sm text-gray-300">Ticker Speed</span>
                  <p class="text-xs text-gray-500">How fast the ticker scrolls across the LED matrix. Lower values = faster scrolling. Default is 50ms</p>
                </div>
                <div class="flex items-center gap-1">
                  <input type="number"
                         min="1"
                         max="100"
                         step="1"
                         :value="$store.app.settings.ticker_speed"
                         @change="$store.app.updateSetting('ticker_speed', $event.target.value)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  <span class="text-gray-400 text-sm">ms</span>
                </div>

                <!-- LED Brightness -->
                <div>
                  <span class="text-sm text-gray-300">Brightness</span>
                  <p class="text-xs text-gray-500">Brightness of the LED matrix display. Range: 0 (off) to 255 (maximum). Lower values save power and reduce eye strain in dark rooms. Default is 150</p>
                </div>
                <div class="flex items-center gap-1">
                  <input type="number"
                         min="0"
                         max="255"
                         step="10"
                         :value="$store.app.settings.led_brightness"
                         @change="$store.app.updateSetting('led_brightness', $event.target.value)"
                         class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                </div>
              </div>

              <!-- Ticker Content Options -->
              <div class="mt-4 pt-3 border-t border-gray-700/50">
                <span class="text-xs text-gray-500 uppercase tracking-wide">Ticker Content</span>
                <div class="mt-2 space-y-2">
                  <!-- Show Portfolio Value -->
                  <label class="flex items-start gap-3 cursor-pointer">
                    <input type="checkbox"
                           :checked="$store.app.settings.ticker_show_value == 1"
                           @change="$store.app.updateSetting('ticker_show_value', $event.target.checked ? 1 : 0)"
                           class="mt-0.5 w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                    <div>
                      <span class="text-sm text-gray-300">Show portfolio value</span>
                      <p class="text-xs text-gray-500">Display total portfolio value (e.g., "EUR 18,647") in the scrolling ticker</p>
                    </div>
                  </label>

                  <!-- Show Cash Balance -->
                  <label class="flex items-start gap-3 cursor-pointer">
                    <input type="checkbox"
                           :checked="$store.app.settings.ticker_show_cash == 1"
                           @change="$store.app.updateSetting('ticker_show_cash', $event.target.checked ? 1 : 0)"
                           class="mt-0.5 w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                    <div>
                      <span class="text-sm text-gray-300">Show cash balance</span>
                      <p class="text-xs text-gray-500">Display available cash (e.g., "CASH EUR 675") in the scrolling ticker</p>
                    </div>
                  </label>

                  <!-- Show Next Actions -->
                  <label class="flex items-start gap-3 cursor-pointer">
                    <input type="checkbox"
                           :checked="$store.app.settings.ticker_show_actions == 1"
                           @change="$store.app.updateSetting('ticker_show_actions', $event.target.checked ? 1 : 0)"
                           class="mt-0.5 w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                    <div>
                      <span class="text-sm text-gray-300">Show next actions</span>
                      <p class="text-xs text-gray-500">Display upcoming trades (e.g., "BUY XIAO", "SELL ABC") in the scrolling ticker</p>
                    </div>
                  </label>

                  <!-- Show Amounts for Actions -->
                  <label class="flex items-start gap-3 cursor-pointer">
                    <input type="checkbox"
                           :checked="$store.app.settings.ticker_show_amounts == 1"
                           @change="$store.app.updateSetting('ticker_show_amounts', $event.target.checked ? 1 : 0)"
                           class="mt-0.5 w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                    <div>
                      <span class="text-sm text-gray-300">Show amounts for actions</span>
                      <p class="text-xs text-gray-500">Include EUR amounts with actions (e.g., "BUY XIAO EUR855" vs just "BUY XIAO")</p>
                    </div>
                  </label>

                  <!-- Max Actions -->
                  <div class="flex items-start gap-3 pt-2">
                    <div class="flex-1">
                      <span class="text-sm text-gray-300">Max actions to show</span>
                      <p class="text-xs text-gray-500">Maximum number of buy/sell recommendations to display in the ticker (each type)</p>
                    </div>
                    <input type="number"
                           min="1"
                           max="5"
                           step="1"
                           :value="$store.app.settings.ticker_max_actions"
                           @change="$store.app.updateSetting('ticker_max_actions', $event.target.value)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  </div>
                </div>
              </div>
            </div>

            <!-- System Actions Section -->
            <div>
              <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">System</h3>

              <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-center">
                <!-- Cache Reset -->
                <span class="text-sm text-gray-300">Caches</span>
                <button @click="$store.app.resetCache()"
                        class="px-3 py-1.5 bg-gray-600 hover:bg-gray-500 text-white text-xs rounded transition-colors">
                  Reset
                </button>

                <!-- Sync Historical -->
                <span class="text-sm text-gray-300">Historical Data</span>
                <button @click="$store.app.syncHistorical()"
                        :disabled="$store.app.loading.historical"
                        class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded transition-colors disabled:opacity-50">
                  <span x-show="$store.app.loading.historical" class="inline-block animate-spin mr-1">&#9696;</span>
                  <span x-text="$store.app.loading.historical ? 'Syncing...' : 'Sync'"></span>
                </button>

                <!-- System Restart -->
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
