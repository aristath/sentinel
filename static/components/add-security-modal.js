/**
 * Add Security Modal Component
 * Form for adding new securities to the universe
 */
class AddSecurityModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showAddSecurityModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-4"
           x-transition>
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-md modal-content" @click.stop>
          <div class="flex items-center justify-between p-4 border-b border-gray-700">
            <h2 class="text-lg font-semibold text-gray-100">Add Security to Universe</h2>
            <button @click="$store.app.showAddSecurityModal = false; $store.app.resetNewSecurity()"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <div class="p-4 space-y-4">
            <div>
              <label class="block text-sm text-gray-300 mb-1">Identifier *</label>
              <input type="text"
                     x-model="$store.app.newSecurity.identifier"
                     placeholder="e.g., AAPL.US or US0378331005"
                     class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
              <p class="text-xs text-gray-300 mt-1">Enter Tradernet symbol (e.g., AAPL.US) or ISIN (e.g., US0378331005)</p>
            </div>

            <div class="bg-blue-900/20 border border-blue-700/50 rounded p-3">
              <p class="text-xs text-blue-300 mb-2">ℹ️ All data will be automatically fetched: name, country, exchange, industry, currency, ISIN, historical data (10 years), and initial score calculation.</p>
            </div>
          </div>

          <div class="flex justify-end gap-2 p-4 border-t border-gray-700">
            <button @click="$store.app.showAddSecurityModal = false; $store.app.resetNewSecurity()"
                    class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
              Cancel
            </button>
            <button @click="$store.app.addSecurity()"
                    :disabled="$store.app.addingSecurity || !$store.app.newSecurity.identifier"
                    class="px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm rounded transition-colors disabled:opacity-50">
              <span x-show="$store.app.addingSecurity" class="inline-block animate-spin mr-1">&#9696;</span>
              <span x-text="$store.app.addingSecurity ? 'Adding Security...' : 'Add Security'"></span>
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('add-security-modal', AddSecurityModal);
