/**
 * Settings Modal Component
 * Full-screen settings organized into cards
 *
 * Note: Score weight settings have been removed. The portfolio optimizer
 * now handles allocation decisions. Per-stock scoring uses fixed weights.
 */
class SettingsModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showSettingsModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex flex-col"
           x-transition
           @click="$store.app.showSettingsModal = false">
        <div class="w-full h-full bg-gray-900 overflow-y-auto" @click.stop>
          <!-- Sticky Header -->
          <div class="flex items-center justify-between p-4 border-b border-gray-700 sticky top-0 bg-gray-900 z-10">
            <h2 class="text-lg font-semibold text-gray-100">Settings</h2>
            <button @click="$store.app.showSettingsModal = false"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <!-- Content Grid -->
          <div class="p-4 md:p-6 lg:p-8">
            <div class="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

              <!-- Portfolio Optimizer Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Portfolio Optimizer</h3>
                <p class="text-xs text-gray-500 mb-4">The optimizer calculates target portfolio weights using a blend of Mean-Variance and Hierarchical Risk Parity strategies.</p>

                <div class="space-y-4">
                  <!-- Optimizer Blend Slider -->
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <span class="text-sm text-gray-300">Strategy Blend</span>
                      <span class="text-sm text-gray-400 font-mono"
                            x-text="($store.app.settings.optimizer_blend * 100).toFixed(0) + '%'"></span>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-xs text-gray-500">MV</span>
                      <input type="range" min="0" max="1" step="0.05"
                             :value="$store.app.settings.optimizer_blend"
                             @input="$store.app.updateSetting('optimizer_blend', parseFloat($event.target.value))"
                             class="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                      <span class="text-xs text-gray-500">HRP</span>
                    </div>
                    <p class="text-xs text-gray-500 mt-1">0% = Goal-directed (Mean-Variance), 100% = Robust (HRP)</p>
                  </div>

                  <!-- Target Return -->
                  <div class="grid grid-cols-[1fr_auto] gap-x-4 items-center">
                    <div>
                      <span class="text-sm text-gray-300">Target Return</span>
                      <p class="text-xs text-gray-500">Annual return goal</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             step="1"
                             :value="($store.app.settings.optimizer_target_return * 100).toFixed(0)"
                             @change="$store.app.updateSetting('optimizer_target_return', $event.target.value / 100)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-400 text-sm">%</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Transaction Costs Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Transaction Costs</h3>
                <p class="text-xs text-gray-500 mb-4">Freedom24 fee structure. Used to calculate minimum worthwhile trade size.</p>

                <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                  <!-- Fixed Cost -->
                  <div>
                    <span class="text-sm text-gray-300">Fixed Cost</span>
                    <p class="text-xs text-gray-500">Per trade</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <span class="text-gray-400 text-sm">EUR</span>
                    <input type="number"
                           step="0.5"
                           min="0"
                           :value="$store.app.settings.transaction_cost_fixed"
                           @change="$store.app.updateSetting('transaction_cost_fixed', $event.target.value)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  </div>

                  <!-- Variable Cost -->
                  <div>
                    <span class="text-sm text-gray-300">Variable Cost</span>
                    <p class="text-xs text-gray-500">Percentage of trade</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           step="0.01"
                           min="0"
                           :value="($store.app.settings.transaction_cost_percent * 100).toFixed(2)"
                           @change="$store.app.updateSetting('transaction_cost_percent', $event.target.value / 100)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">%</span>
                  </div>

                  <!-- Min Cash Reserve -->
                  <div>
                    <span class="text-sm text-gray-300">Min Cash Reserve</span>
                    <p class="text-xs text-gray-500">Never deploy below this</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <span class="text-gray-400 text-sm">EUR</span>
                    <input type="number"
                           step="50"
                           min="0"
                           :value="$store.app.settings.min_cash_reserve"
                           @change="$store.app.updateSetting('min_cash_reserve', $event.target.value)"
                           class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  </div>
                </div>

                <!-- Calculated min trade amount -->
                <div class="mt-4 pt-3 border-t border-gray-700/50">
                  <div class="flex items-center justify-between">
                    <span class="text-xs text-gray-500">Min worthwhile trade (1% cost):</span>
                    <span class="text-sm text-gray-300 font-mono"
                          x-text="'EUR ' + (($store.app.settings.transaction_cost_fixed || 2) / (0.01 - ($store.app.settings.transaction_cost_percent || 0.002))).toFixed(0)"></span>
                  </div>
                </div>
              </div>

              <!-- Market Regime Detection Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Market Regime Detection</h3>
                <p class="text-xs text-gray-500 mb-4">Cash reserves adjust automatically based on market conditions (SPY/QQQ 200-day MA).</p>

                <div class="space-y-3">
                  <!-- Enable/Disable -->
                  <label class="flex items-center gap-3 cursor-pointer">
                    <input type="checkbox"
                           :checked="$store.app.settings.market_regime_detection_enabled == 1"
                           @change="$store.app.updateSetting('market_regime_detection_enabled', $event.target.checked ? 1 : 0)"
                           class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                    <span class="text-sm text-gray-300">Enable regime-based cash reserves</span>
                  </label>

                  <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                    <!-- Bull Market Reserve -->
                    <div>
                      <span class="text-sm text-gray-300">Bull Market Reserve</span>
                      <p class="text-xs text-gray-500">Cash reserve percentage</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             step="0.5"
                             min="1"
                             max="40"
                             :value="($store.app.settings.market_regime_bull_cash_reserve * 100).toFixed(1)"
                             @change="$store.app.updateSetting('market_regime_bull_cash_reserve', Math.max(0.01, Math.min(0.40, $event.target.value / 100)))"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-400 text-sm">%</span>
                    </div>

                    <!-- Bear Market Reserve -->
                    <div>
                      <span class="text-sm text-gray-300">Bear Market Reserve</span>
                      <p class="text-xs text-gray-500">Cash reserve percentage</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             step="0.5"
                             min="1"
                             max="40"
                             :value="($store.app.settings.market_regime_bear_cash_reserve * 100).toFixed(1)"
                             @change="$store.app.updateSetting('market_regime_bear_cash_reserve', Math.max(0.01, Math.min(0.40, $event.target.value / 100)))"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-400 text-sm">%</span>
                    </div>

                    <!-- Sideways Market Reserve -->
                    <div>
                      <span class="text-sm text-gray-300">Sideways Market Reserve</span>
                      <p class="text-xs text-gray-500">Cash reserve percentage</p>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             step="0.5"
                             min="1"
                             max="40"
                             :value="($store.app.settings.market_regime_sideways_cash_reserve * 100).toFixed(1)"
                             @change="$store.app.updateSetting('market_regime_sideways_cash_reserve', Math.max(0.01, Math.min(0.40, $event.target.value / 100)))"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-400 text-sm">%</span>
                    </div>
                  </div>

                  <!-- Info note -->
                  <div class="mt-3 pt-3 border-t border-gray-700/50">
                    <p class="text-xs text-gray-500">Reserves are calculated as percentage of total portfolio value, with a minimum floor of €500.</p>
                  </div>
                </div>
              </div>

              <!-- Holistic Planner Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Holistic Planner</h3>
                <p class="text-xs text-gray-500 mb-4">Controls how the planner generates and evaluates action sequences. More opportunities and combinatorial generation explore more scenarios but may be slower.</p>

                <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                  <!-- Max Plan Depth -->
                  <div>
                    <span class="text-sm text-gray-300">Max Plan Depth</span>
                    <p class="text-xs text-gray-500">Maximum sequence length (1-10)</p>
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

                  <!-- Max Opportunities Per Category -->
                  <div>
                    <span class="text-sm text-gray-300">Max Opportunities/Category</span>
                    <p class="text-xs text-gray-500">How many opportunities to consider (1-20)</p>
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

                  <!-- Enable Combinatorial -->
                  <div>
                    <span class="text-sm text-gray-300">Combinatorial Generation</span>
                    <p class="text-xs text-gray-500">Explore all valid combinations</p>
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

                  <!-- Priority Threshold -->
                  <div>
                    <span class="text-sm text-gray-300">Priority Threshold</span>
                    <p class="text-xs text-gray-500">Min priority for combinations (0.0-1.0)</p>
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

                  <!-- Batch Interval -->
                  <div>
                    <span class="text-sm text-gray-300">Batch Interval</span>
                    <p class="text-xs text-gray-500">How often to process batches (1-300 seconds)</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           min="1"
                           max="300"
                           step="1"
                           :value="$store.app.settings.planner_batch_interval_seconds"
                           @change="$store.app.updateSetting('planner_batch_interval_seconds', Math.max(1, Math.min(300, parseInt($event.target.value) || 10)))"
                           class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">sec</span>
                  </div>

                  <!-- Batch Size -->
                  <div>
                    <span class="text-sm text-gray-300">Batch Size</span>
                    <p class="text-xs text-gray-500">Sequences per batch (10-1000)</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           min="10"
                           max="1000"
                           step="10"
                           :value="$store.app.settings.planner_batch_size"
                           @change="$store.app.updateSetting('planner_batch_size', Math.max(10, Math.min(1000, parseInt($event.target.value) || 100)))"
                           class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">seq</span>
                  </div>
                </div>

                <!-- Info note -->
                <div class="mt-4 pt-3 border-t border-gray-700/50">
                  <p class="text-xs text-gray-500">Higher values explore more scenarios but may be slower. Early filtering prevents performance issues. Incremental planner processes sequences continuously in batches.</p>
                </div>
              </div>

              <!-- Trading Constraints Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Trading Constraints</h3>

                <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                  <!-- Min Hold Days -->
                  <div>
                    <span class="text-sm text-gray-300">Min Hold Days</span>
                    <p class="text-xs text-gray-500">Days to hold before selling</p>
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
                    <p class="text-xs text-gray-500">Wait after selling before re-selling</p>
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
                    <p class="text-xs text-gray-500">Block sells if loss exceeds this</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           step="1"
                           :value="($store.app.settings.max_loss_threshold * 100).toFixed(0)"
                           @change="$store.app.updateSetting('max_loss_threshold', $event.target.value / 100)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">%</span>
                  </div>

                  <!-- Min Stock Score -->
                  <div>
                    <span class="text-sm text-gray-300">Min Stock Score</span>
                    <p class="text-xs text-gray-500">Minimum score to consider (0-1)</p>
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

              <!-- Scoring Parameters Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Scoring Parameters</h3>

                <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                  <!-- Target Annual Return -->
                  <div>
                    <span class="text-sm text-gray-300">Target Annual Return</span>
                    <p class="text-xs text-gray-500">Target CAGR for scoring</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           step="1"
                           :value="($store.app.settings.target_annual_return * 100).toFixed(0)"
                           @change="$store.app.updateSetting('target_annual_return', $event.target.value / 100)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">%</span>
                  </div>

                  <!-- Market Avg P/E -->
                  <div>
                    <span class="text-sm text-gray-300">Market Avg P/E</span>
                    <p class="text-xs text-gray-500">Baseline for valuation</p>
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

              <!-- LED Matrix Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">LED Matrix</h3>

                <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                  <!-- Ticker Speed -->
                  <div>
                    <span class="text-sm text-gray-300">Ticker Speed</span>
                    <p class="text-xs text-gray-500">Lower = faster scroll</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           min="1"
                           max="100"
                           step="1"
                           :value="$store.app.settings.ticker_speed"
                           @change="$store.app.updateSetting('ticker_speed', $event.target.value)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">ms</span>
                  </div>

                  <!-- LED Brightness -->
                  <div>
                    <span class="text-sm text-gray-300">Brightness</span>
                    <p class="text-xs text-gray-500">0-255 (default 150)</p>
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

                <!-- Ticker Content Options -->
                <div class="mt-4 pt-3 border-t border-gray-700/50">
                  <span class="text-xs text-gray-500 uppercase tracking-wide">Ticker Content</span>
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

              <!-- Job Scheduling Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Job Scheduling</h3>
                <p class="text-xs text-gray-500 mb-4">Simplified to 4 consolidated jobs: sync cycle (trading), daily pipeline (data), and maintenance.</p>

                <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                  <!-- Sync Cycle -->
                  <div>
                    <span class="text-sm text-gray-300">Sync Cycle</span>
                    <p class="text-xs text-gray-500">Trades, prices, recommendations, execution</p>
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

                  <!-- Maintenance Hour -->
                  <div>
                    <span class="text-sm text-gray-300">Maintenance</span>
                    <p class="text-xs text-gray-500">Daily backup and cleanup hour</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           min="0"
                           max="23"
                           step="1"
                           :value="$store.app.settings.job_maintenance_hour"
                           @change="$store.app.updateJobSetting('job_maintenance_hour', $event.target.value)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">h</span>
                  </div>
                </div>

                <!-- Fixed Jobs Info -->
                <div class="mt-4 pt-3 border-t border-gray-700/50">
                  <span class="text-xs text-gray-500 uppercase tracking-wide">Fixed Schedules</span>
                  <div class="mt-2 space-y-1 text-xs text-gray-400">
                    <p>Daily Pipeline: Hourly (per-symbol data sync)</p>
                    <p>Weekly Maintenance: Sundays (integrity checks)</p>
                  </div>
                </div>
              </div>

              <!-- System Actions Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">System</h3>

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

              <!-- Custom Grouping Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Custom Grouping</h3>
                <p class="text-xs text-gray-500 mb-4">Create custom groups for countries and industries to simplify constraints and improve optimizer performance.</p>
                <grouping-manager></grouping-manager>
              </div>

            </div>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('settings-modal', SettingsModal);
