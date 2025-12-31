/**
 * Edit Security Modal Component
 * Form for editing existing securities in the universe
 */
class EditSecurityModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showEditSecurityModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-4"
           x-transition>
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-md modal-content" @click.stop>
          <div class="flex items-center justify-between p-4 border-b border-gray-700">
            <h2 class="text-lg font-semibold text-gray-100">Edit Security</h2>
            <button @click="$store.app.closeEditStock()"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <template x-if="$store.app.editingSecurity">
            <div class="p-4 space-y-4">
              <div>
                <label class="block text-sm text-gray-300 mb-1">Symbol (Tradernet)</label>
                <input type="text"
                       x-model="$store.app.editingSecurity.symbol"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">Tradernet ticker symbol (e.g., ASML.NL, RHM.DE)</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Yahoo Symbol (override)</label>
                <input type="text"
                       x-model="$store.app.editingSecurity.yahoo_symbol"
                       placeholder="Leave empty to use convention"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">e.g., 1810.HK for Xiaomi, 300750.SZ for CATL</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Name</label>
                <input type="text"
                       x-model="$store.app.editingSecurity.name"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">ISIN</label>
                <input type="text"
                       disabled
                       :value="$store.app.editingSecurity.isin"
                       class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-sm text-gray-400 cursor-not-allowed">
                <p class="text-xs text-gray-300 mt-1">Unique security identifier (cannot be changed)</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Country</label>
                <input type="text"
                       x-model="$store.app.editingSecurity.country"
                       placeholder="e.g., United States, Netherlands, Germany"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">Country where the security is domiciled (auto-detected from Yahoo Finance, can be manually edited)</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Exchange</label>
                <input type="text"
                       x-model="$store.app.editingSecurity.fullExchangeName"
                       placeholder="e.g., NASDAQ, Euronext Amsterdam, XETRA"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">Exchange where the security trades (auto-detected from Yahoo Finance, can be manually edited)</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Industry</label>
                <input type="text"
                       x-model="$store.app.editingSecurity.industry"
                       placeholder="e.g., Technology, Healthcare, Financial Services"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">Industry classification (auto-detected from Yahoo Finance, can be manually edited)</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Min Lot Size</label>
                <input type="number"
                       x-model="$store.app.editingSecurity.min_lot"
                       min="1"
                       step="1"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">Minimum shares per trade (e.g., 100 for Japanese securities)</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Min Portfolio Target (%)</label>
                <input type="number"
                       x-model="$store.app.editingSecurity.min_portfolio_target"
                       min="0"
                       max="20"
                       step="0.1"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">Minimum target portfolio allocation (0-20%). Used by optimizer to set lower bound.</p>
              </div>

              <div>
                <label class="block text-sm text-gray-300 mb-1">Max Portfolio Target (%)</label>
                <input type="number"
                       x-model="$store.app.editingSecurity.max_portfolio_target"
                       min="0"
                       max="30"
                       step="0.1"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-300 mt-1">Maximum target portfolio allocation (0-30%). Used by optimizer to set upper bound.</p>
              </div>

              <div class="border-t border-gray-700 pt-4 mt-4 space-y-3">
                <label class="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox"
                         x-model="$store.app.editingSecurity.allow_buy"
                         class="w-4 h-4 rounded border-gray-600 bg-gray-900 text-green-600 focus:ring-green-500 focus:ring-offset-gray-800">
                  <div>
                    <span class="text-sm text-gray-300">Allow BUY</span>
                    <p class="text-xs text-gray-300">Include in buy recommendations</p>
                  </div>
                </label>

                <label class="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox"
                         x-model="$store.app.editingSecurity.allow_sell"
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
            <button @click="$store.app.refreshSecurityData($store.app.editingSecurity?.originalIsin)"
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

customElements.define('edit-security-modal', EditSecurityModal);
