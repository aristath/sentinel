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
      <div class="bg-gray-800 border border-gray-700 rounded p-3">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xs text-gray-400 uppercase tracking-wide">Next Actions</h2>
          <button @click="$store.app.fetchRecommendations()"
                  class="p-1 text-gray-400 hover:text-gray-200 rounded hover:bg-gray-700 transition-colors"
                  :disabled="$store.app.loading.recommendations"
                  title="Refresh recommendations">
            <span x-show="$store.app.loading.recommendations" class="inline-block animate-spin">&#9696;</span>
            <span x-show="!$store.app.loading.recommendations">&#8635;</span>
          </button>
        </div>

        <!-- Scrollable content area -->
        <div class="max-h-[400px] overflow-y-auto">

        <!-- Empty state - only shown when no recommendations -->
        <template x-if="!$store.app.loading.recommendations && (!$store.app.recommendations || !$store.app.recommendations.steps || $store.app.recommendations.steps.length === 0)">
          <div class="text-gray-500 text-sm py-4 text-center">
            <div>No recommendations pending</div>
            <div class="text-xs text-gray-600 mt-1">Portfolio is optimally balanced</div>
          </div>
        </template>

        <!-- RECOMMENDATIONS SEQUENCE -->
        <template x-if="$store.app.recommendations && $store.app.recommendations.steps && $store.app.recommendations.steps.length > 0">
          <div class="mb-3">
            <div class="text-xs text-gray-400 mb-2 flex items-center justify-between">
              <span x-text="'Optimal Sequence (' + $store.app.recommendations.steps.length + ' step' + ($store.app.recommendations.steps.length > 1 ? 's' : '') + ')'"></span>
              <div class="flex items-center gap-2">
                <span class="text-green-400" x-show="$store.app.recommendations.total_score_improvement > 0" x-text="'+' + $store.app.recommendations.total_score_improvement.toFixed(1) + ' score'"></span>
                <span class="text-red-400" x-show="$store.app.recommendations.total_score_improvement < 0" x-text="$store.app.recommendations.total_score_improvement.toFixed(1) + ' score'"></span>
                <button @click="$store.app.executeRecommendation()"
                        class="px-2 py-1 text-xs bg-green-600 hover:bg-green-700 text-white rounded"
                        :disabled="$store.app.loading.execute"
                        title="Execute first step">
                  <span x-show="$store.app.loading.execute" class="inline-block animate-spin">&#9696;</span>
                  <span x-show="!$store.app.loading.execute">Execute Step 1</span>
                </button>
              </div>
            </div>
            <div class="space-y-2">
              <template x-for="(step, index) in $store.app.recommendations.steps" :key="'step-' + step.step">
                <div class="bg-gray-900 rounded p-2 border"
                     :class="step.side === 'SELL' ? 'border-red-900/50' : 'border-green-900/50'">
                  <div class="flex items-start justify-between gap-2">
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 flex-wrap">
                        <span class="text-xs font-mono bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded" x-text="'Step ' + step.step"></span>
                        <span class="text-xs font-mono px-1.5 py-0.5 rounded"
                              :class="step.side === 'SELL' ? 'bg-red-900/50 text-red-300' : 'bg-green-900/50 text-green-300'"
                              x-text="step.side"></span>
                        <span class="font-mono font-bold"
                              :class="step.side === 'SELL' ? 'text-red-400' : 'text-green-400'"
                              x-text="step.symbol"></span>
                      </div>
                      <div class="text-sm text-gray-300 truncate mt-0.5" x-text="step.name"></div>
                      <div class="text-xs text-gray-500 mt-1" x-text="step.reason"></div>
                      <div class="text-xs text-gray-600 mt-1 flex items-center gap-3 flex-wrap">
                        <span x-text="'Score: ' + step.portfolio_score_before.toFixed(1) + ' → ' + step.portfolio_score_after.toFixed(1)"></span>
                        <span class="text-green-400" x-show="step.score_change > 0" x-text="'+' + step.score_change.toFixed(1)"></span>
                        <span class="text-red-400" x-show="step.score_change < 0" x-text="step.score_change.toFixed(1)"></span>
                      </div>
                    </div>
                    <div class="text-right flex-shrink-0 flex flex-col items-end gap-1">
                      <div class="text-sm font-mono font-bold"
                           :class="step.side === 'SELL' ? 'text-red-400' : 'text-green-400'"
                           x-text="(step.side === 'SELL' ? '-' : '+') + '€' + step.estimated_value.toLocaleString()"></div>
                      <div class="text-xs text-gray-400" x-text="step.quantity + ' @ €' + step.estimated_price"></div>
                      <div class="text-xs text-gray-500" x-text="'Cash: €' + step.available_cash_before.toLocaleString() + ' → €' + step.available_cash_after.toLocaleString()"></div>
                    </div>
                  </div>
                </div>
              </template>
            </div>
            <div class="mt-2 text-xs text-gray-500 text-center" x-show="$store.app.recommendations.final_available_cash">
              Final cash: €<span x-text="$store.app.recommendations.final_available_cash.toLocaleString()"></span>
            </div>
          </div>
        </template>

        </div><!-- End scrollable content -->
      </div>
    `;
  }
}

customElements.define('next-actions-card', NextActionsCard);
