/**
 * P&L Card Component
 * Displays total portfolio profit/loss
 */
class PnlCard extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="card card--pnl" x-data="{ editingDeposits: false, depositAmount: '' }">
        <div class="card__header">
          <h2 class="card__title">Total Gains/Losses</h2>
          <button @click="$store.app.fetchPnl()"
                  class="btn btn--sm btn--ghost"
                  :disabled="$store.app.pnl.loading"
                  title="Refresh P&L">
            <span x-show="$store.app.pnl.loading" class="btn__spinner">&#9696;</span>
            <span x-show="!$store.app.pnl.loading">&#8635;</span>
          </button>
        </div>

        <div class="pnl-display">
          <!-- Loading state -->
          <template x-if="$store.app.pnl.loading && $store.app.pnl.pnl === null">
            <div class="pnl-loading">Loading...</div>
          </template>

          <!-- Error state -->
          <template x-if="$store.app.pnl.error && !$store.app.pnl.loading">
            <div class="pnl-error" x-text="$store.app.pnl.error"></div>
          </template>

          <!-- Deposits not set - show setup form -->
          <template x-if="!$store.app.pnl.deposits_set && !$store.app.pnl.error && !$store.app.pnl.loading">
            <div class="pnl-setup">
              <div x-show="!editingDeposits" class="pnl-setup__prompt">
                <p class="pnl-setup__text">Set your total deposits to calculate P&L</p>
                <button @click="editingDeposits = true; depositAmount = ''"
                        class="btn btn--primary btn--sm">
                  Set Deposits
                </button>
              </div>
              <div x-show="editingDeposits" class="pnl-setup__form">
                <input type="number"
                       x-model="depositAmount"
                       placeholder="Total deposits in EUR"
                       class="input input--sm"
                       @keyup.enter="$store.app.setManualDeposits(depositAmount); editingDeposits = false">
                <div class="pnl-setup__actions">
                  <button @click="editingDeposits = false" class="btn btn--secondary btn--sm">Cancel</button>
                  <button @click="$store.app.setManualDeposits(depositAmount); editingDeposits = false"
                          class="btn btn--primary btn--sm">Save</button>
                </div>
              </div>
            </div>
          </template>

          <!-- P&L Value -->
          <template x-if="$store.app.pnl.deposits_set && $store.app.pnl.pnl !== null && !$store.app.pnl.error">
            <div class="pnl-content">
              <div class="pnl-value"
                   :class="$store.app.pnl.pnl >= 0 ? 'pnl-value--positive' : 'pnl-value--negative'">
                <span x-text="$store.app.pnl.pnl >= 0 ? '+' : ''"></span>
                <span x-text="'€' + $store.app.pnl.pnl.toLocaleString('en', {minimumFractionDigits: 2, maximumFractionDigits: 2})"></span>
              </div>
              <div class="pnl-percent"
                   :class="$store.app.pnl.pnl_pct >= 0 ? 'pnl-percent--positive' : 'pnl-percent--negative'">
                (<span x-text="$store.app.pnl.pnl_pct >= 0 ? '+' : ''"></span><span x-text="$store.app.pnl.pnl_pct.toFixed(2)"></span>%)
              </div>
              <div class="pnl-details">
                <span class="pnl-detail">
                  Value: <span x-text="'€' + ($store.app.pnl.total_value || 0).toLocaleString('en', {minimumFractionDigits: 2, maximumFractionDigits: 2})"></span>
                </span>
                <span class="pnl-detail">
                  Invested: <span x-text="'€' + ($store.app.pnl.net_deposits || 0).toLocaleString('en', {minimumFractionDigits: 2, maximumFractionDigits: 2})"></span>
                </span>
              </div>
              <button @click="editingDeposits = true; depositAmount = $store.app.pnl.manual_deposits"
                      class="pnl-edit-link">
                Edit deposits
              </button>
              <div x-show="editingDeposits" class="pnl-setup__form" style="margin-top: 0.5rem">
                <input type="number"
                       x-model="depositAmount"
                       placeholder="Total deposits in EUR"
                       class="input input--sm"
                       @keyup.enter="$store.app.setManualDeposits(depositAmount); editingDeposits = false">
                <div class="pnl-setup__actions">
                  <button @click="editingDeposits = false" class="btn btn--secondary btn--sm">Cancel</button>
                  <button @click="$store.app.setManualDeposits(depositAmount); editingDeposits = false"
                          class="btn btn--primary btn--sm">Save</button>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    `;
  }
}

customElements.define('pnl-card', PnlCard);
