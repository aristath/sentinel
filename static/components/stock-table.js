/**
 * Stock Table Component
 * Displays the stock universe with filtering, sorting, and position data
 */
class StockTable extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="card" x-data="stockTableComponent()">
        <div class="card__header">
          <h2 class="card__title">Stock Universe</h2>
          <button @click="$store.app.showAddStockModal = true"
                  class="btn btn--success btn--sm">
            + Add Stock
          </button>
        </div>

        <!-- Filter Bar -->
        <div class="stock-filters">
          <div class="stock-filters__search">
            <input type="text"
                   x-model="$store.app.searchQuery"
                   placeholder="Search symbol or name..."
                   class="input input--sm">
          </div>
          <div class="stock-filters__dropdowns">
            <select x-model="$store.app.stockFilter" class="select">
              <option value="all">All Regions</option>
              <option value="EU">EU</option>
              <option value="ASIA">Asia</option>
              <option value="US">US</option>
            </select>
            <select x-model="$store.app.industryFilter" class="select">
              <option value="all">All Sectors</option>
              <template x-for="ind in $store.app.industries" :key="ind">
                <option :value="ind" x-text="ind"></option>
              </template>
            </select>
            <select x-model="$store.app.minScore" class="select">
              <option value="0">Any Score</option>
              <option value="0.3">Score >= 0.3</option>
              <option value="0.5">Score >= 0.5</option>
              <option value="0.7">Score >= 0.7</option>
            </select>
          </div>
        </div>

        <!-- Results count -->
        <div class="stock-filters__count" x-show="$store.app.stocks.length > 0">
          <span x-text="$store.app.filteredStocks.length"></span> of
          <span x-text="$store.app.stocks.length"></span> stocks
        </div>

        <div class="overflow-x">
          <table class="table">
            <thead class="table__head">
              <tr>
                <th @click="$store.app.sortStocks('symbol')"
                    class="table__col--sortable">
                  Symbol
                  <span class="sort-indicator" x-show="$store.app.sortBy === 'symbol'"
                        x-text="$store.app.sortDesc ? '\\u25BC' : '\\u25B2'"></span>
                </th>
                <th @click="$store.app.sortStocks('name')"
                    class="table__col--sortable">
                  Company
                  <span class="sort-indicator" x-show="$store.app.sortBy === 'name'"
                        x-text="$store.app.sortDesc ? '\\u25BC' : '\\u25B2'"></span>
                </th>
                <th @click="$store.app.sortStocks('geography')"
                    class="table__col--sortable table__col--center">
                  Region
                  <span class="sort-indicator" x-show="$store.app.sortBy === 'geography'"
                        x-text="$store.app.sortDesc ? '\\u25BC' : '\\u25B2'"></span>
                </th>
                <th @click="$store.app.sortStocks('industry')"
                    class="table__col--sortable">
                  Sector
                  <span class="sort-indicator" x-show="$store.app.sortBy === 'industry'"
                        x-text="$store.app.sortDesc ? '\\u25BC' : '\\u25B2'"></span>
                </th>
                <th @click="$store.app.sortStocks('current_price')"
                    class="table__col--sortable table__col--right">
                  Price
                  <span class="sort-indicator" x-show="$store.app.sortBy === 'current_price'"
                        x-text="$store.app.sortDesc ? '\\u25BC' : '\\u25B2'"></span>
                </th>
                <th @click="$store.app.sortStocks('shares')"
                    class="table__col--sortable table__col--right">
                  Shares
                  <span class="sort-indicator" x-show="$store.app.sortBy === 'shares'"
                        x-text="$store.app.sortDesc ? '\\u25BC' : '\\u25B2'"></span>
                </th>
                <th @click="$store.app.sortStocks('position_value')"
                    class="table__col--sortable table__col--right">
                  Value
                  <span class="sort-indicator" x-show="$store.app.sortBy === 'position_value'"
                        x-text="$store.app.sortDesc ? '\\u25BC' : '\\u25B2'"></span>
                </th>
                <th @click="$store.app.sortStocks('total_score')"
                    class="table__col--sortable table__col--right">
                  Score
                  <span class="sort-indicator" x-show="$store.app.sortBy === 'total_score'"
                        x-text="$store.app.sortDesc ? '\\u25BC' : '\\u25B2'"></span>
                </th>
                <th class="table__col--center">Actions</th>
              </tr>
            </thead>
            <tbody class="table__body">
              <template x-for="stock in $store.app.filteredStocks" :key="stock.symbol">
                <tr>
                  <td class="table__col--mono" x-text="stock.symbol"></td>
                  <td class="table__col--truncate" x-text="stock.name"></td>
                  <td class="table__col--center">
                    <span class="tag" :class="getGeoTagClass(stock.geography)" x-text="stock.geography"></span>
                  </td>
                  <td class="table__col--muted table__col--truncate" x-text="stock.industry || '-'"></td>
                  <td class="table__col--right table__col--mono"
                      x-text="stock.current_price ? formatCurrency(stock.current_price) : '-'"></td>
                  <td class="table__col--right"
                      x-text="stock.shares || '-'"></td>
                  <td class="table__col--right table__col--mono"
                      :class="stock.position_value ? 'table__col--value' : ''"
                      x-text="stock.position_value ? formatCurrency(stock.position_value) : '-'"></td>
                  <td class="table__col--right">
                    <span class="score" :class="getScoreClass(stock.total_score)"
                          x-text="formatScore(stock.total_score)"></span>
                  </td>
                  <td class="table__col--center">
                    <div class="table-actions">
                      <button @click="$store.app.openEditStock(stock)"
                              class="action-icon action-icon--secondary"
                              title="Edit stock">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                      </button>
                      <button @click="$store.app.refreshSingleScore(stock.symbol)"
                              class="action-icon action-icon--primary"
                              title="Refresh score">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M21 2v6h-6"/>
                          <path d="M3 12a9 9 0 0 1 15-6.7L21 8"/>
                          <path d="M3 22v-6h6"/>
                          <path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>
                        </svg>
                      </button>
                      <button @click="$store.app.removeStock(stock.symbol)"
                              class="action-icon action-icon--danger"
                              title="Remove from universe">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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

        <!-- Empty state -->
        <div x-show="$store.app.filteredStocks.length === 0 && $store.app.stocks.length > 0"
             class="empty-state">
          No stocks match your filters
        </div>
        <div x-show="$store.app.stocks.length === 0"
             class="empty-state">
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
      // Convert minScore to number on change
      this.$watch('$store.app.minScore', (val) => {
        this.$store.app.minScore = parseFloat(val) || 0;
      });
    }
  };
}

customElements.define('stock-table', StockTable);
