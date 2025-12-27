/**
 * Industry Radar Card Component
 * Card wrapper for industry allocation radar chart
 */
class IndustryRadarCard extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3" x-data>
        <h2 class="text-xs text-gray-400 uppercase tracking-wide mb-3">Industry Allocation</h2>
        <allocation-radar type="industry"></allocation-radar>
      </div>
    `;
  }
}

customElements.define('industry-radar-card', IndustryRadarCard);

