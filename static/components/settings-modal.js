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
              <button @click="activeTab = 'planning'"
                      :class="activeTab === 'planning' ? 'border-b-2 border-blue-500 text-blue-400' : 'text-gray-300 hover:text-gray-100'"
                      class="px-4 py-2 text-sm font-medium transition-colors">
                Planning
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
                <!-- Trading Constraints -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">Trading Constraints</h3>
                  <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                    <div>
                      <span class="text-sm text-gray-300">Min Hold Days</span>
                      <p class="text-xs text-gray-300">Days to hold before selling</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             :value="$store.app.settings.min_hold_days"
                             @change="$store.app.updateSetting('min_hold_days', $event.target.value)"
                             class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-300 text-sm">days</span>
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Sell Cooldown</span>
                      <p class="text-xs text-gray-300">Wait after selling before re-selling</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             :value="$store.app.settings.sell_cooldown_days"
                             @change="$store.app.updateSetting('sell_cooldown_days', $event.target.value)"
                             class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-300 text-sm">days</span>
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Max Loss Threshold</span>
                      <p class="text-xs text-gray-300">Block sells if loss exceeds this</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             step="1"
                             :value="($store.app.settings.max_loss_threshold * 100).toFixed(0)"
                             @change="$store.app.updateSetting('max_loss_threshold', $event.target.value / 100)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-300 text-sm">%</span>
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Min Security Score</span>
                      <p class="text-xs text-gray-300">Minimum score to consider (0-1)</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="0"
                             max="1"
                             step="0.05"
                             :value="$store.app.settings.min_stock_score"
                             @change="$store.app.updateSetting('min_stock_score', $event.target.value)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                  </div>
                </div>

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

              <!-- Planning Tab -->
              <div x-show="activeTab === 'planning'" x-transition class="space-y-6">
                <!-- Holistic Planner -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">Holistic Planner</h3>
                  <p class="text-xs text-gray-300 mb-4">Controls how the planner generates and evaluates action sequences. More opportunities and combinatorial generation explore more scenarios but may be slower.</p>
                  <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                    <div>
                      <span class="text-sm text-gray-300">Max Plan Depth</span>
                      <p class="text-xs text-gray-300">Maximum sequence length (1-10)</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="1"
                             max="10"
                             step="1"
                             :value="$store.app.settings.max_plan_depth"
                             @change="$store.app.updateSetting('max_plan_depth', Math.max(1, Math.min(10, parseInt($event.target.value) || 5)))"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Max Opportunities/Category</span>
                      <p class="text-xs text-gray-300">How many opportunities to consider (1-20)</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="1"
                             max="20"
                             step="1"
                             :value="$store.app.settings.max_opportunities_per_category"
                             @change="$store.app.updateSetting('max_opportunities_per_category', Math.max(1, Math.min(20, parseInt($event.target.value) || 5)))"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Combinatorial Generation</span>
                      <p class="text-xs text-gray-300">Explore all valid combinations</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="$store.app.settings.enable_combinatorial_generation == 1"
                               @change="$store.app.updateSetting('enable_combinatorial_generation', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300" x-text="$store.app.settings.enable_combinatorial_generation == 1 ? 'Enabled' : 'Disabled'"></span>
                      </label>
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Priority Threshold</span>
                      <p class="text-xs text-gray-300">Min priority for combinations (0.0-1.0)</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="0"
                             max="1"
                             step="0.05"
                             :value="$store.app.settings.priority_threshold_for_combinations"
                             @change="$store.app.updateSetting('priority_threshold_for_combinations', Math.max(0, Math.min(1, parseFloat($event.target.value) || 0.3)))"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                  </div>
                  <div class="mt-4 pt-3 border-t border-gray-700/50">
                    <p class="text-xs text-gray-300">Higher values explore more scenarios but may be slower. Early filtering prevents performance issues.</p>
                  </div>
                </div>

                <!-- Incremental Planner -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">Incremental Planner</h3>
                  <p class="text-xs text-gray-300 mb-4">Processes sequences continuously in batches, exploring thousands of scenarios over time. When enabled, the planner runs every N seconds and accumulates results in the database.</p>
                  <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                    <div>
                      <span class="text-sm text-gray-300">Incremental Mode</span>
                      <p class="text-xs text-gray-300">Enable continuous batch processing</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="$store.app.settings.incremental_planner_enabled == 1"
                               @change="$store.app.updateSetting('incremental_planner_enabled', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300" x-text="$store.app.settings.incremental_planner_enabled == 1 ? 'Enabled' : 'Disabled'"></span>
                      </label>
                    </div>
                  </div>
                </div>

                <!-- Combinatorial Generation -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide mb-3">Combinatorial Generation</h3>
                  <p class="text-xs text-gray-300 mb-4">Controls how many combinatorial sequences are generated. Higher values explore more scenarios but require more computation time.</p>
                  <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                    <div>
                      <span class="text-sm text-gray-300">Max Combinations Per Depth</span>
                      <p class="text-xs text-gray-300">Sequences per depth level (10-500)</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="10"
                             max="500"
                             step="10"
                             :value="$store.app.settings.combinatorial_max_combinations_per_depth || 50"
                             @change="$store.app.updateSetting('combinatorial_max_combinations_per_depth', Math.max(10, Math.min(500, parseInt($event.target.value) || 50)))"
                             class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Max Sells in Combinations</span>
                      <p class="text-xs text-gray-300">Maximum sells per sequence (1-10)</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="1"
                             max="10"
                             step="1"
                             :value="$store.app.settings.combinatorial_max_sells || 4"
                             @change="$store.app.updateSetting('combinatorial_max_sells', Math.max(1, Math.min(10, parseInt($event.target.value) || 4)))"
                             class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Max Buys in Combinations</span>
                      <p class="text-xs text-gray-300">Maximum buys per sequence (1-10)</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="1"
                             max="10"
                             step="1"
                             :value="$store.app.settings.combinatorial_max_buys || 4"
                             @change="$store.app.updateSetting('combinatorial_max_buys', Math.max(1, Math.min(10, parseInt($event.target.value) || 4)))"
                             class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                      <span class="text-sm text-gray-300">Max Candidates</span>
                      <p class="text-xs text-gray-300">Candidates considered for combinations (5-30)</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="5"
                             max="30"
                             step="1"
                             :value="$store.app.settings.combinatorial_max_candidates || 12"
                             @change="$store.app.updateSetting('combinatorial_max_candidates', Math.max(5, Math.min(30, parseInt($event.target.value) || 12)))"
                             class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    </div>
                  </div>
                  <div class="mt-4 pt-3 border-t border-gray-700/50">
                    <button
                      type="button"
                      @click="if (confirm('This will delete existing sequences and regenerate them with current settings. Existing evaluations will be preserved. Continue?')) { $store.app.regenerateSequences() }"
                      :disabled="$store.app.settings.incremental_planner_enabled != 1"
                      class="w-full px-4 py-2 bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed text-white text-sm font-medium rounded transition-colors"
                      x-text="$store.app.settings.incremental_planner_enabled != 1 ? 'Enable Incremental Planner First' : 'Regenerate Sequences'">
                    </button>
                    <p class="text-xs text-gray-300 mt-2">Deletes sequences and regenerates with current combinatorial settings. Existing evaluations are preserved and reused.</p>
                  </div>
                </div>

                <!-- Enhanced Scenario Exploration (Advanced - Collapsed) -->
                <div class="bg-gray-800 border border-gray-700 rounded p-4">
                  <div class="flex items-center justify-between mb-3">
                    <h3 class="text-sm font-medium text-gray-300 uppercase tracking-wide">Enhanced Scenario Exploration</h3>
                    <button @click="showAdvanced = !showAdvanced"
                            class="text-xs text-blue-400 hover:text-blue-300">
                      <span x-text="showAdvanced ? 'Hide Advanced' : 'Show Advanced'"></span>
                    </button>
                  </div>
                  <p class="text-xs text-gray-300 mb-4">Advanced techniques for exploring more diverse and optimal trade sequences. Beam search maintains multiple candidates, diverse selection ensures variety, and multi-objective optimization balances multiple goals.</p>

                  <div x-show="showAdvanced" x-transition class="space-y-4">
                    <div>
                      <div class="flex items-center justify-between mb-2">
                        <span class="text-sm text-gray-300">Beam Width</span>
                        <span class="text-sm text-gray-300 font-mono"
                              x-text="($store.app.settings.beam_width || 10)"></span>
                      </div>
                      <input type="range" min="1" max="50" step="1"
                             :value="$store.app.settings.beam_width || 10"
                             @input="$store.app.updateSetting('beam_width', parseInt($event.target.value) || 10)"
                             class="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                      <p class="text-xs text-gray-300 mt-1">Number of top sequences to maintain during evaluation (1-50)</p>
                    </div>

                    <div>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="($store.app.settings.enable_diverse_selection || 1) == 1"
                               @change="$store.app.updateSetting('enable_diverse_selection', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Enable Diverse Selection</span>
                      </label>
                      <p class="text-xs text-gray-300 mt-1 ml-7">Select opportunities from different countries/industries to ensure diversification</p>
                    </div>

                    <div x-show="($store.app.settings.enable_diverse_selection || 1) == 1">
                      <div class="flex items-center justify-between mb-2">
                        <span class="text-sm text-gray-300">Diversity Weight</span>
                        <span class="text-sm text-gray-300 font-mono"
                              x-text="(($store.app.settings.diversity_weight || 0.3) * 100).toFixed(0) + '%'"></span>
                      </div>
                      <div class="flex items-center gap-2">
                        <span class="text-xs text-gray-300">Priority</span>
                        <input type="range" min="0" max="1" step="0.05"
                               :value="$store.app.settings.diversity_weight || 0.3"
                               @input="$store.app.updateSetting('diversity_weight', parseFloat($event.target.value) || 0.3)"
                               class="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                        <span class="text-xs text-gray-300">Diversity</span>
                      </div>
                      <p class="text-xs text-gray-300 mt-1">Balance between priority and diversity (0% = pure priority, 100% = pure diversity)</p>
                    </div>

                    <div>
                      <div class="flex items-center justify-between mb-2">
                        <span class="text-sm text-gray-300">Cost Penalty Factor</span>
                        <span class="text-sm text-gray-300 font-mono"
                              x-text="(($store.app.settings.cost_penalty_factor || 0.1) * 100).toFixed(0) + '%'"></span>
                      </div>
                      <input type="range" min="0" max="1" step="0.05"
                             :value="$store.app.settings.cost_penalty_factor || 0.1"
                             @input="$store.app.updateSetting('cost_penalty_factor', parseFloat($event.target.value) || 0.1)"
                             class="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                      <p class="text-xs text-gray-300 mt-1">Penalty applied to sequences with high transaction costs (0% = ignore costs, 100% = maximum penalty)</p>
                    </div>

                    <div>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="($store.app.settings.enable_multi_objective || 0) == 1"
                               @change="$store.app.updateSetting('enable_multi_objective', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Enable Multi-Objective Optimization</span>
                      </label>
                      <p class="text-xs text-gray-300 mt-1 ml-7">Use Pareto frontier to balance score, diversification, risk, and cost simultaneously</p>
                    </div>

                    <div>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="($store.app.settings.enable_stochastic_scenarios || 0) == 1"
                               @change="$store.app.updateSetting('enable_stochastic_scenarios', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Enable Stochastic Price Scenarios</span>
                      </label>
                      <p class="text-xs text-gray-300 mt-1 ml-7">Evaluate sequences under price variations (±10%, ±5%) to account for uncertainty. Uses conservative scoring (60% worst-case, 40% average).</p>
                    </div>

                    <div>
                      <div class="flex items-center justify-between mb-2">
                        <span class="text-sm text-gray-300">Risk Profile</span>
                        <span class="text-sm text-gray-300 font-mono capitalize"
                              x-text="$store.app.settings.risk_profile || 'balanced'"></span>
                      </div>
                      <select :value="$store.app.settings.risk_profile || 'balanced'"
                              @change="$store.app.updateSetting('risk_profile', $event.target.value)"
                              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                        <option value="conservative">Conservative (Stability & Diversification)</option>
                        <option value="balanced">Balanced (Default)</option>
                        <option value="aggressive">Aggressive (Return & Promise)</option>
                      </select>
                      <p class="text-xs text-gray-300 mt-1">Adjusts scoring weights: Conservative emphasizes stability, Aggressive emphasizes returns</p>
                    </div>

                    <div>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="($store.app.settings.enable_market_regime_scenarios || 0) == 1"
                               @change="$store.app.updateSetting('enable_market_regime_scenarios', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Enable Market Regime Scenarios</span>
                      </label>
                      <p class="text-xs text-gray-300 mt-1 ml-7">Generate patterns based on market conditions (bull/bear/sideways). Bull: growth focus, Bear: defensive, Sideways: balanced.</p>
                    </div>

                    <div>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="($store.app.settings.enable_correlation_aware || 0) == 1"
                               @change="$store.app.updateSetting('enable_correlation_aware', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Enable Correlation-Aware Filtering</span>
                      </label>
                      <p class="text-xs text-gray-300 mt-1 ml-7">Filter out sequences that would create highly correlated positions (correlation > 0.7) to improve diversification.</p>
                    </div>

                    <div>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="($store.app.settings.enable_partial_execution || 0) == 1"
                               @change="$store.app.updateSetting('enable_partial_execution', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Enable Partial Execution Scenarios</span>
                      </label>
                      <p class="text-xs text-gray-300 mt-1 ml-7">Generate variants of sequences with only first N actions (1, 2, 3...) to evaluate interrupted or partially feasible sequences.</p>
                    </div>

                    <div>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="($store.app.settings.enable_constraint_relaxation || 0) == 1"
                               @change="$store.app.updateSetting('enable_constraint_relaxation', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Enable Constraint Relaxation</span>
                      </label>
                      <p class="text-xs text-gray-300 mt-1 ml-7">Generate variants with relaxed cash/position limits (10-30% over budget, 1.5x position size) to explore better solutions.</p>
                    </div>

                    <div>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="($store.app.settings.enable_monte_carlo_paths || 0) == 1"
                               @change="$store.app.updateSetting('enable_monte_carlo_paths', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Enable Monte Carlo Price Paths</span>
                      </label>
                      <p class="text-xs text-gray-300 mt-1 ml-7">Evaluate sequences under 100+ random price paths using historical volatility (geometric Brownian motion). More robust than fixed scenarios.</p>
                    </div>

                    <div x-show="($store.app.settings.enable_monte_carlo_paths || 0) == 1">
                      <div class="flex items-center justify-between mb-2">
                        <span class="text-sm text-gray-300">Monte Carlo Path Count</span>
                        <span class="text-sm text-gray-300 font-mono"
                              x-text="$store.app.settings.monte_carlo_path_count || 100"></span>
                      </div>
                      <input type="range"
                             :value="$store.app.settings.monte_carlo_path_count || 100"
                             @input="$store.app.updateSetting('monte_carlo_path_count', parseInt($event.target.value))"
                             min="10" max="500" step="10"
                             class="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                      <div class="flex justify-between text-xs text-gray-300 mt-1">
                        <span>10</span>
                        <span>500</span>
                      </div>
                      <p class="text-xs text-gray-300 mt-1">Number of random price paths to simulate. More paths = more robust but slower.</p>
                    </div>

                    <div>
                      <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox"
                               :checked="($store.app.settings.enable_multi_timeframe || 0) == 1"
                               @change="$store.app.updateSetting('enable_multi_timeframe', $event.target.checked ? 1 : 0)"
                               class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                        <span class="text-sm text-gray-300">Enable Multi-Timeframe Optimization</span>
                      </label>
                      <p class="text-xs text-gray-300 mt-1 ml-7">Optimize sequences for multiple timeframes simultaneously: short-term (1y, 20%), medium-term (3y, 30%), long-term (5y, 50%).</p>
                    </div>
                  </div>

                  <div class="mt-4 pt-3 border-t border-gray-700/50">
                    <p class="text-xs text-gray-300">These features explore more scenarios to find optimal sequences. Higher beam width and enabled features may increase computation time.</p>
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
