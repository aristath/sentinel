/**
 * Trades Table Component
 * Displays recent trades
 */
class TradesTable extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3 mt-4" x-data>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xs text-gray-400 uppercase tracking-wide">Recent Trades</h2>
        </div>

        <div x-show="$store.app.trades.length === 0" class="text-center py-6 text-gray-500 text-sm">
          No trades yet
        </div>

        <div x-show="$store.app.trades.length > 0" class="overflow-x-auto overflow-y-scroll" style="max-height: 350px;">
          <table class="w-full text-xs">
            <thead class="text-gray-500 uppercase text-left border-b border-gray-700">
              <tr>
                <th class="py-2 px-2">Date</th>
                <th class="py-2 px-2">Symbol</th>
                <th class="py-2 px-2 hidden sm:table-cell">Name</th>
                <th class="py-2 px-2">Side</th>
                <th class="py-2 px-2 text-right">Qty</th>
                <th class="py-2 px-2 text-right hidden sm:table-cell">Price</th>
                <th class="py-2 px-2 text-right">Value</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-800">
              <template x-for="trade in ($store.app.trades || [])" :key="trade.id">
                <tr class="hover:bg-gray-800/50">
                  <td class="py-1.5 px-2 text-gray-400" x-text="formatDateTime(trade.executed_at)"></td>
                  <td class="py-1.5 px-2 font-mono text-blue-400" x-text="trade.symbol"></td>
                  <td class="py-1.5 px-2 text-gray-500 truncate max-w-32 hidden sm:table-cell" x-text="trade.name"></td>
                  <td class="py-1.5 px-2">
                    <span class="px-1.5 py-0.5 rounded text-xs font-medium"
                          :class="trade.side.toLowerCase() === 'buy' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'"
                          x-text="trade.side.toUpperCase()"></span>
                  </td>
                  <td class="py-1.5 px-2 text-right font-mono text-gray-300" x-text="trade.quantity"></td>
                  <td class="py-1.5 px-2 text-right font-mono text-gray-400 hidden sm:table-cell" x-text="formatCurrency(trade.price)"></td>
                  <td class="py-1.5 px-2 text-right font-mono font-semibold text-gray-200" x-text="formatCurrency(trade.quantity * trade.price)"></td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    `;
  }
}

customElements.define('trades-table', TradesTable);
