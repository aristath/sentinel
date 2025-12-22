/**
 * Edit Stock Modal Component
 * Form for editing existing stocks in the universe
 */
class EditStockModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showEditStockModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-4"
           x-transition>
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-md" @click.stop>
          <div class="flex items-center justify-between p-4 border-b border-gray-700">
            <h2 class="text-lg font-semibold text-gray-100">Edit Stock</h2>
            <button @click="$store.app.closeEditStock()"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <template x-if="$store.app.editingStock">
            <div class="p-4 space-y-4">
              <div>
                <label class="block text-sm text-gray-400 mb-1">Symbol (Tradernet)</label>
                <input type="text"
                       :value="$store.app.editingStock.symbol"
                       disabled
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-500 cursor-not-allowed">
                <p class="text-xs text-gray-500 mt-1">Primary identifier (read-only)</p>
              </div>

              <div>
                <label class="block text-sm text-gray-400 mb-1">Yahoo Symbol (override)</label>
                <input type="text"
                       x-model="$store.app.editingStock.yahoo_symbol"
                       placeholder="Leave empty to use convention"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-500 mt-1">e.g., 1810.HK for Xiaomi, 300750.SZ for CATL</p>
              </div>

              <div>
                <label class="block text-sm text-gray-400 mb-1">Name</label>
                <input type="text"
                       x-model="$store.app.editingStock.name"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
              </div>

              <div>
                <label class="block text-sm text-gray-400 mb-1">Region</label>
                <input type="text"
                       x-model="$store.app.editingStock.geography"
                       list="edit-geographies-list"
                       placeholder="e.g., EU, US, ASIA"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <datalist id="edit-geographies-list">
                  <template x-for="geo in ($store.app.geographies || [])" :key="geo">
                    <option :value="geo"></option>
                  </template>
                </datalist>
              </div>

              <div>
                <label class="block text-sm text-gray-400 mb-1">Industry</label>
                <input type="text"
                       x-model="$store.app.editingStock.industry"
                       list="edit-industries-list"
                       placeholder="e.g., Industrial, Defense"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <datalist id="edit-industries-list">
                  <template x-for="ind in ($store.app.industries || [])" :key="ind">
                    <option :value="ind"></option>
                  </template>
                </datalist>
                <p class="text-xs text-gray-500 mt-1">Comma-separated for multiple industries</p>
              </div>

              <div>
                <label class="block text-sm text-gray-400 mb-1">Min Lot Size</label>
                <input type="number"
                       x-model="$store.app.editingStock.min_lot"
                       min="1"
                       step="1"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <p class="text-xs text-gray-500 mt-1">Minimum shares per trade (e.g., 100 for Japanese stocks)</p>
              </div>
            </div>
          </template>

          <div class="flex justify-end gap-2 p-4 border-t border-gray-700">
            <button @click="$store.app.closeEditStock()"
                    class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
              Cancel
            </button>
            <button @click="$store.app.saveStock()"
                    :disabled="$store.app.loading.stockSave"
                    class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors disabled:opacity-50">
              <span x-show="$store.app.loading.stockSave" class="inline-block animate-spin mr-1">&#9696;</span>
              Save Changes
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('edit-stock-modal', EditStockModal);
