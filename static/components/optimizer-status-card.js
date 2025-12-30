/**
 * Optimizer Status Card Component
 * Displays portfolio optimization status, settings, and recommended adjustments
 */
class OptimizerStatusCard extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-4" x-data="{ expanded: false }">
        <!-- Header -->
        <div class="flex justify-between items-center mb-3">
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-semibold text-gray-100 uppercase tracking-wide">Portfolio Optimizer</h3>
            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                  :class="$store.app.optimizerStatus?.last_run?.success ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-300'">
              <span class="w-1.5 h-1.5 rounded-full mr-1.5"
                    :class="$store.app.optimizerStatus?.last_run?.success ? 'bg-green-400' : 'bg-gray-500'"></span>
              <span x-text="$store.app.optimizerStatus?.last_run?.success ? 'Active' : 'Ready'"></span>
            </span>
          </div>
          <button @click="expanded = !expanded"
                  class="text-gray-300 hover:text-gray-100 text-xs">
            <span x-show="!expanded">Show Details</span>
            <span x-show="expanded">Hide Details</span>
          </button>
        </div>

        <!-- Results Summary Row -->
        <div class="grid grid-cols-2 gap-4 mb-3">
          <!-- Achieved Return -->
          <div class="text-center">
            <p class="text-xs text-gray-300 mb-1">Expected Return</p>
            <template x-if="$store.app.optimizerStatus?.last_run?.achieved_return_pct">
              <p class="text-lg font-mono"
                 :class="$store.app.optimizerStatus.last_run.achieved_return_pct >= ($store.app.settings?.optimizer_target_return || 0.11) * 100 ? 'text-green-400' : 'text-yellow-400'"
                 x-text="$store.app.optimizerStatus.last_run.achieved_return_pct.toFixed(1) + '%'"></p>
            </template>
            <template x-if="!$store.app.optimizerStatus?.last_run?.achieved_return_pct">
              <p class="text-lg font-mono text-gray-400">--</p>
            </template>
          </div>

          <!-- Stocks Optimized -->
          <div class="text-center">
            <p class="text-xs text-gray-300 mb-1">Stocks Optimized</p>
            <p class="text-lg font-mono text-gray-300"
               x-text="$store.app.optimizerStatus?.last_run?.total_stocks_optimized || '--'"></p>
          </div>
        </div>

        <!-- Next Action -->
        <template x-if="$store.app.optimizerStatus?.last_run?.next_action">
          <div class="bg-gray-900/50 rounded p-2 mb-3">
            <p class="text-xs text-gray-300 mb-1">Next Recommended Action</p>
            <p class="text-sm font-medium text-gray-100"
               x-text="$store.app.optimizerStatus.last_run.next_action"></p>
          </div>
        </template>

        <!-- Expandable Details -->
        <div x-show="expanded"
             x-transition:enter="transition ease-out duration-200"
             x-transition:enter-start="opacity-0"
             x-transition:enter-end="opacity-100"
             x-transition:leave="transition ease-in duration-150"
             x-transition:leave-start="opacity-100"
             x-transition:leave-end="opacity-0">
          <!-- Top Adjustments Table -->
          <template x-if="$store.app.optimizerStatus?.last_run?.top_adjustments?.length > 0">
            <div class="mt-3">
              <p class="text-xs text-gray-300 mb-2 uppercase tracking-wide">Top Weight Adjustments</p>
              <div class="space-y-1">
                <template x-for="adj in $store.app.optimizerStatus.last_run.top_adjustments" :key="adj.symbol">
                  <div class="flex items-center justify-between text-xs bg-gray-900/50 rounded px-2 py-1.5">
                    <span class="font-mono text-gray-200" x-text="adj.symbol"></span>
                    <div class="flex items-center gap-2">
                      <span class="text-gray-400" x-text="adj.current_pct.toFixed(1) + '%'"></span>
                      <span class="text-gray-400">&rarr;</span>
                      <span class="text-gray-300" x-text="adj.target_pct.toFixed(1) + '%'"></span>
                      <span class="font-medium w-16 text-right"
                            :class="adj.direction === 'buy' ? 'text-green-400' : 'text-red-400'"
                            x-text="(adj.direction === 'buy' ? '+' : '') + adj.change_pct.toFixed(1) + '%'"></span>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </template>

          <!-- Optimizer Info -->
          <div class="mt-3 pt-3 border-t border-gray-700/50">
            <div class="grid grid-cols-2 gap-4 text-xs">
              <div>
                <span class="text-gray-300">Fallback Used:</span>
                <span class="text-gray-300 ml-1"
                      x-text="$store.app.optimizerStatus?.last_run?.fallback_used || 'None'"></span>
              </div>
              <div>
                <span class="text-gray-300">Min Trade:</span>
                <span class="text-gray-300 ml-1"
                      x-text="$store.app.optimizerStatus?.settings?.min_trade_amount ? '€' + $store.app.optimizerStatus.settings.min_trade_amount : '--'"></span>
              </div>
              <div>
                <span class="text-gray-300">Cash Reserve:</span>
                <span class="text-gray-300 ml-1"
                      x-text="$store.app.optimizerStatus?.settings?.min_cash_reserve ? '€' + $store.app.optimizerStatus.settings.min_cash_reserve : '--'"></span>
              </div>
              <div>
                <span class="text-gray-300">Settings:</span>
                <span class="text-gray-300 ml-1 text-xs">
                  <button @click="$store.app.showSettingsModal = true" class="text-blue-400 hover:text-blue-300">Edit in Settings</button>
                </span>
              </div>
            </div>
          </div>

          <!-- Run Button -->
          <div class="mt-3 pt-3 border-t border-gray-700/50 flex justify-end">
            <button @click="$store.app.runOptimizer()"
                    class="px-3 py-1.5 text-xs font-medium text-blue-400 hover:text-blue-300 border border-blue-500/30 hover:border-blue-500/50 rounded transition-colors">
              Run Optimization
            </button>
          </div>
        </div>

        <!-- Collapsed State: No Data Message -->
        <template x-if="!$store.app.optimizerStatus?.last_run && !expanded">
          <p class="text-xs text-gray-300 text-center">
            No optimization results yet. Click "Show Details" to run manually.
          </p>
        </template>
      </div>
    `;
  }
}

customElements.define('optimizer-status-card', OptimizerStatusCard);
