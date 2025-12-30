/**
 * Market Status Component
 * Displays market status indicators for different geographies
 */
class MarketStatus extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="flex flex-wrap items-center gap-2 text-xs mb-4" x-data>
        <template x-for="(market, geo) in $store.app.markets" :key="geo">
          <div class="flex items-center gap-1 px-2 py-1 rounded"
               :class="market.open ? 'bg-green-900/30 text-green-400' : 'bg-gray-800 text-gray-500'"
               :title="market.open ? geo + ' market open (closes ' + market.closes_at + ')' : geo + ' market closed (opens ' + market.opens_at + (market.opens_date ? ' on ' + market.opens_date : '') + ')'">
            <span class="w-1.5 h-1.5 rounded-full"
                  :class="market.open ? 'bg-green-500' : 'bg-gray-600'"></span>
            <span x-text="geo"></span>
          </div>
        </template>
      </div>
    `;
  }
}

customElements.define('market-status', MarketStatus);
