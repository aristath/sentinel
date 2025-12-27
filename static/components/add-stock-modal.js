/**
 * Add Stock Modal Component
 * Form for adding new stocks to the universe
 */
class AddStockModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showAddStockModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-4"
           x-transition>
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-md" @click.stop>
          <div class="flex items-center justify-between p-4 border-b border-gray-700">
            <h2 class="text-lg font-semibold text-gray-100">Add Stock to Universe</h2>
            <button @click="$store.app.showAddStockModal = false; $store.app.resetNewStock()"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <div class="p-4 space-y-4">
            <div>
              <label class="block text-sm text-gray-400 mb-1">Symbol *</label>
              <input type="text"
                     x-model="$store.app.newStock.symbol"
                     placeholder="e.g., AAPL, MSFT.US"
                     class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1">Name *</label>
              <input type="text"
                     x-model="$store.app.newStock.name"
                     placeholder="e.g., Apple Inc."
                     class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
            </div>

            <div>
              <label class="block text-sm text-gray-400 mb-1">Yahoo Symbol (optional)</label>
              <input type="text"
                     x-model="$store.app.newStock.yahoo_symbol"
                     placeholder="Leave empty to use convention"
                     class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
              <p class="text-xs text-gray-500 mt-1">e.g., 1810.HK for Xiaomi, 300750.SZ for CATL</p>
            </div>

            <div class="bg-blue-900/20 border border-blue-700/50 rounded p-3">
              <p class="text-xs text-blue-300 mb-2">ℹ️ Country, Exchange, and Industry will be automatically detected from Yahoo Finance when the stock is added.</p>
            </div>
          </div>

          <div class="flex justify-end gap-2 p-4 border-t border-gray-700">
            <button @click="$store.app.showAddStockModal = false; $store.app.resetNewStock()"
                    class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
              Cancel
            </button>
            <button @click="$store.app.addStock()"
                    :disabled="$store.app.addingStock || !$store.app.newStock.symbol || !$store.app.newStock.name"
                    class="px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm rounded transition-colors disabled:opacity-50">
              <span x-show="$store.app.addingStock" class="inline-block animate-spin mr-1">&#9696;</span>
              Add Stock
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('add-stock-modal', AddStockModal);
