/**
 * Summary Cards Component
 * Displays portfolio summary statistics
 */
class SummaryCards extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="grid grid-cols-3 gap-3" x-data>
        <div class="bg-gray-800 border border-gray-700 rounded p-3">
          <p class="text-xs text-gray-400 uppercase tracking-wide mb-1">Total Value</p>
          <p class="text-xl font-mono font-bold text-green-400" x-text="formatCurrency($store.app.allocation.total_value)"></p>
        </div>
        <div class="bg-gray-800 border border-gray-700 rounded p-3">
          <p class="text-xs text-gray-400 uppercase tracking-wide mb-1">Cash Balance</p>
          <p class="text-xl font-mono font-bold text-gray-100" x-text="formatCurrency($store.app.allocation.cash_balance)"></p>
        </div>
        <div class="bg-gray-800 border border-gray-700 rounded p-3">
          <p class="text-xs text-gray-400 uppercase tracking-wide mb-1">Active Positions</p>
          <p class="text-xl font-mono font-bold text-gray-100" x-text="$store.app.status.active_positions || 0"></p>
        </div>
      </div>
    `;
  }
}

customElements.define('summary-cards', SummaryCards);
