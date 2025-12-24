/**
 * Next Actions Card Component
 * Shows upcoming automated trades - sells first, then buys
 */
class NextActionsCard extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3" x-data>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xs text-gray-400 uppercase tracking-wide">Next Actions</h2>
          <button @click="$store.app.fetchRecommendations(); $store.app.fetchSellRecommendations(); $store.app.fetchMultiStepRecommendations()"
                  class="p-1 text-gray-400 hover:text-gray-200 rounded hover:bg-gray-700 transition-colors"
                  :disabled="$store.app.loading.recommendations || $store.app.loading.sellRecommendations || $store.app.loading.multiStepRecommendations"
                  title="Refresh">
            <span x-show="$store.app.loading.recommendations || $store.app.loading.sellRecommendations || $store.app.loading.multiStepRecommendations" class="inline-block animate-spin">&#9696;</span>
            <span x-show="!$store.app.loading.recommendations && !$store.app.loading.sellRecommendations && !$store.app.loading.multiStepRecommendations">&#8635;</span>
          </button>
        </div>

        <!-- Scrollable content area -->
        <div class="max-h-[300px] overflow-y-auto">

        <!-- Empty state -->
        <template x-if="!$store.app.loading.recommendations && !$store.app.loading.sellRecommendations && !$store.app.loading.multiStepRecommendations && !$store.app.multiStepRecommendations && $store.app.recommendations.length === 0 && $store.app.sellRecommendations.length === 0">
          <div class="text-gray-500 text-sm py-4 text-center">No pending actions</div>
        </template>

        <!-- MULTI-STEP RECOMMENDATIONS SECTION -->
        <template x-if="$store.app.multiStepRecommendations && $store.app.multiStepRecommendations.steps && $store.app.multiStepRecommendations.steps.length > 0">
          <div class="mb-3">
            <div class="text-xs text-gray-400 mb-2 flex items-center justify-between">
              <span x-text="'Multi-Step Plan (' + $store.app.multiStepRecommendations.depth + ' steps)'"></span>
              <div class="flex items-center gap-2">
                <span class="text-green-400" x-text="'↑' + $store.app.multiStepRecommendations.total_score_improvement.toFixed(1) + ' score'"></span>
                <button
                  @click="$store.app.executeAllMultiStep()"
                  :disabled="$store.app.loading.execute"
                  class="text-xs px-2 py-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded"
                  title="Execute all steps in sequence">
                  Execute All
                </button>
              </div>
            </div>
            <div class="space-y-2">
              <template x-for="(step, index) in $store.app.multiStepRecommendations.steps" :key="'step-' + step.step">
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
                      <button
                        @click="$store.app.executeMultiStepStep(step.step)"
                        :disabled="$store.app.loading.execute || $store.app.executingStep === step.step"
                        class="text-xs px-2 py-0.5 mt-1 rounded"
                        :class="step.side === 'SELL' 
                          ? 'bg-red-600 hover:bg-red-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white' 
                          : 'bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white'"
                        :title="'Execute step ' + step.step">
                        <span x-show="!$store.app.loading.execute || $store.app.executingStep !== step.step">Execute</span>
                        <span x-show="$store.app.loading.execute && $store.app.executingStep === step.step">...</span>
                      </button>
                    </div>
                  </div>
                </div>
              </template>
            </div>
            <div class="mt-2 text-xs text-gray-500 text-center" x-show="$store.app.multiStepRecommendations.final_available_cash">
              Final cash: €<span x-text="$store.app.multiStepRecommendations.final_available_cash.toLocaleString()"></span>
            </div>
          </div>
        </template>

        <!-- SELL SECTION (only show if no multi-step recommendations) -->
        <template x-if="(!$store.app.multiStepRecommendations || $store.app.multiStepRecommendations.steps.length === 0) && $store.app.sellRecommendations.length > 0">
          <div class="mb-3">
            <div class="space-y-2">
              <template x-for="rec in ($store.app.sellRecommendations || [])" :key="rec.symbol">
                <div class="bg-gray-900 rounded p-2 border border-red-900/50">
                  <div class="flex items-start justify-between gap-2">
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2">
                        <span class="text-xs font-mono bg-red-900/50 text-red-300 px-1.5 py-0.5 rounded">SELL</span>
                        <span class="font-mono text-red-400 font-bold" x-text="rec.symbol"></span>
                      </div>
                      <div class="text-sm text-gray-300 truncate mt-0.5" x-text="rec.name"></div>
                      <div class="text-xs text-gray-500 mt-1" x-text="rec.reason"></div>
                    </div>
                    <div class="text-right flex-shrink-0">
                      <div class="text-sm font-mono font-bold text-red-400" x-text="'-€' + rec.estimated_value.toLocaleString()"></div>
                      <div class="text-xs text-gray-400" x-text="rec.quantity + ' @ €' + rec.estimated_price"></div>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </template>

        <!-- BUY SECTION (only show if no multi-step recommendations) -->
        <template x-if="(!$store.app.multiStepRecommendations || $store.app.multiStepRecommendations.steps.length === 0) && $store.app.recommendations.length > 0">
          <div>
            <div class="space-y-2">
              <template x-for="(rec, index) in ($store.app.recommendations || [])" :key="rec.symbol">
                <div class="bg-gray-900 rounded p-2 border border-gray-700">
                  <div class="flex items-start justify-between gap-2">
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2">
                        <span class="text-xs font-mono bg-green-900/50 text-green-300 px-1.5 py-0.5 rounded" x-text="'#' + (index + 1)"></span>
                        <span class="font-mono text-green-400 font-bold" x-text="rec.symbol"></span>
                        <span class="text-xs px-1.5 py-0.5 rounded"
                              :class="rec.geography === 'EU' ? 'bg-blue-900 text-blue-300' : rec.geography === 'US' ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'"
                              x-text="rec.geography"></span>
                      </div>
                      <div class="text-sm text-gray-300 truncate mt-0.5" x-text="rec.name"></div>
                      <div class="text-xs text-gray-500 mt-1" x-text="rec.reason"></div>
                    </div>
                    <div class="text-right flex-shrink-0">
                      <div class="text-sm font-mono font-bold text-green-400" x-text="'€' + rec.amount.toLocaleString()"></div>
                      <div class="text-xs text-gray-400" x-text="rec.quantity ? rec.quantity + ' @ €' + rec.current_price : ''"></div>
                      <!-- Fund this button - shows when cash is insufficient -->
                      <button x-show="rec.amount > ($store.app.allocation?.cash_balance || 0)"
                              @click.stop="$store.app.openFundingModal(rec)"
                              class="mt-1 px-2 py-0.5 text-xs bg-blue-900/50 text-blue-300 hover:bg-blue-800 rounded transition-colors">
                        Fund this
                      </button>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </template>

        </div><!-- End scrollable content -->
      </div>
    `;
  }
}

customElements.define('next-actions-card', NextActionsCard);
