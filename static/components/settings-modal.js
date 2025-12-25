/**
 * Settings Modal Component
 * Full-screen settings organized into cards
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

              <!-- Trading Parameters Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4">
                <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-3">Trading Parameters</h3>

                <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                  <!-- Min Trade Size -->
                  <div>
                    <span class="text-sm text-gray-300">Min Trade Size</span>
                    <p class="text-xs text-gray-500">Minimum EUR for buy orders</p>
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
                           class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">%</span>
                  </div>

                  <!-- Min Sell Value -->
                  <div>
                    <span class="text-sm text-gray-300">Min Sell Value</span>
                    <p class="text-xs text-gray-500">Minimum EUR for sell orders</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <span class="text-gray-400 text-sm">EUR</span>
                    <input type="number"
                           :value="$store.app.settings.min_sell_value"
                           @change="$store.app.updateSetting('min_sell_value', $event.target.value)"
                           class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  </div>

                  <!-- Recommendation Depth -->
                  <div>
                    <span class="text-sm text-gray-300">Recommendation Depth</span>
                    <p class="text-xs text-gray-500">Steps in multi-step plans (1-5)</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           min="1"
                           max="5"
                           step="1"
                           :value="$store.app.settings.recommendation_depth"
                           @change="$store.app.updateSetting('recommendation_depth', $event.target.value)"
                           class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">steps</span>
                  </div>

                  <!-- Min Stock Score -->
                  <div>
                    <span class="text-sm text-gray-300">Min Stock Score</span>
                    <p class="text-xs text-gray-500">Minimum score to consider buying (0-1)</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           min="0"
                           max="1"
                           step="0.05"
                           :value="$store.app.settings.min_stock_score"
                           @change="$store.app.updateSetting('min_stock_score', $event.target.value)"
                           class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
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
                           class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
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
                           class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  </div>
                </div>
              </div>

              <!-- Buy Score Weights Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4"
                   x-data="{
                     buyGroups: [
                       { key: 'long_term', label: 'Long-term', desc: 'CAGR, Sortino, Sharpe' },
                       { key: 'fundamentals', label: 'Fundamentals', desc: 'Financial strength' },
                       { key: 'opportunity', label: 'Opportunity', desc: '52W high, P/E ratio' },
                       { key: 'dividends', label: 'Dividends', desc: 'Yield, consistency' },
                       { key: 'short_term', label: 'Short-term', desc: 'Momentum, drawdown' },
                       { key: 'technicals', label: 'Technicals', desc: 'RSI, Bollinger, EMA' },
                       { key: 'opinion', label: 'Opinion', desc: 'Analyst recs, targets' },
                       { key: 'diversification', label: 'Diversification', desc: 'Geography, industry' }
                     ],
                     get buySum() {
                       return this.buyGroups.reduce((sum, g) =>
                         sum + ($store.app.settings['score_weight_' + g.key] || 0), 0);
                     },
                     buyPct(key) {
                       const raw = $store.app.settings['score_weight_' + key] || 0;
                       const sum = this.buySum;
                       return sum > 0 ? ((raw / sum) * 100).toFixed(0) : '0';
                     }
                   }">
                <div class="flex items-center justify-between mb-3">
                  <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide">Buy Score Weights</h3>
                  <span class="text-xs text-gray-500 font-mono">Sum: <span x-text="buySum.toFixed(2)"></span></span>
                </div>
                <p class="text-xs text-gray-500 mb-3">Adjust importance of each factor for buy decisions.</p>

                <div class="space-y-2">
                  <template x-for="group in buyGroups" :key="group.key">
                    <div class="grid grid-cols-[1fr_80px_40px] gap-2 items-center">
                      <div>
                        <span class="text-sm text-gray-300" x-text="group.label"></span>
                        <p class="text-xs text-gray-500" x-text="group.desc"></p>
                      </div>
                      <input type="range" min="0" max="1" step="0.01"
                             :value="$store.app.settings['score_weight_' + group.key]"
                             @input="$store.app.updateSetting('score_weight_' + group.key, parseFloat($event.target.value))"
                             class="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-green-500">
                      <span class="text-sm text-gray-400 font-mono text-right"
                            x-text="buyPct(group.key) + '%'"></span>
                    </div>
                  </template>
                </div>
              </div>

              <!-- Sell Score Weights Card -->
              <div class="bg-gray-800 border border-gray-700 rounded p-4"
                   x-data="{
                     sellGroups: [
                       { key: 'underperformance', label: 'Underperformance', desc: 'Return vs target' },
                       { key: 'time_held', label: 'Time Held', desc: 'Position age' },
                       { key: 'portfolio_balance', label: 'Portfolio Balance', desc: 'Overweight detection' },
                       { key: 'instability', label: 'Instability', desc: 'Bubble/volatility' },
                       { key: 'drawdown', label: 'Drawdown', desc: 'Current drawdown' }
                     ],
                     get sellSum() {
                       return this.sellGroups.reduce((sum, g) =>
                         sum + ($store.app.settings['sell_weight_' + g.key] || 0), 0);
                     },
                     sellPct(key) {
                       const raw = $store.app.settings['sell_weight_' + key] || 0;
                       const sum = this.sellSum;
                       return sum > 0 ? ((raw / sum) * 100).toFixed(0) : '0';
                     }
                   }">
                <div class="flex items-center justify-between mb-3">
                  <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide">Sell Score Weights</h3>
                  <span class="text-xs text-gray-500 font-mono">Sum: <span x-text="sellSum.toFixed(2)"></span></span>
                </div>
                <p class="text-xs text-gray-500 mb-3">Adjust importance of each factor for sell decisions.</p>

                <div class="space-y-2">
                  <template x-for="group in sellGroups" :key="group.key">
                    <div class="grid grid-cols-[1fr_80px_40px] gap-2 items-center">
                      <div>
                        <span class="text-sm text-gray-300" x-text="group.label"></span>
                        <p class="text-xs text-gray-500" x-text="group.desc"></p>
                      </div>
                      <input type="range" min="0" max="1" step="0.01"
                             :value="$store.app.settings['sell_weight_' + group.key]"
                             @input="$store.app.updateSetting('sell_weight_' + group.key, parseFloat($event.target.value))"
                             class="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-red-500">
                      <span class="text-sm text-gray-400 font-mono text-right"
                            x-text="sellPct(group.key) + '%'"></span>
                    </div>
                  </template>
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
                           class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
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
                           class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
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

                <div class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                  <!-- Portfolio Sync -->
                  <div>
                    <span class="text-sm text-gray-300">Portfolio Sync</span>
                    <p class="text-xs text-gray-500">Fetch positions</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           min="1"
                           max="60"
                           step="1"
                           :value="$store.app.settings.job_portfolio_sync_minutes"
                           @change="$store.app.updateJobSetting('job_portfolio_sync_minutes', $event.target.value)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">min</span>
                  </div>

                  <!-- Trade Sync -->
                  <div>
                    <span class="text-sm text-gray-300">Trade Sync</span>
                    <p class="text-xs text-gray-500">Sync executed trades</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           min="1"
                           max="60"
                           step="1"
                           :value="$store.app.settings.job_trade_sync_minutes"
                           @change="$store.app.updateJobSetting('job_trade_sync_minutes', $event.target.value)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">min</span>
                  </div>

                  <!-- Price Sync -->
                  <div>
                    <span class="text-sm text-gray-300">Price Sync</span>
                    <p class="text-xs text-gray-500">Fetch current prices</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           min="1"
                           max="60"
                           step="1"
                           :value="$store.app.settings.job_price_sync_minutes"
                           @change="$store.app.updateJobSetting('job_price_sync_minutes', $event.target.value)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">min</span>
                  </div>

                  <!-- Score Refresh -->
                  <div>
                    <span class="text-sm text-gray-300">Score Refresh</span>
                    <p class="text-xs text-gray-500">Recalculate scores</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           min="1"
                           max="60"
                           step="1"
                           :value="$store.app.settings.job_score_refresh_minutes"
                           @change="$store.app.updateJobSetting('job_score_refresh_minutes', $event.target.value)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">min</span>
                  </div>

                  <!-- Rebalance Check -->
                  <div>
                    <span class="text-sm text-gray-300">Rebalance Check</span>
                    <p class="text-xs text-gray-500">Check opportunities</p>
                  </div>
                  <div class="flex items-center gap-1">
                    <input type="number"
                           min="1"
                           max="60"
                           step="1"
                           :value="$store.app.settings.job_rebalance_check_minutes"
                           @change="$store.app.updateJobSetting('job_rebalance_check_minutes', $event.target.value)"
                           class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                    <span class="text-gray-400 text-sm">min</span>
                  </div>
                </div>

                <!-- Daily Jobs -->
                <div class="mt-4 pt-3 border-t border-gray-700/50">
                  <span class="text-xs text-gray-500 uppercase tracking-wide">Daily Jobs (Hour 0-23)</span>
                  <div class="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 items-start">
                    <!-- Cash Flow Sync -->
                    <div>
                      <span class="text-sm text-gray-300">Cash Flow Sync</span>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="0"
                             max="23"
                             step="1"
                             :value="$store.app.settings.job_cash_flow_sync_hour"
                             @change="$store.app.updateJobSetting('job_cash_flow_sync_hour', $event.target.value)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-400 text-sm">h</span>
                    </div>

                    <!-- Historical Sync -->
                    <div>
                      <span class="text-sm text-gray-300">Historical Sync</span>
                    </div>
                    <div class="flex items-center gap-1">
                      <input type="number"
                             min="0"
                             max="23"
                             step="1"
                             :value="$store.app.settings.job_historical_sync_hour"
                             @change="$store.app.updateJobSetting('job_historical_sync_hour', $event.target.value)"
                             class="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-right font-mono text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                      <span class="text-gray-400 text-sm">h</span>
                    </div>

                    <!-- Maintenance -->
                    <div>
                      <span class="text-sm text-gray-300">Maintenance</span>
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

            </div>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('settings-modal', SettingsModal);
