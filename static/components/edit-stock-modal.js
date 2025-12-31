/**
 * Edit Stock Modal Component
 * Form for editing existing securitys in the universe
 */
class EditStockModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showEditStockModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-4"
           x-transition>
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-md modal-content" @click.stop>
          <div class="flex items-center justify-between p-4 border-b border-gray-700">
            <h2 class="text-lg font-semibold text-gray-100">Edit Stock</h2>
            <button @click="$store.app.closeEditStock()"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <template x-if="$store.app.editingStock">
            <div class="p-4 space-y-4">
              <div>
                <label class="block text-sm text-gray-300 mb-1">Symbol (Tradernet)</label>
                <input type="text"
                       x-model="$store.app.editingStock.symbol"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">Tradernet ticker symbol (e.g., ASML.NL, RHM.DE)</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Yahoo Symbol (override)</label>
                <input type="text"
                       x-model="$store.app.editingStock.yahoo_symbol"
                       placeholder="Leave empty to use convention"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">e.g., 1810.HK for Xiaomi, 300750.SZ for CATL</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Name</label>
                <input type="text"
                       x-model="$store.app.editingStock.name"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Country</label>
                <div class="px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-300">
                  <span x-text="$store.app.editingStock.country || 'Auto-detected from Yahoo Finance'"></span>
                </div>
                <p class="text-xs text-gray-300 mt-1">Automatically detected from Yahoo Finance</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Exchange</label>
                <div class="px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-300">
                  <span x-text="$store.app.editingStock.fullExchangeName || 'Auto-detected from Yahoo Finance'"></span>
                </div>
                <p class="text-xs text-gray-300 mt-1">Automatically detected from Yahoo Finance</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Industry</label>
                <div class="px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-300">
                  <span x-text="$store.app.editingStock.industry || 'Auto-detected from Yahoo Finance'"></span>
                </div>
                <p class="text-xs text-gray-300 mt-1">Automatically detected from Yahoo Finance during daily pipeline</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Min Lot Size</label>
                <input type="number"
                       x-model="$store.app.editingStock.min_lot"
                       min="1"
                       step="1"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">Minimum shares per trade (e.g., 100 for Japanese securitys)</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Min Portfolio Target (%)</label>
                <input type="number"
                       x-model="$store.app.editingStock.min_portfolio_target"
                       min="0"
                       max="20"
                       step="0.1"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">Minimum target portfolio allocation (0-20%). Used by optimizer to set lower bound.</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Max Portfolio Target (%)</label>
                <input type="number"
                       x-model="$store.app.editingStock.max_portfolio_target"
                       min="0"
                       max="30"
                       step="0.1"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">Maximum target portfolio allocation (0-30%). Used by optimizer to set upper bound.</p>
              </div>

              <div class="border-t border-gray-700 pt-4 mt-4 space-y-3">
                <label class="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox"
                         x-model="$store.app.editingStock.allow_buy"
                         class="w-4 h-4 rounded border-gray-600 bg-gray-900 text-green-600 focus:ring-green-500 focus:ring-offset-gray-800">
                  <div>
                    <span class="text-sm text-gray-300">Allow BUY</span>
                    <p class="text-xs text-gray-300">Include in buy recommendations</p>
                  </div>
                </label>

                <label class="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox"
                         x-model="$store.app.editingStock.allow_sell"
                         class="w-4 h-4 rounded border-gray-600 bg-gray-900 text-red-600 focus:ring-red-500 focus:ring-offset-gray-800">
                  <div>
                    <span class="text-sm text-gray-300">Allow SELL</span>
                    <p class="text-xs text-gray-300">Include in sell recommendations</p>
                  </div>
                </label>
              </div>
            </div>
          </template>

          <div class="flex justify-between items-center p-4 border-t border-gray-700">
            <button @click="$store.app.refreshStockData($store.app.editingStock?.originalIsin)"
                    :disabled="$store.app.loading.refreshData"
                    class="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 text-white text-sm rounded transition-colors disabled:opacity-50"
                    title="Sync historical data, recalculate metrics, and refresh score">
              <span x-show="$store.app.loading.refreshData" class="inline-block animate-spin mr-1">&#9696;</span>
              <span x-text="$store.app.loading.refreshData ? 'Refreshing...' : 'Refresh Data'"></span>
            </button>
            <div class="flex gap-2">
              <button @click="$store.app.closeEditStock()"
                      class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
                Cancel
              </button>
              <button @click="$store.app.saveStock()"
                      :disabled="$store.app.loading.securitySave"
                      class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors disabled:opacity-50">
                <span x-show="$store.app.loading.securitySave" class="inline-block animate-spin mr-1">&#9696;</span>
                Save Changes
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('edit-security-modal', EditStockModal);
