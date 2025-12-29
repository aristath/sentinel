/**
 * Next Actions Card Component
 * Shows upcoming automated trades with priority:
 * 1. Strategic planners (all strategies)
 * 2. Multi-step (must start with SELL)
 * 3. Normal recommendations
 */
class NextActionsCard extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border-2 border-blue-500/30 rounded-lg p-6 shadow-lg">
        <div class="flex items-center justify-between mb-4">
          <div class="flex-1">
            <h2 class="text-lg font-bold text-blue-400 uppercase tracking-wide mb-1">Next Actions</h2>
            <p class="text-xs text-gray-500">Automated portfolio management recommendations</p>
          </div>
          <!-- Quick Metrics Summary -->
          <div class="hidden md:flex items-center gap-4 mr-4 text-xs">
            <div class="text-right">
              <div class="text-gray-500">Total Value</div>
              <div class="text-green-400 font-mono font-semibold" x-text="formatCurrency($store.app.allocation.total_value)"></div>
            </div>
            <div class="w-px h-8 bg-gray-700"></div>
            <div class="text-right">
              <div class="text-gray-500">Cash</div>
              <div class="text-gray-300 font-mono font-semibold" x-text="formatCurrency($store.app.allocation.cash_balance)"></div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button @click="$store.app.fetchRecommendations()"
                    class="p-2 text-gray-400 hover:text-gray-200 rounded hover:bg-gray-700 transition-colors"
                    :disabled="$store.app.loading.recommendations"
                    title="Refresh recommendations">
              <span x-show="$store.app.loading.recommendations" class="inline-block animate-spin">&#9696;</span>
              <span x-show="!$store.app.loading.recommendations">&#8635;</span>
            </button>
            <button @click="if (confirm('This will delete existing sequences and regenerate them with current settings. Existing evaluations will be preserved. Continue?')) { $store.app.regenerateSequences() }"
                    class="p-2 text-gray-400 hover:text-gray-200 rounded hover:bg-gray-700 transition-colors"
                    :disabled="$store.app.settings.incremental_planner_enabled != 1"
                    x-show="$store.app.settings.incremental_planner_enabled == 1"
                    title="Regenerate sequences">
              <span>&#8634;</span>
            </button>
          </div>
        </div>

        <!-- Content area -->
        <div>

        <!-- Empty state - only shown when no recommendations -->
        <template x-if="!$store.app.loading.recommendations && (!$store.app.recommendations || !$store.app.recommendations.steps || $store.app.recommendations.steps.length === 0)">
          <div class="text-gray-400 text-base py-8 text-center">
            <div class="text-lg font-semibold mb-2">No recommendations pending</div>
            <div class="text-sm text-gray-500">Portfolio is optimally balanced</div>
          </div>
        </template>

        <!-- RECOMMENDATIONS SEQUENCE -->
        <template x-if="$store.app.recommendations && $store.app.recommendations.steps && $store.app.recommendations.steps.length > 0">
          <div class="mb-3">
            <!-- Evaluation count -->
            <div class="text-sm text-gray-400 mb-2" x-show="$store.app.recommendations.evaluated_count !== undefined">
              <span x-text="'Scenarios evaluated: ' + ($store.app.recommendations.evaluated_count || 0).toLocaleString()"></span>
            </div>
            <div class="text-sm text-gray-300 mb-4 flex items-center justify-between">
              <div class="flex items-center gap-3">
                <span class="font-semibold" x-text="'Optimal Sequence (' + $store.app.recommendations.steps.length + ' step' + ($store.app.recommendations.steps.length > 1 ? 's' : '') + ')'"></span>
                <span class="text-green-400 font-medium" x-show="$store.app.recommendations.total_score_improvement > 0" x-text="'+' + $store.app.recommendations.total_score_improvement.toFixed(1) + ' score'"></span>
                <span class="text-red-400 font-medium" x-show="$store.app.recommendations.total_score_improvement < 0" x-text="$store.app.recommendations.total_score_improvement.toFixed(1) + ' score'"></span>
              </div>
              <div class="text-xs text-gray-500 italic">
                Trades execute automatically every <span x-text="Math.round($store.app.settings.job_sync_cycle_minutes || 15)"></span> minutes
              </div>
            </div>
            <div class="space-y-3">
              <template x-for="(step, index) in $store.app.recommendations.steps" :key="'step-' + step.step">
                <div class="bg-gray-900 rounded-lg p-4 border-2 transition-all hover:shadow-md"
                     :class="step.side === 'SELL' ? 'border-red-900/50 hover:border-red-700/50' : 'border-green-900/50 hover:border-green-700/50'">
                  <div class="flex items-start justify-between gap-4">
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 flex-wrap mb-2">
                        <span class="text-sm font-mono bg-gray-700 text-gray-300 px-2 py-1 rounded" x-text="'Step ' + step.step"></span>
                        <span class="text-sm font-mono px-2 py-1 rounded font-semibold"
                              :class="step.side === 'SELL' ? 'bg-red-900/50 text-red-300' : 'bg-green-900/50 text-green-300'"
                              x-text="step.side"></span>
                        <span class="text-lg font-mono font-bold"
                              :class="step.side === 'SELL' ? 'text-red-400' : 'text-green-400'"
                              x-text="step.symbol"></span>
                      </div>
                      <div class="text-base text-gray-200 font-medium mb-1" x-text="step.name"></div>
                      <div class="text-sm text-gray-400 mb-2" x-text="step.reason"></div>
                      <div class="text-sm text-gray-500 flex items-center gap-4 flex-wrap">
                        <span x-text="'Score: ' + step.portfolio_score_before.toFixed(1) + ' → ' + step.portfolio_score_after.toFixed(1)"></span>
                        <span class="text-green-400 font-medium" x-show="step.score_change > 0" x-text="'+' + step.score_change.toFixed(1)"></span>
                        <span class="text-red-400 font-medium" x-show="step.score_change < 0" x-text="step.score_change.toFixed(1)"></span>
                      </div>
                    </div>
                    <div class="text-right flex-shrink-0 flex flex-col items-end gap-2">
                      <div class="text-lg font-mono font-bold"
                           :class="step.side === 'SELL' ? 'text-red-400' : 'text-green-400'"
                           x-text="(step.side === 'SELL' ? '-' : '+') + '€' + step.estimated_value.toLocaleString()"></div>
                      <div class="text-sm text-gray-400" x-text="step.quantity + ' @ €' + step.estimated_price"></div>
                      <div class="text-xs text-gray-500" x-text="'Cash: €' + step.available_cash_before.toLocaleString() + ' → €' + step.available_cash_after.toLocaleString()"></div>
                    </div>
                  </div>
                </div>
              </template>
            </div>
            <div class="mt-4 text-sm text-gray-400 text-center" x-show="$store.app.recommendations.final_available_cash">
              Final cash: <span class="font-semibold text-gray-300" x-text="'€' + $store.app.recommendations.final_available_cash.toLocaleString()"></span>
            </div>
          </div>
        </template>

        </div><!-- End scrollable content -->
      </div>
    `;
  }
}

customElements.define('next-actions-card', NextActionsCard);
