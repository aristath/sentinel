/**
 * Funding Modal Component
 * Shows funding options to enable a buy recommendation
 */
class FundingModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showFundingModal"
           x-cloak
           class="fixed inset-0 z-50 overflow-y-auto"
           @keydown.escape.window="$store.app.closeFundingModal()">
        <!-- Backdrop -->
        <div class="fixed inset-0 bg-black/70 transition-opacity"
             @click="$store.app.closeFundingModal()"></div>

        <!-- Modal -->
        <div class="flex min-h-full items-center justify-center p-4">
          <div class="relative bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] border border-gray-700 flex flex-col"
               @click.stop>
            <!-- Header -->
            <div class="flex items-center justify-between p-4 border-b border-gray-700 flex-shrink-0">
              <div>
                <h3 class="text-lg font-semibold text-white">
                  Fund: <span class="text-green-400" x-text="$store.app.fundingTarget?.symbol"></span>
                </h3>
                <p class="text-sm text-gray-400">
                  Buy €<span x-text="$store.app.fundingTarget?.amount?.toLocaleString()"></span>
                </p>
              </div>
              <button @click="$store.app.closeFundingModal()"
                      class="text-gray-400 hover:text-white p-1">
                <span class="text-xl">&times;</span>
              </button>
            </div>

            <!-- Content -->
            <div class="p-4 overflow-y-auto flex-1 min-h-0">
              <!-- Loading State -->
              <template x-if="$store.app.loadingFundingOptions">
                <div class="flex items-center justify-center py-8">
                  <span class="animate-spin text-2xl">&#9696;</span>
                  <span class="ml-2 text-gray-400">Loading funding options...</span>
                </div>
              </template>

              <!-- Cash Info -->
              <template x-if="!$store.app.loadingFundingOptions && $store.app.fundingData">
                <div class="mb-4 p-3 bg-gray-900 rounded border border-gray-700">
                  <div class="flex justify-between text-sm">
                    <span class="text-gray-400">Cash Available:</span>
                    <span class="text-white font-mono" x-text="'€' + ($store.app.fundingData.cash_available || 0).toLocaleString()"></span>
                  </div>
                  <div class="flex justify-between text-sm mt-1">
                    <span class="text-gray-400">Cash Needed:</span>
                    <span class="text-yellow-400 font-mono" x-text="'€' + ($store.app.fundingData.cash_needed || 0).toLocaleString()"></span>
                  </div>
                </div>
              </template>

              <!-- No Options -->
              <template x-if="!$store.app.loadingFundingOptions && $store.app.fundingOptions.length === 0">
                <div class="text-center py-8 text-gray-500">
                  <template x-if="$store.app.fundingData?.message">
                    <p x-text="$store.app.fundingData.message"></p>
                  </template>
                  <template x-if="!$store.app.fundingData?.message">
                    <p>No funding options available. Not enough positions can be sold.</p>
                  </template>
                </div>
              </template>

              <!-- Funding Options -->
              <template x-if="!$store.app.loadingFundingOptions && $store.app.fundingOptions.length > 0">
                <div class="space-y-4">
                  <template x-for="(option, idx) in $store.app.fundingOptions" :key="option.strategy">
                    <div class="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
                      <!-- Option Header -->
                      <div class="p-3 border-b border-gray-700 flex items-center justify-between">
                        <div>
                          <div class="flex items-center gap-2">
                            <span class="text-xs px-2 py-0.5 rounded font-mono"
                                  :class="idx === 0 ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-300'"
                                  x-text="'Option ' + (idx + 1)"></span>
                            <span class="text-white font-medium" x-text="option.description"></span>
                          </div>
                          <div class="text-xs text-gray-500 mt-1" x-text="'Strategy: ' + option.strategy"></div>
                        </div>
                        <div class="text-right">
                          <div class="font-mono font-bold"
                               :class="option.net_score_change >= 0 ? 'text-green-400' : 'text-red-400'"
                               x-text="(option.net_score_change >= 0 ? '+' : '') + option.net_score_change.toFixed(1)"></div>
                          <div class="text-xs text-gray-500">score change</div>
                        </div>
                      </div>

                      <!-- Sells List -->
                      <div class="p-3">
                        <div class="text-xs text-gray-500 mb-2">Positions to sell:</div>
                        <div class="space-y-2">
                          <template x-for="sell in option.sells" :key="sell.symbol">
                            <div class="flex items-center justify-between text-sm">
                              <div class="flex items-center gap-2">
                                <span class="text-xs px-1.5 py-0.5 bg-red-900/50 text-red-300 rounded">SELL</span>
                                <span class="font-mono text-white" x-text="sell.symbol"></span>
                                <span class="text-gray-500" x-text="sell.sell_pct.toFixed(0) + '%'"></span>
                                <!-- Warnings Popover -->
                                <template x-if="sell.warnings && sell.warnings.length > 0">
                                  <div class="relative inline-block" x-data="{ open: false }">
                                    <span class="text-yellow-500 cursor-pointer hover:text-yellow-400"
                                          @mouseenter="open = true"
                                          @mouseleave="open = false"
                                          @click="open = !open">&#9888;</span>
                                    <div x-show="open" x-cloak
                                         x-transition:enter="transition ease-out duration-100"
                                         x-transition:enter-start="opacity-0 scale-95"
                                         x-transition:enter-end="opacity-100 scale-100"
                                         class="absolute z-50 left-6 top-0 w-64 p-2 bg-yellow-900/95 border border-yellow-700 rounded shadow-lg text-xs">
                                      <div class="font-semibold text-yellow-300 mb-1 pb-1 border-b border-yellow-700/50">Warnings:</div>
                                      <template x-for="warning in sell.warnings" :key="warning">
                                        <div class="py-1 text-yellow-200 flex items-start gap-1">
                                          <span class="text-yellow-500">•</span>
                                          <span x-text="warning"></span>
                                        </div>
                                      </template>
                                    </div>
                                  </div>
                                </template>
                              </div>
                              <div class="text-right">
                                <span class="font-mono text-red-400" x-text="'€' + sell.value_eur.toLocaleString()"></span>
                                <span class="text-xs ml-1"
                                      :class="sell.profit_pct >= 0 ? 'text-green-500' : 'text-red-500'"
                                      x-text="'(' + (sell.profit_pct >= 0 ? '+' : '') + sell.profit_pct.toFixed(1) + '%)'"></span>
                              </div>
                            </div>
                          </template>
                        </div>

                        <!-- Total and Execute -->
                        <div class="mt-3 pt-3 border-t border-gray-700 flex items-center justify-between">
                          <div class="text-sm">
                            <span class="text-gray-400">Total:</span>
                            <span class="font-mono text-white ml-1" x-text="'€' + option.total_sell_value.toLocaleString()"></span>
                            <template x-if="option.has_warnings">
                              <span class="ml-2 text-xs text-yellow-500">&#9888; Review warnings above</span>
                            </template>
                          </div>
                          <button @click="$store.app.executeFunding(option)"
                                  :disabled="$store.app.executingFunding"
                                  class="px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white text-sm rounded transition-colors">
                            <span x-show="!$store.app.executingFunding">Execute</span>
                            <span x-show="$store.app.executingFunding" class="animate-spin inline-block">&#9696;</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </template>
                </div>
              </template>
            </div>

            <!-- Footer -->
            <div class="p-4 border-t border-gray-700 flex justify-end flex-shrink-0">
              <button @click="$store.app.closeFundingModal()"
                      class="px-4 py-2 text-gray-400 hover:text-white transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('funding-modal', FundingModal);
