/**
 * Edit Stock Modal Component
 * Form for editing existing stocks in the universe
 */
class EditStockModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showEditStockModal"
           class="modal-overlay"
           x-transition>
        <div class="modal modal--sm">
          <div class="modal__header">
            <h2 class="modal__title">Edit Stock</h2>
            <button @click="$store.app.closeEditStock()"
                    class="modal__close">&times;</button>
          </div>

          <template x-if="$store.app.editingStock">
            <div class="modal__body">
              <div class="form-group">
                <label class="label">Symbol (Tradernet)</label>
                <input type="text"
                       :value="$store.app.editingStock.symbol"
                       disabled
                       class="input input--disabled">
                <small class="text-muted">Primary identifier (read-only)</small>
              </div>

              <div class="form-group">
                <label class="label">Yahoo Symbol (override)</label>
                <input type="text"
                       x-model="$store.app.editingStock.yahoo_symbol"
                       placeholder="Leave empty to use convention"
                       class="input">
                <small class="text-muted">e.g., 1810.HK for Xiaomi, 300750.SZ for CATL</small>
              </div>

              <div class="form-group">
                <label class="label">Name</label>
                <input type="text"
                       x-model="$store.app.editingStock.name"
                       class="input">
              </div>

              <div class="form-group">
                <label class="label">Region</label>
                <select x-model="$store.app.editingStock.geography" class="input">
                  <template x-for="geo in $store.app.geographies" :key="geo">
                    <option :value="geo" x-text="geo"></option>
                  </template>
                </select>
              </div>

              <div class="form-group">
                <label class="label">Industry</label>
                <input type="text"
                       x-model="$store.app.editingStock.industry"
                       placeholder="e.g., Industrial, Defense"
                       class="input">
                <small class="text-muted">Comma-separated for multiple industries</small>
              </div>

              <div class="form-group">
                <label class="label">Min Lot Size</label>
                <input type="number"
                       x-model="$store.app.editingStock.min_lot"
                       min="1"
                       step="1"
                       class="input">
                <small class="text-muted">Minimum shares per trade (e.g., 100 for Japanese stocks)</small>
              </div>
            </div>
          </template>

          <div class="modal__footer">
            <button @click="$store.app.closeEditStock()"
                    class="btn btn--secondary">
              Cancel
            </button>
            <button @click="$store.app.saveStock()"
                    :disabled="$store.app.loading.stockSave"
                    class="btn btn--primary">
              <span x-show="$store.app.loading.stockSave" class="btn__spinner">&#9696;</span>
              Save Changes
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('edit-stock-modal', EditStockModal);
