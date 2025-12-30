/**
 * Quick Actions Component
 * Provides action buttons for refresh scores, sync prices
 */
class QuickActions extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3" x-data>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xs text-gray-300 uppercase tracking-wide">Quick Actions</h2>
        </div>

        <div class="flex flex-col gap-2">
          <button @click="$store.app.refreshScores()"
                  class="w-full px-3 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded transition-colors disabled:opacity-50"
                  :disabled="$store.app.loading.scores">
            <span x-show="$store.app.loading.scores" class="inline-block animate-spin mr-1">&#9696;</span>
            Refresh All Scores
          </button>

          <button @click="$store.app.syncPrices()"
                  class="w-full px-3 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors disabled:opacity-50"
                  :disabled="$store.app.loading.sync">
            <span x-show="$store.app.loading.sync" class="inline-block animate-spin mr-1">&#9696;</span>
            Sync Prices
          </button>
        </div>

        <div x-show="$store.app.message"
             x-text="$store.app.message"
             class="mt-3 px-3 py-2 rounded text-sm"
             :class="$store.app.messageType === 'success' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'">
        </div>
      </div>
    `;
  }
}

customElements.define('quick-actions', QuickActions);
