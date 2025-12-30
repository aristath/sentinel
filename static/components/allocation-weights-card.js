/**
 * Allocation Weights Card Component
 * Container for country and industry allocation radar charts
 */
class AllocationWeightsCard extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3" x-data>
        <h2 class="text-xs text-gray-300 uppercase tracking-wide mb-3">Portfolio Allocation</h2>
        <allocation-radar></allocation-radar>
      </div>
    `;
  }
}

customElements.define('allocation-weights-card', AllocationWeightsCard);
