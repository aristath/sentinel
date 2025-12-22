/**
 * Stock Table Component
 * Displays the stock universe with filtering, sorting, and position data
 * Responsive: Progressive column hiding on smaller screens
 */
class StockTable extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="bg-gray-800 border border-gray-700 rounded p-3" x-data="stockTableComponent()">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-xs text-gray-400 uppercase tracking-wide">Stock Universe</h2>
          <button @click="$store.app.showAddStockModal = true"
                  class="px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white text-xs rounded transition-colors">
            + Add Stock
          </button>
        </div>

        <!-- Filter Bar -->
        <div class="flex flex-col sm:flex-row gap-2 mb-3">
          <input type="text"
                 x-model="$store.app.searchQuery"
                 placeholder="Search symbol or name..."
                 class="flex-1 px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
          <div class="flex gap-2">
            <select x-model="$store.app.stockFilter"
                    class="px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
              <option value="all">All Regions</option>
              <option value="EU">EU</option>
              <option value="ASIA">Asia</option>
              <option value="US">US</option>
            </select>
            <select x-model="$store.app.industryFilter"
                    class="px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none hidden sm:block">
              <option value="all">All Sectors</option>
              <template x-for="ind in ($store.app.industries || [])" :key="ind">
                <option :value="ind" x-text="ind"></option>
              </template>
            </select>
            <select x-model="$store.app.minScore"
                    class="px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none hidden md:block">
              <option value="0">Any Score</option>
              <option value="0.3">Score >= 0.3</option>
              <option value="0.5">Score >= 0.5</option>
              <option value="0.7">Score >= 0.7</option>
            </select>
          </div>
        </div>

        <!-- Results count -->
        <div class="text-xs text-gray-500 mb-2" x-show="$store.app.stocks.length > 0">
          <span x-text="$store.app.filteredStocks.length"></span> of
          <span x-text="$store.app.stocks.length"></span> stocks
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead class="text-gray-500 uppercase text-left border-b border-gray-700">
              <tr>
                <th @click="$store.app.sortStocks('symbol')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 sticky left-0 bg-gray-800 z-10">
                  Symbol
                  <span x-show="$store.app.sortBy === 'symbol'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('name')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 hidden sm:table-cell">
                  Company
                  <span x-show="$store.app.sortBy === 'name'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('geography')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 text-center">
                  Region
                  <span x-show="$store.app.sortBy === 'geography'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('industry')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 hidden lg:table-cell">
                  Sector
                  <span x-show="$store.app.sortBy === 'industry'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('position_value')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 text-right">
                  Value
                  <span x-show="$store.app.sortBy === 'position_value'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('total_score')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 text-right">
                  Score
                  <span x-show="$store.app.sortBy === 'total_score'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('priority_multiplier')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 text-center hidden lg:table-cell">
                  Mult
                  <span x-show="$store.app.sortBy === 'priority_multiplier'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th @click="$store.app.sortStocks('priority_score')"
                    class="py-2 px-2 cursor-pointer hover:text-gray-300 text-right">
                  Priority
                  <span x-show="$store.app.sortBy === 'priority_score'" class="ml-1"
                        x-text="$store.app.sortDesc ? '▼' : '▲'"></span>
                </th>
                <th class="py-2 px-2 text-center hidden md:table-cell">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-800">
              <template x-for="stock in ($store.app.filteredStocks || [])" :key="stock.symbol">
                <tr class="hover:bg-gray-800/50 cursor-pointer md:cursor-default"
                    @click="window.innerWidth < 768 && $store.app.openEditStock(stock)">
                  <td class="py-1.5 px-2 font-mono text-blue-400 sticky left-0 bg-gray-800">
                    <button @click.stop="$store.app.showStockChart = true; $store.app.selectedStockSymbol = stock.symbol"
                            class="hover:underline cursor-pointer"
                            title="View chart">
                      <span x-text="stock.symbol"></span>
                    </button>
                  </td>
                  <td class="py-1.5 px-2 text-gray-300 truncate max-w-32 hidden sm:table-cell" x-text="stock.name"></td>
                  <td class="py-1.5 px-2 text-center">
                    <span class="px-1.5 py-0.5 rounded text-xs"
                          :class="getGeoTagClass(stock.geography)"
                          x-text="stock.geography"></span>
                  </td>
                  <td class="py-1.5 px-2 text-gray-500 truncate max-w-24 hidden lg:table-cell" x-text="stock.industry || '-'"></td>
                  <td class="py-1.5 px-2 text-right font-mono"
                      :class="stock.position_value ? 'text-green-400' : 'text-gray-600'"
                      x-text="stock.position_value ? formatCurrency(stock.position_value) : '-'"></td>
                  <td class="py-1.5 px-2 text-right">
                    <span class="font-mono px-1.5 py-0.5 rounded"
                          :class="getScoreClass(stock.total_score)"
                          x-text="formatScore(stock.total_score)"></span>
                  </td>
                  <td class="py-1.5 px-2 text-center hidden lg:table-cell">
                    <input type="number"
                           class="w-12 px-1 py-0.5 bg-gray-900 border border-gray-600 rounded text-center text-xs text-gray-300 focus:border-blue-500 focus:outline-none"
                           :value="stock.priority_multiplier || 1"
                           min="0.1"
                           max="3"
                           step="0.1"
                           @click.stop
                           @change="$store.app.updateMultiplier(stock.symbol, $event.target.value)"
                           title="Priority multiplier (0.1-3.0)">
                  </td>
                  <td class="py-1.5 px-2 text-right">
                    <span class="font-mono px-1.5 py-0.5 rounded"
                          :class="getPriorityClass(stock.priority_score)"
                          x-text="formatPriority(stock.priority_score)"></span>
                  </td>
                  <td class="py-1.5 px-2 text-center hidden md:table-cell" @click.stop>
                    <div class="flex justify-center gap-1">
                      <button @click="$store.app.openEditStock(stock)"
                              class="p-1 text-gray-400 hover:text-blue-400 transition-colors"
                              title="Edit stock">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                      </button>
                      <button @click="$store.app.refreshSingleScore(stock.symbol)"
                              class="p-1 text-gray-400 hover:text-green-400 transition-colors"
                              title="Refresh score">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M21 2v6h-6"/>
                          <path d="M3 12a9 9 0 0 1 15-6.7L21 8"/>
                          <path d="M3 22v-6h6"/>
                          <path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>
                        </svg>
                      </button>
                      <button @click="$store.app.removeStock(stock.symbol)"
                              class="p-1 text-gray-400 hover:text-red-400 transition-colors"
                              title="Remove from universe">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M3 6h18"/>
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                          <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <!-- Empty states -->
        <div x-show="$store.app.filteredStocks.length === 0 && $store.app.stocks.length > 0"
             class="text-center py-6 text-gray-500 text-sm">
          No stocks match your filters
        </div>
        <div x-show="$store.app.stocks.length === 0"
             class="text-center py-6 text-gray-500 text-sm">
          No stocks in universe
        </div>
      </div>
    `;
  }
}

/**
 * Alpine.js component for table interactions
 */
function stockTableComponent() {
  return {
    init() {
      this.$watch('$store.app.minScore', (val) => {
        this.$store.app.minScore = parseFloat(val) || 0;
      });
    }
  };
}

customElements.define('stock-table', StockTable);
