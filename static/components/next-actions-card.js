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
          <button @click="$store.app.fetchRecommendations(); $store.app.fetchSellRecommendations()"
                  class="p-1 text-gray-400 hover:text-gray-200 rounded hover:bg-gray-700 transition-colors"
                  :disabled="$store.app.loading.recommendations || $store.app.loading.sellRecommendations"
                  title="Refresh">
            <span x-show="$store.app.loading.recommendations || $store.app.loading.sellRecommendations" class="inline-block animate-spin">&#9696;</span>
            <span x-show="!$store.app.loading.recommendations && !$store.app.loading.sellRecommendations">&#8635;</span>
          </button>
        </div>

        <!-- Scrollable content area -->
        <div class="max-h-[300px] overflow-y-auto">

        <!-- Empty state -->
        <template x-if="!$store.app.loading.recommendations && !$store.app.loading.sellRecommendations && $store.app.recommendations.length === 0 && $store.app.sellRecommendations.length === 0">
          <div class="text-gray-500 text-sm py-4 text-center">No pending actions</div>
        </template>

        <!-- SELL SECTION -->
        <template x-if="$store.app.sellRecommendations.length > 0">
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

        <!-- BUY SECTION -->
        <template x-if="$store.app.recommendations.length > 0">
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
