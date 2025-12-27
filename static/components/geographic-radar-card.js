/**
 * Geographic Radar Card Component
 * Card wrapper for geographic allocation radar chart
 */
class GeographicRadarCard extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3" x-data>
        <h2 class="text-xs text-gray-400 uppercase tracking-wide mb-3">Geographic Allocation</h2>
        <allocation-radar type="geographic"></allocation-radar>
      </div>
    `;
  }
}

customElements.define('geographic-radar-card', GeographicRadarCard);

