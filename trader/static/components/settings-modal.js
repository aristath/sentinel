/**
 * Settings Modal Component
 * Tabbed interface for organized settings management
 *
 * Note: Score weight settings have been removed. The portfolio optimizer
 * now handles allocation decisions. Per-security scoring uses fixed weights.
 */
class SettingsModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data="{ activeTab: 'trading', showAdvanced: false }"
           x-show="$store.app.showSettingsModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex flex-col"
           x-transition
           @click="$store.app.showSettingsModal = false">
        <div class="w-full h-full bg-gray-900 overflow-y-auto" @click.stop>
          <!-- Sticky Header with Tabs -->
          <div class="sticky top-0 bg-gray-900 z-10 border-b border-gray-700">
            <div class="flex items-center justify-between p-4">
              <h2 class="text-lg font-semibold text-gray-100">Settings</h2>
              <button @click="$store.app.showSettingsModal = false"
                      class="text-gray-300 hover:text-gray-100 text-2xl leading-none">&times;</button>
            </div>
            <!-- Tab Navigation -->
            <div class="flex border-b border-gray-700 px-4">
              <button @click="activeTab = 'trading'"
                      :class="activeTab === 'trading' ? 'border-b-2 border-blue-500 text-blue-400' : 'text-gray-300 hover:text-gray-100'"
                      class="px-4 py-2 text-sm font-medium transition-colors">
                Trading
              </button>
              <button @click="activeTab = 'portfolio'"
                      :class="activeTab === 'portfolio' ? 'border-b-2 border-blue-500 text-blue-400' : 'text-gray-300 hover:text-gray-100'"
                      class="px-4 py-2 text-sm font-medium transition-colors">
                Portfolio
              </button>
              <button @click="activeTab = 'display'"
                      :class="activeTab === 'display' ? 'border-b-2 border-blue-500 text-blue-400' : 'text-gray-300 hover:text-gray-100'"
                      class="px-4 py-2 text-sm font-medium transition-colors">
                Display
              </button>
              <button @click="activeTab = 'system'"
                      :class="activeTab === 'system' ? 'border-b-2 border-blue-500 text-blue-400' : 'text-gray-300 hover:text-gray-100'"
                      class="px-4 py-2 text-sm font-medium transition-colors">
                System
              </button>
            </div>
          </div>

          <!-- Tab Content -->
          <div class="p-4 md:p-6 lg:p-8">
            <div class="max-w-7xl mx-auto">

              <!-- Trading Tab -->
              <div x-show="activeTab === 'trading'" x-transition class="space-y-6">

                <!-- Trade Frequency Limits -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">Trade Frequency Limits</h3>
                  <p class="text-xs text-gray-300 mb-4">Prevent excessive trading by enforcing minimum time between trades and daily/weekly limits. Critical for long-term retirement fund management.</p>
                  <div class="space-y-3">
                    <label class="flex items-center gap-3 cursor-pointer">
                      <input type="checkbox"
                             :checked="$store.app.settings.trade_frequency_limits_enabled == 1"
                             @change="$store.app.updateSetting('trade_frequency_limits_enabled', $event.target.checked ? 1 : 0)"
                             class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                      <span class="text-sm text-gray-300">Enable frequency limits</span>
                    </label>
                    <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                      <div>
                        <span class="text-sm text-gray-300">Min Time Between Trades</span>
                        <p class="text-xs text-gray-300">Minimum minutes between any trades</p>
                      </div>
                      <div class="flex items-center gap-1">
                        <input type="number"
                               min="0"
                               step="5"
                               :value="$store.app.settings.min_time_between_trades_minutes || 60"
                               @change="$store.app.updateSetting('min_time_between_trades_minutes', $event.target.value)"
                               class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                        <span class="text-gray-300 text-sm">min</span>
                      </div>
                      <div>
                        <span class="text-sm text-gray-300">Max Trades Per Day</span>
                        <p class="text-xs text-gray-300">Maximum trades per calendar day</p>
                      </div>
                      <div class="flex items-center gap-1">
                        <input type="number"
                               min="1"
                               step="1"
                               :value="$store.app.settings.max_trades_per_day || 4"
                               @change="$store.app.updateSetting('max_trades_per_day', $event.target.value)"
                               class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      </div>
                      <div>
                        <span class="text-sm text-gray-300">Max Trades Per Week</span>
                        <p class="text-xs text-gray-300">Maximum trades per rolling 7-day window</p>
                      </div>
                      <div class="flex items-center gap-1">
                        <input type="number"
                               min="1"
                               step="1"
                               :value="$store.app.settings.max_trades_per_week || 10"
                               @change="$store.app.updateSetting('max_trades_per_week', $event.target.value)"
                               class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      </div>
                    </div>
                    <div class="mt-3 pt-3 border-t border-gray-700/50">
                      <p class="text-xs text-gray-300">These limits help prevent overtrading and reduce transaction costs. Defaults are conservative for long-term retirement funds.</p>
                    </div>
                  </div>
                </div>

                <!-- Transaction Costs -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">Transaction Costs</h3>
                  <p class="text-xs text-gray-300 mb-4">Freedom24 fee structure. Used to calculate minimum worthwhile trade size.</p>
                  <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                    <div>
                      <span class="text-sm text-gray-300">Fixed Cost</span>
                      <p class="text-xs text-gray-300">Per trade</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <span class="text-gray-300 text-sm">EUR</span>
                      <input type="number"
                             step="0.5"
                             min="0"
                             :value="$store.app.settings.transaction_cost_fixed"
                             @change="$store.app.updateSetting('transaction_cost_fixed', $event.target.value)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Variable Cost</span>
                      <p class="text-xs text-gray-300">Percentage of trade</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             step="0.01"
                             min="0"
                             :value="($store.app.settings.transaction_cost_percent * 100).toFixed(2)"
                             @change="$store.app.updateSetting('transaction_cost_percent', $event.target.value / 100)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-300 text-sm">%</span>
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Min Cash Reserve</span>
                      <p class="text-xs text-gray-300">Never deploy below this</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <span class="text-gray-300 text-sm">EUR</span>
                      <input type="number"
                             step="50"
                             min="0"
                             :value="$store.app.settings.min_cash_reserve"
                             @change="$store.app.updateSetting('min_cash_reserve', $event.target.value)"
                             class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                  </div>
                  <div class="mt-4 pt-3 border-t border-gray-700/50">
                    <div class="flex items-center justify-between">
                      <span class="text-xs text-gray-300">Min worthwhile trade (1% cost):</span>
                      <span class="text-sm text-gray-300 font-mono"
                            x-text="'EUR ' + (($store.app.settings.transaction_cost_fixed || 2) / (0.01 - ($store.app.settings.transaction_cost_percent || 0.002))).toFixed(0)"></span>
                    </div>
                  </div>
                </div>

                <!-- Scoring Parameters -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">Scoring Parameters</h3>
                  <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                    <div>
                      <span class="text-sm text-gray-300">Target Annual Return</span>
                      <p class="text-xs text-gray-300">Target CAGR for scoring</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             step="1"
                             :value="($store.app.settings.target_annual_return * 100).toFixed(0)"
                             @change="$store.app.updateSetting('target_annual_return', $event.target.value / 100)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-300 text-sm">%</span>
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Market Avg P/E</span>
                      <p class="text-xs text-gray-300">Baseline for valuation</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             step="0.1"
                             :value="$store.app.settings.market_avg_pe"
                             @change="$store.app.updateSetting('market_avg_pe', $event.target.value)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                  </div>
                </div>
              </div>

              <!-- Portfolio Tab -->
              <div x-show="activeTab === 'portfolio'" x-transition class="space-y-6">
                <!-- Portfolio Optimizer -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">Portfolio Optimizer</h3>
                  <p class="text-xs text-gray-300 mb-4">The optimizer calculates target portfolio weights using a blend of Mean-Variance and Hierarchical Risk Parity strategies.</p>
                  <div class="space-y-4">
                    <div>
                      <div class="flex items-center justify-between mb-2">
                        <span class="text-sm text-gray-300">Strategy Blend</span>
                        <span class="text-sm text-gray-300 font-mono"
                              x-text="($store.app.settings.optimizer_blend * 100).toFixed(0) + '%'"></span>
                      </div>
                      <div class="flex items-center gap-2">
                        <span class="text-xs text-gray-300">MV</span>
                        <input type="range" min="0" max="1" step="0.05"
                               :value="$store.app.settings.optimizer_blend"
                               @input="$store.app.updateSetting('optimizer_blend', parseFloat($event.target.value))"
                               class="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                        <span class="text-xs text-gray-300">HRP</span>
                      </div>
                      <p class="text-xs text-gray-300 mt-1">0% = Goal-directed (Mean-Variance), 100% = Robust (HRP)</p>
                    </div>
                    <div class="grid grid-cols-[1fr_auto] gap-x-4 items-center">
                      <div>
                        <span class="text-sm text-gray-300">Target Return</span>
                        <p class="text-xs text-gray-300">Annual return goal</p>
                      </div>
                      <div class="flex items-center gap-1">
                        <input type="number"
                               step="1"
                               :value="($store.app.settings.optimizer_target_return * 100).toFixed(0)"
                               @change="$store.app.updateSetting('optimizer_target_return', $event.target.value / 100)"
                               class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                        <span class="text-gray-300 text-sm">%</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Market Regime Detection -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">Market Regime Detection</h3>
                  <p class="text-xs text-gray-300 mb-4">Cash reserves adjust automatically based on market conditions (SPY/QQQ 200-day MA).</p>
                  <div class="space-y-3">
                    <label class="flex items-center gap-3 cursor-pointer">
                      <input type="checkbox"
                             :checked="$store.app.settings.market_regime_detection_enabled == 1"
                             @change="$store.app.updateSetting('market_regime_detection_enabled', $event.target.checked ? 1 : 0)"
                             class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                      <span class="text-sm text-gray-300">Enable regime-based cash reserves</span>
                    </label>
                    <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                      <div>
                        <span class="text-sm text-gray-300">Bull Market Reserve</span>
                        <p class="text-xs text-gray-300">Cash reserve percentage</p>
                      </div>
                      <div class="flex items-center gap-1">
                        <input type="number"
                               step="0.5"
                               min="1"
                               max="40"
                               :value="($store.app.settings.market_regime_bull_cash_reserve * 100).toFixed(1)"
                               @change="$store.app.updateSetting('market_regime_bull_cash_reserve', Math.max(0.01, Math.min(0.40, $event.target.value / 100)))"
                               class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                        <span class="text-gray-300 text-sm">%</span>
                      </div>
                      <div>
                        <span class="text-sm text-gray-300">Bear Market Reserve</span>
                        <p class="text-xs text-gray-300">Cash reserve percentage</p>
                      </div>
                      <div class="flex items-center gap-1">
                        <input type="number"
                               step="0.5"
                               min="1"
                               max="40"
                               :value="($store.app.settings.market_regime_bear_cash_reserve * 100).toFixed(1)"
                               @change="$store.app.updateSetting('market_regime_bear_cash_reserve', Math.max(0.01, Math.min(0.40, $event.target.value / 100)))"
                               class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                        <span class="text-gray-300 text-sm">%</span>
                      </div>
                      <div>
                        <span class="text-sm text-gray-300">Sideways Market Reserve</span>
                        <p class="text-xs text-gray-300">Cash reserve percentage</p>
                      </div>
                      <div class="flex items-center gap-1">
                        <input type="number"
                               step="0.5"
                               min="1"
                               max="40"
                               :value="($store.app.settings.market_regime_sideways_cash_reserve * 100).toFixed(1)"
                               @change="$store.app.updateSetting('market_regime_sideways_cash_reserve', Math.max(0.01, Math.min(0.40, $event.target.value / 100)))"
                               class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                        <span class="text-gray-300 text-sm">%</span>
                      </div>
                    </div>
                    <div class="mt-3 pt-3 border-t border-gray-700/50">
                      <p class="text-xs text-gray-300">Reserves are calculated as percentage of total portfolio value, with a minimum floor of €500.</p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Display Tab -->
              <div x-show="activeTab === 'display'" x-transition class="space-y-6">
                <!-- LED Matrix -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">LED Matrix</h3>
                  <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                    <div>
                      <span class="text-sm text-gray-300">Ticker Speed</span>
                      <p class="text-xs text-gray-300">Lower = faster scroll</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="1"
                             max="100"
                             step="1"
                             :value="$store.app.settings.ticker_speed"
                             @change="$store.app.updateSetting('ticker_speed', $event.target.value)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-300 text-sm">ms</span>
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Brightness</span>
                      <p class="text-xs text-gray-300">0-255 (default 150)</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="0"
                             max="255"
                             step="10"
                             :value="$store.app.settings.led_brightness"
                             @change="$store.app.updateSetting('led_brightness', $event.target.value)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                  </div>
                  <div class="mt-4 pt-3 border-t border-gray-700/50">
                    <span class="text-xs text-gray-300 uppercase tracking-wide">Ticker Content</span>
                    <div class="mt-2 space-y-2">
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="$store.app.settings.ticker_show_value == 1"
                               @change="$store.app.updateSetting('ticker_show_value', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Portfolio value</span>
                      </label>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="$store.app.settings.ticker_show_cash == 1"
                               @change="$store.app.updateSetting('ticker_show_cash', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Cash balance</span>
                      </label>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="$store.app.settings.ticker_show_actions == 1"
                               @change="$store.app.updateSetting('ticker_show_actions', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Next actions</span>
                      </label>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="$store.app.settings.ticker_show_amounts == 1"
                               @change="$store.app.updateSetting('ticker_show_amounts', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Show amounts</span>
                      </label>
                      <div class="flex items-center justify-between pt-2">
                        <span class="text-sm text-gray-300">Max actions</span>
                        <input type="number"
                               min="1"
                               max="10"
                               step="1"
                               :value="$store.app.settings.ticker_max_actions"
                               @change="$store.app.updateSetting('ticker_max_actions', $event.target.value)"
                               class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- System Tab -->
              <div x-show="activeTab === 'system'" x-transition class="space-y-6">
                <!-- Job Scheduling -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">Job Scheduling</h3>
                  <p class="text-xs text-gray-300 mb-4">Simplified to 4 consolidated jobs: sync cycle (trading), daily pipeline (data), and maintenance.</p>
                  <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                    <div>
                      <span class="text-sm text-gray-300">Sync Cycle</span>
                      <p class="text-xs text-gray-300">Trades, prices, recommendations, execution</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="5"
                             max="60"
                             step="5"
                             :value="$store.app.settings.job_sync_cycle_minutes"
                             @change="$store.app.updateJobSetting('job_sync_cycle_minutes', $event.target.value)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-400 text-sm">min</span>
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Maintenance</span>
                      <p class="text-xs text-gray-300">Daily backup and cleanup hour</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="0"
                             max="23"
                             step="1"
                             :value="$store.app.settings.job_maintenance_hour"
                             @change="$store.app.updateJobSetting('job_maintenance_hour', $event.target.value)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-300 text-sm">h</span>
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Auto-Deploy</span>
                      <p class="text-xs text-gray-300">Check for updates and deploy changes</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             :value="$store.app.settings.job_auto_deploy_minutes"
                             @change="$store.app.updateJobSetting('job_auto_deploy_minutes', $event.target.value)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-400 text-sm">min</span>
                    </div>
                  </div>
                  <div class="mt-4 pt-3 border-t border-gray-700/50">
                    <span class="text-xs text-gray-300 uppercase tracking-wide">Fixed Schedules</span>
                    <div class="mt-2 space-y-1 text-xs text-gray-300">
                      <p>Daily Pipeline: Hourly (per-symbol data sync)</p>
                      <p>Weekly Maintenance: Sundays (integrity checks)</p>
                    </div>
                  </div>
                </div>

                <!-- System Actions -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">System</h3>
                  <div class="space-y-3">
                    <div class="flex items-center justify-between">
                      <span class="text-sm text-gray-300">Caches</span>
                      <button @click="$store.app.resetCache()"
                              class="px-3 py-1.5 bg-gray-600 hover:bg-gray-500 text-white text-xs rounded transition-colors">
                        Reset
                      </button>
                    </div>
                    <div class="flex items-center justify-between">
                      <span class="text-sm text-gray-300">Historical Data</span>
                      <button @click="$store.app.syncHistorical()"
                              :disabled="$store.app.loading.historical"
                              class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded transition-colors disabled:opacity-50">
                        <span x-show="$store.app.loading.historical" class="inline-block animate-spin mr-1">&#9696;</span>
                        <span x-text="$store.app.loading.historical ? 'Syncing...' : 'Sync'"></span>
                      </button>
                    </div>
                    <div class="flex items-center justify-between">
                      <span class="text-sm text-gray-300">System</span>
                      <button @click="if(confirm('Reboot the system?')) API.restartSystem()"
                              class="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs rounded transition-colors">
                        Restart
                      </button>
                    </div>
                  </div>
                </div>

                <!-- API Credentials -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">API Credentials</h3>
                  <p class="text-xs text-gray-300 mb-4">Tradernet API credentials for trading and portfolio operations. Credentials are stored securely and passed with each request.</p>
                  <div class="space-y-4">
                    <div>
                      <label class="block text-sm text-gray-300 mb-1">API Key</label>
                      <input type="password"
                             :value="$store.app.settings.tradernet_api_key || ''"
                             @change="$store.app.updateSetting('tradernet_api_key', $event.target.value)"
                             placeholder="Enter API key"
                             class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500 font-mono">
                    </div>
                    <div>
                      <label class="block text-sm text-gray-300 mb-1">API Secret</label>
                      <input type="password"
                             :value="$store.app.settings.tradernet_api_secret || ''"
                             @change="$store.app.updateSetting('tradernet_api_secret', $event.target.value)"
                             placeholder="Enter API secret"
                             class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500 font-mono">
                    </div>
                    <div class="flex items-center gap-3">
                      <button @click="$store.app.testTradernetConnection()"
                              :disabled="$store.app.loading.tradernetTest"
                              class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors disabled:opacity-50">
                        <span x-show="$store.app.loading.tradernetTest" class="inline-block animate-spin mr-1">&#9696;</span>
                        <span x-text="$store.app.loading.tradernetTest ? 'Testing...' : 'Test Connection'"></span>
                      </button>
                      <div x-show="$store.app.tradernetConnectionStatus !== null" class="text-sm"
                           :class="$store.app.tradernetConnectionStatus ? 'text-green-400' : 'text-red-400'">
                        <span x-text="$store.app.tradernetConnectionStatus ? '✓ Connected' : '✗ Disconnected'"></span>
                      </div>
                    </div>
                    <div class="mt-3 pt-3 border-t border-gray-700/50">
                      <p class="text-xs text-gray-300">Credentials are automatically saved when changed. They will be used for all Tradernet API requests.</p>
                    </div>
                  </div>
                </div>

                <!-- Custom Grouping -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">Custom Grouping</h3>
                  <p class="text-xs text-gray-300 mb-4">Create custom groups for countries and industries to simplify constraints and improve optimizer performance.</p>
                  <grouping-manager></grouping-manager>
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('settings-modal', SettingsModal);
