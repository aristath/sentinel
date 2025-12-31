/**
 * Universe Management Modal Component
 * Shows suggestions for adding and pruning securitys from the universe
 */
class UniverseManagementModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showUniverseManagementModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-4"
           x-transition>
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col modal-content" @click.stop>
          <div class="flex items-center justify-between p-4 border-b border-gray-700">
            <h2 class="text-lg font-semibold text-gray-100">Manage Universe</h2>
            <button @click="$store.app.showUniverseManagementModal = false"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <div class="flex-1 overflow-y-auto p-4 space-y-6">
            <!-- Loading State -->
            <div x-show="$store.app.loading.universeSuggestions"
                 class="text-center py-8 text-gray-300">
              <div class="inline-block animate-spin mr-2">&#9696;</div>
              Loading suggestions...
            </div>

            <!-- Content -->
            <div x-show="!$store.app.loading.universeSuggestions" class="space-y-6">
              <!-- Candidates to Add Section -->
              <div>
                <h3 class="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
                  <span class="px-2 py-1 bg-green-600/20 text-green-400 rounded text-xs">
                    Candidates to Add
                  </span>
                  <span class="text-xs text-gray-400">
                    (<span x-text="$store.app.universeSuggestions.candidatesToAdd.length"></span>)
                  </span>
                </h3>

                <!-- Empty State -->
                <div x-show="$store.app.universeSuggestions.candidatesToAdd.length === 0"
                     class="text-center py-4 text-gray-400 text-sm border border-gray-700 rounded">
                  No candidates found above score threshold
                </div>

                <!-- Candidates List -->
                <div x-show="$store.app.universeSuggestions.candidatesToAdd.length > 0"
                     class="space-y-2">
                  <template x-for="candidate in $store.app.universeSuggestions.candidatesToAdd" :key="candidate.symbol">
                    <div class="bg-gray-900 border border-gray-700 rounded p-3 flex items-start justify-between gap-4">
                      <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-1">
                          <span class="font-mono text-blue-400 font-semibold" x-text="candidate.symbol"></span>
                          <span class="px-1.5 py-0.5 bg-blue-600/20 text-blue-400 rounded text-xs font-mono"
                                x-text="'Score: ' + candidate.score.toFixed(3)"></span>
                        </div>
                        <div class="text-sm text-gray-300 mb-1" x-text="candidate.name"></div>
                        <div class="flex flex-wrap gap-2 text-xs text-gray-400">
                          <span x-show="candidate.country" x-text="'Country: ' + candidate.country"></span>
                          <span x-show="candidate.industry" x-text="'Industry: ' + candidate.industry"></span>
                          <span x-show="candidate.exchange" x-text="'Exchange: ' + candidate.exchange"></span>
                          <span x-show="candidate.isin" x-text="'ISIN: ' + candidate.isin"></span>
                          <span x-show="candidate.volume" x-text="'Volume: ' + candidate.volume.toLocaleString()"></span>
                        </div>
                      </div>
                      <button @click="$store.app.addStockFromSuggestion(candidate.isin)"
                              :disabled="$store.app.addingFromSuggestion[candidate.isin]"
                              class="px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white text-xs rounded transition-colors disabled:opacity-50 whitespace-nowrap">
                        <span x-show="$store.app.addingFromSuggestion[candidate.isin]" class="inline-block animate-spin mr-1">&#9696;</span>
                        <span x-text="$store.app.addingFromSuggestion[candidate.isin] ? 'Adding...' : 'Add'"></span>
                      </button>
                    </div>
                  </template>
                </div>
              </div>

              <!-- Securities to Prune Section -->
              <div>
                <h3 class="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
                  <span class="px-2 py-1 bg-red-600/20 text-red-400 rounded text-xs">
                    Securities to Prune
                  </span>
                  <span class="text-xs text-gray-400">
                    (<span x-text="$store.app.universeSuggestions.securitysToPrune.length"></span>)
                  </span>
                </h3>

                <!-- Empty State -->
                <div x-show="$store.app.universeSuggestions.securitysToPrune.length === 0"
                     class="text-center py-4 text-gray-400 text-sm border border-gray-700 rounded">
                  No securitys meet pruning criteria
                </div>

                <!-- Prune List -->
                <div x-show="$store.app.universeSuggestions.securitysToPrune.length > 0"
                     class="space-y-2">
                  <template x-for="security in $store.app.universeSuggestions.securitysToPrune" :key="security.symbol">
                    <div class="bg-gray-900 border border-gray-700 rounded p-3 flex items-start justify-between gap-4">
                      <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-1">
                          <span class="font-mono text-red-400 font-semibold" x-text="security.symbol"></span>
                          <span class="px-1.5 py-0.5 rounded text-xs font-mono"
                                :class="security.reason === 'delisted' ? 'bg-red-600/20 text-red-400' : 'bg-yellow-600/20 text-yellow-400'"
                                x-text="security.reason === 'delisted' ? 'Delisted' : 'Low Score'"></span>
                        </div>
                        <div class="text-sm text-gray-300 mb-1" x-text="security.name"></div>
                        <div class="flex flex-wrap gap-2 text-xs text-gray-400 mb-2">
                          <span x-show="security.country" x-text="'Country: ' + security.country"></span>
                          <span x-show="security.industry" x-text="'Industry: ' + security.industry"></span>
                        </div>
                        <div class="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span class="text-gray-500">Avg Score:</span>
                            <span class="text-gray-300 font-mono ml-1" x-text="security.average_score.toFixed(3)"></span>
                          </div>
                          <div>
                            <span class="text-gray-500">Current Score:</span>
                            <span class="text-gray-300 font-mono ml-1" x-text="security.current_score !== null ? security.current_score.toFixed(3) : 'N/A'"></span>
                          </div>
                          <div>
                            <span class="text-gray-500">Samples:</span>
                            <span class="text-gray-300 ml-1" x-text="security.sample_count"></span>
                          </div>
                          <div>
                            <span class="text-gray-500">Months:</span>
                            <span class="text-gray-300 ml-1" x-text="security.months_analyzed"></span>
                          </div>
                        </div>
                      </div>
                      <button @click="$store.app.pruneStockFromSuggestion(security.isin)"
                              :disabled="$store.app.pruningFromSuggestion[security.isin]"
                              class="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs rounded transition-colors disabled:opacity-50 whitespace-nowrap">
                        <span x-show="$store.app.pruningFromSuggestion[security.isin]" class="inline-block animate-spin mr-1">&#9696;</span>
                        <span x-text="$store.app.pruningFromSuggestion[security.isin] ? 'Pruning...' : 'Prune'"></span>
                      </button>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>

          <div class="flex justify-end gap-2 p-4 border-t border-gray-700">
            <button @click="$store.app.fetchUniverseSuggestions()"
                    :disabled="$store.app.loading.universeSuggestions"
                    class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors disabled:opacity-50">
              <span x-show="$store.app.loading.universeSuggestions" class="inline-block animate-spin mr-1">&#9696;</span>
              Refresh
            </button>
            <button @click="$store.app.showUniverseManagementModal = false"
                    class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
              Close
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('universe-management-modal', UniverseManagementModal);
