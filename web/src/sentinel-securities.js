import { LitElement, html } from "lit";
import { deleteJson, getJson, postJson, putJson } from "./api.js";
import { formatCurrency, formatPercent } from "./format.js";
import { LiveResource } from "./live-resource.js";

const COLUMN_SETTING_KEY = "ui_securities_table_columns";
const DEFAULT_COLUMNS = [
  "price",
  "security",
  "value",
  "pnl",
  "ideal",
  "deviation",
  "ai_score",
  "opportunity_score",
  "plan",
  "trade",
];

function plainPercent(value, fractionDigits = 1) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(fractionDigits)}%` : "-";
}

function scorePercent(value, fractionDigits = 0) {
  const number = value == null ? Number.NaN : Number(value);
  return Number.isFinite(number)
    ? `${(number * 100).toFixed(fractionDigits)}%`
    : "-";
}

function variantFor(value) {
  const number = Number(value);

  if (number > 0) {
    return "success";
  }

  if (number < 0) {
    return "error";
  }

  return undefined;
}

function recommendationValue(security) {
  const recommendation = security.recommendation;

  if (!recommendation) {
    return 0;
  }

  const direction = recommendation.action === "buy" ? 1 : -1;
  return direction * Math.abs(Number(recommendation.value_delta_eur) || 0);
}

function safeId(symbol) {
  return String(symbol).replaceAll(/[^a-zA-Z0-9_-]/g, "-");
}

class SentinelSecurities extends LitElement {
  static properties = {
    period: { state: true },
    search: { state: true },
    expandedSymbols: { state: true },
    sortColumn: { state: true },
    sortReversed: { state: true },
    busyAction: { state: true },
    message: { state: true },
    errorMessage: { state: true },
    addError: { state: true },
    deleteCandidate: { state: true },
    visibleColumns: { state: true },
    columnsBusy: { state: true },
    activeRowSymbol: { state: true },
    inactiveOnly: { type: Boolean, attribute: "inactive-only" },
    bare: { type: Boolean },
  };

  constructor() {
    super();
    this.period = "1Y";
    this.search = "";
    this.expandedSymbols = new Set();
    this.sortColumn = "ideal";
    this.sortReversed = true;
    this.busyAction = "";
    this.message = "";
    this.errorMessage = "";
    this.addError = "";
    this.deleteCandidate = undefined;
    this.visibleColumns = undefined;
    this.columnsBusy = false;
    this.activeRowSymbol = undefined;
    this.inactiveOnly = false;
    this.bare = false;
    this.securityListChanged = (event) => {
      if (event.target !== this) {
        this.securities.refresh();
      }
    };
  }

  securities = new LiveResource(
    this,
    (signal) =>
      getJson(
        `/api/unified?period=${this.period}${this.inactiveOnly ? "&inactive_only=true" : ""}`,
        { signal },
      ),
    { interval: 60_000 },
  );

  columnSettings = new LiveResource(
    this,
    (signal) => getJson("/api/settings", { signal }),
    { interval: 0 },
  );

  createRenderRoot() {
    return this;
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener(
      "sentinel-security-list-change",
      this.securityListChanged,
    );
    window.addEventListener(
      "sentinel-setting-changed",
      this.refreshForCashSetting,
    );
  }

  disconnectedCallback() {
    window.removeEventListener(
      "sentinel-security-list-change",
      this.securityListChanged,
    );
    window.removeEventListener(
      "sentinel-setting-changed",
      this.refreshForCashSetting,
    );
    super.disconnectedCallback();
  }

  refreshForCashSetting = (event) => {
    if (
      event.detail?.key === "simulated_cash_eur" ||
      event.detail?.key === "trading_mode"
    ) {
      this.securities.refresh();
    }
  };

  get allSecurities() {
    return this.securities.value ?? [];
  }

  get visibleSecurities() {
    const term = this.search.trim().toLowerCase();
    const securities = this.allSecurities.filter((security) => {
      if (!term) {
        return true;
      }

      return [
        security.symbol,
        security.name,
        security.geography,
        security.industry,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term));
    });

    return securities.sort((left, right) => {
      let result;

      switch (this.sortColumn) {
        case "symbol":
          result = String(left.symbol).localeCompare(String(right.symbol));
          break;
        case "value":
          result = Number(left.value_eur || 0) - Number(right.value_eur || 0);
          break;
        case "pnl":
          result = Number(left.profit_pct || 0) - Number(right.profit_pct || 0);
          break;
        case "ideal":
          result =
            Number(left.ideal_allocation || 0) -
            Number(right.ideal_allocation || 0);
          break;
        case "deviation":
          result =
            left.current_allocation -
            left.ideal_allocation -
            (right.current_allocation - right.ideal_allocation);
          break;
        case "ai_score":
          if (
            left.ai_research_multiplier == null ||
            right.ai_research_multiplier == null
          ) {
            return (
              Number(left.ai_research_multiplier == null) -
                Number(right.ai_research_multiplier == null) ||
              String(left.symbol).localeCompare(String(right.symbol))
            );
          }
          result =
            Number(left.ai_research_multiplier) -
            Number(right.ai_research_multiplier);
          break;
        case "opportunity_score":
          result = Number(left.opp_score ?? 0) - Number(right.opp_score ?? 0);
          break;
        case "recommendation":
          result = recommendationValue(left) - recommendationValue(right);
          break;
        default: {
          const leftRank =
            left.recommendation?.execution_rank ?? Number.POSITIVE_INFINITY;
          const rightRank =
            right.recommendation?.execution_rank ?? Number.POSITIVE_INFINITY;
          result =
            leftRank - rightRank ||
            String(left.symbol).localeCompare(String(right.symbol));
        }
      }

      return this.sortReversed ? -result : result;
    });
  }

  get selectedColumns() {
    const configured =
      this.visibleColumns ?? this.columnSettings.value?.[COLUMN_SETTING_KEY];
    let columns = DEFAULT_COLUMNS;

    if (Array.isArray(configured)) {
      // Legacy selections predate these columns. Preserve their hidden
      // columns while showing the additions by default.
      const valid = configured.filter((column) =>
        DEFAULT_COLUMNS.includes(column),
      );
      if (valid.length > 0) {
        columns = [...valid, "deviation", "ai_score", "opportunity_score"];
      }
    } else if (Array.isArray(configured?.hidden)) {
      columns = DEFAULT_COLUMNS.filter(
        (column) => !configured.hidden.includes(column),
      );
    }

    const selected = new Set(columns);
    selected.add("security");
    return selected;
  }

  columnVisible(column) {
    return this.selectedColumns.has(column);
  }

  activateRow(symbol) {
    this.activeRowSymbol = symbol;
  }

  deactivateRow(symbol) {
    if (this.activeRowSymbol === symbol) {
      this.activeRowSymbol = undefined;
    }
  }

  rowFocusOut(event, symbol) {
    if (!event.currentTarget.contains(event.relatedTarget)) {
      this.deactivateRow(symbol);
    }
  }

  headingRowStyle(symbol) {
    if (this.activeRowSymbol !== symbol && !this.expandedSymbols.has(symbol)) {
      return "";
    }

    return "background: var(--wa-color-surface-lowered)";
  }

  get stats() {
    return {
      total: this.allSecurities.length,
      positions: this.allSecurities.filter((security) => security.has_position)
        .length,
      buys: this.allSecurities.filter(
        (security) => security.recommendation?.action === "buy",
      ).length,
      sells: this.allSecurities.filter(
        (security) => security.recommendation?.action === "sell",
      ).length,
    };
  }

  renderColored(value, formatted) {
    const variant = variantFor(value);
    return variant
      ? html`<span data-tone=${variant}>${formatted}</span>`
      : formatted;
  }

  changePeriod(event) {
    this.period = event.currentTarget.value;
    this.securities.refresh();
    this.dispatchEvent(
      new CustomEvent("sentinel-security-period-change", {
        bubbles: true,
        composed: true,
        detail: { period: this.period },
      }),
    );
  }

  changeSearch(event) {
    this.search = event.currentTarget.value;
  }

  changeSort(column) {
    if (this.sortColumn === column) {
      this.sortReversed = !this.sortReversed;
      return;
    }

    this.sortColumn = column;
    this.sortReversed = false;
  }

  sortMarker(column) {
    if (this.sortColumn !== column) {
      return "↕";
    }

    return this.sortReversed ? "↓" : "↑";
  }

  toggleExpanded(symbol) {
    const expanded = new Set(this.expandedSymbols);

    if (expanded.has(symbol)) {
      expanded.delete(symbol);
    } else {
      expanded.add(symbol);
    }

    this.expandedSymbols = expanded;
  }

  toggleAll() {
    const symbols = this.visibleSecurities.map((security) => security.symbol);
    const allExpanded =
      symbols.length > 0 &&
      symbols.every((symbol) => this.expandedSymbols.has(symbol));
    this.expandedSymbols = allExpanded ? new Set() : new Set(symbols);
  }

  updateLocalSecurity(symbol, updates) {
    this.securities.value = this.allSecurities.map((security) =>
      security.symbol === symbol ? { ...security, ...updates } : security,
    );
    this.requestUpdate();
  }

  async updateExecutionControl(event, security, field) {
    const value = event.currentTarget.checked ? 1 : 0;
    const previous = security[field];

    this.errorMessage = "";
    this.message = "";
    this.busyAction = `${field}:${security.symbol}`;
    this.updateLocalSecurity(security.symbol, { [field]: value });

    try {
      await putJson(`/api/securities/${encodeURIComponent(security.symbol)}`, {
        [field]: value,
      });
      const label = {
        allow_buy: "buy permission",
        allow_sell: "sell permission",
        cooldown_enabled: "cool-off periods",
      }[field];
      this.message = `${security.symbol} ${label} updated`;
    } catch (error) {
      this.updateLocalSecurity(security.symbol, { [field]: previous });
      this.errorMessage = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  async saveAliases(security) {
    const input = this.querySelector(`#aliases-${safeId(security.symbol)}`);

    if (!input) {
      return;
    }

    this.busyAction = `aliases:${security.symbol}`;
    this.errorMessage = "";
    this.message = "";

    try {
      await putJson(`/api/securities/${encodeURIComponent(security.symbol)}`, {
        aliases: input.value,
      });
      this.updateLocalSecurity(security.symbol, { aliases: input.value });
      this.message = `${security.symbol} aliases updated`;
    } catch (error) {
      this.errorMessage = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  openAddDialog() {
    this.addError = "";
    this.querySelector("#add-security-dialog").open = true;
  }

  openColumnsDialog() {
    this.errorMessage = "";
    this.querySelector("#columns-dialog").open = true;
  }

  closeColumnsDialog() {
    this.querySelector("#columns-dialog").open = false;
  }

  async toggleColumn(event, column) {
    const previous = this.selectedColumns;
    const next = new Set(previous);

    if (event.currentTarget.checked) {
      next.add(column);
    } else {
      next.delete(column);
    }

    if (next.size === 0) {
      event.currentTarget.checked = true;
      this.errorMessage = "At least one table column must remain visible";
      return;
    }

    const selection = {
      hidden: DEFAULT_COLUMNS.filter((candidate) => !next.has(candidate)),
    };
    this.visibleColumns = selection;
    this.columnsBusy = true;
    this.errorMessage = "";

    try {
      await putJson(`/api/settings/${COLUMN_SETTING_KEY}`, {
        value: selection,
      });
      this.columnSettings.value = {
        ...this.columnSettings.value,
        [COLUMN_SETTING_KEY]: selection,
      };
    } catch (error) {
      this.visibleColumns = {
        hidden: DEFAULT_COLUMNS.filter((candidate) => !previous.has(candidate)),
      };
      this.errorMessage = error.message;
    } finally {
      this.columnsBusy = false;
    }
  }

  closeAddDialog() {
    this.querySelector("#add-security-dialog").open = false;
  }

  async addSecurity(event) {
    event.preventDefault();
    const input = this.querySelector("#add-security-symbol");
    const symbol = input?.value.trim().toUpperCase();

    if (!symbol) {
      this.addError = "Symbol is required";
      return;
    }

    this.busyAction = "add";
    this.addError = "";

    try {
      await postJson("/api/securities", { symbol });
      this.closeAddDialog();
      input.value = "";
      this.message = `${symbol} added`;
      await this.securities.refresh();
    } catch (error) {
      this.addError = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  async openDeleteDialog(security) {
    this.deleteCandidate = security;
    this.errorMessage = "";
    await this.updateComplete;
    this.querySelector("#delete-security-dialog").open = true;
  }

  closeDeleteDialog() {
    this.querySelector("#delete-security-dialog").open = false;
  }

  async deleteSecurity() {
    const security = this.deleteCandidate;

    if (!security) {
      return;
    }

    this.busyAction = `delete:${security.symbol}`;
    this.errorMessage = "";

    try {
      await deleteJson(
        `/api/securities/${encodeURIComponent(security.symbol)}?sell_position=false`,
      );
      this.closeDeleteDialog();
      this.expandedSymbols = new Set(
        [...this.expandedSymbols].filter(
          (symbol) => symbol !== security.symbol,
        ),
      );
      this.message = this.inactiveOnly
        ? `${security.symbol} permanently deleted`
        : `${security.symbol} removed`;
      this.deleteCandidate = undefined;
      await this.securities.refresh();
      this.dispatchEvent(
        new CustomEvent("sentinel-security-list-change", {
          bubbles: true,
          composed: true,
        }),
      );
    } catch (error) {
      this.errorMessage = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  async activateSecurity(security) {
    this.busyAction = `activate:${security.symbol}`;
    this.errorMessage = "";
    this.message = "";

    try {
      await postJson("/api/securities", { symbol: security.symbol });
      this.expandedSymbols = new Set(
        [...this.expandedSymbols].filter(
          (symbol) => symbol !== security.symbol,
        ),
      );
      this.message = `${security.symbol} activated`;
      await this.securities.refresh();
      this.dispatchEvent(
        new CustomEvent("sentinel-security-list-change", {
          bubbles: true,
          composed: true,
        }),
      );
    } catch (error) {
      this.errorMessage = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  renderControls() {
    if (this.inactiveOnly) {
      return "";
    }

    return html`
      <div
        class="sentinel-layout securities-toolbar"
        data-align="center"
        data-justify="between"
        data-wrap
      >
        <div
          class="sentinel-layout securities-filters"
          data-align="center"
          data-wrap
        >
          <div class="sentinel-layout" data-align="center">
            <span class="securities-period-label" aria-hidden="true"
              >Period</span
            >
            <wa-radio-group
              size="xs"
              orientation="horizontal"
              aria-label="Security price period"
              .value=${this.period}
              @change=${this.changePeriod}
            >
              <wa-radio appearance="button" value="1M">1M</wa-radio>
              <wa-radio appearance="button" value="1Y">1Y</wa-radio>
              <wa-radio appearance="button" value="5Y">5Y</wa-radio>
              <wa-radio appearance="button" value="10Y">10Y</wa-radio>
            </wa-radio-group>
          </div>
          <wa-input
            class="securities-search"
            size="xs"
            type="search"
            aria-label="Search securities"
            placeholder="Search securities"
            @input=${this.changeSearch}
          ></wa-input>
        </div>
        <div class="sentinel-layout" data-align="center">
          <wa-button
            size="xs"
            appearance="plain"
            @click=${this.openColumnsDialog}
            >Columns</wa-button
          >
          <wa-button
            size="xs"
            appearance="outlined"
            @click=${this.openAddDialog}
            >Add Security</wa-button
          >
        </div>
      </div>
    `;
  }

  renderStats() {
    if (this.inactiveOnly) {
      return "";
    }

    const stats = this.stats;

    return html`
      <div class="securities-stats">
        ${stats.total} securities&nbsp;·&nbsp;${stats.positions}
        positions&nbsp;·&nbsp;
        <span data-tone="success">${stats.buys} buy signals</span>&nbsp;·&nbsp;
        <span data-tone="error">${stats.sells} sell signals</span>&nbsp;·&nbsp;
        ${this.visibleSecurities.length} shown
      </div>
    `;
  }

  renderSortableHeader(label, column) {
    const ariaSort =
      this.sortColumn === column
        ? this.sortReversed
          ? "descending"
          : "ascending"
        : "none";

    return html`
      <th
        scope="col"
        aria-sort=${ariaSort}
        style="text-align: left; vertical-align: middle"
      >
        <wa-button
          class="security-sort"
          size="xs"
          appearance="plain"
          @click=${() => this.changeSort(column)}
          >${label}<span aria-hidden="true" class="security-sort-marker"
            >${this.sortMarker(column)}</span
          ></wa-button
        >
      </th>
    `;
  }

  renderRecommendation(security) {
    const recommendation = security.recommendation;

    if (!recommendation) {
      return html`<span>-</span>`;
    }

    const variant = recommendation.action === "buy" ? "success" : "error";
    return html`<span data-tone=${variant}
      >${recommendation.action.toUpperCase()}
      ${formatCurrency(Math.abs(recommendation.value_delta_eur), "EUR")}</span
    >`;
  }

  renderPriceSparkline(security) {
    const values = (security.prices ?? [])
      .map((price) => Number(price.close))
      .filter(Number.isFinite);

    if (values.length < 2) {
      return "-";
    }

    const averageCost = Number(security.avg_cost);
    const hasAverageCost = Boolean(security.has_position) && averageCost > 0;
    const scaleValues = hasAverageCost ? [...values, averageCost] : values;
    const minimum = Math.min(...scaleValues);
    const maximum = Math.max(...scaleValues);
    const label = hasAverageCost
      ? `${security.symbol} price history; green above and red below average purchase price`
      : `${security.symbol} price history; no position`;

    return html`<sentinel-chart
      role="img"
      compact
      aria-label=${label}
      min=${minimum}
      max=${maximum}
      threshold=${hasAverageCost ? averageCost : ""}
      .values=${values}
    ></sentinel-chart>`;
  }

  renderSecurityRow(security) {
    const expanded = this.expandedSymbols.has(security.symbol);
    const detailsId = `security-${safeId(security.symbol)}-details`;
    const allocationChange =
      Math.abs(security.post_plan_allocation - security.current_allocation) >
      0.5;
    const idealDifference =
      security.ideal_allocation - security.current_allocation;

    return html`
      <tr
        style=${this.headingRowStyle(security.symbol)}
        @mouseenter=${() => this.activateRow(security.symbol)}
        @mouseleave=${() => this.deactivateRow(security.symbol)}
        @focusin=${() => this.activateRow(security.symbol)}
        @focusout=${(event) => this.rowFocusOut(event, security.symbol)}
      >
        <td style="vertical-align: middle">
          ${expanded
            ? html`<wa-button
                class="security-expand"
                size="xs"
                appearance="plain"
                aria-label="Collapse ${security.symbol}"
                aria-expanded="true"
                aria-controls=${detailsId}
                @click=${() => this.toggleExpanded(security.symbol)}
                >−</wa-button
              >`
            : html`<wa-button
                class="security-expand"
                size="xs"
                appearance="plain"
                aria-label="Expand ${security.symbol}"
                aria-expanded="false"
                aria-controls=${detailsId}
                @click=${() => this.toggleExpanded(security.symbol)}
                >+</wa-button
              >`}
        </td>
        ${this.columnVisible("price")
          ? html`<td style="vertical-align: middle; white-space: nowrap">
              ${this.renderPriceSparkline(security)}
            </td>`
          : ""}
        <th
          scope="row"
          style="font: inherit; text-align: left; vertical-align: middle; overflow-wrap: anywhere"
        >
          ${security.price_warning
            ? html`<span data-tone="warning">!&nbsp;</span>`
            : ""}<span class="security-symbol" style="white-space: nowrap"
            >${security.symbol}</span
          >
        </th>
        ${this.columnVisible("value")
          ? html`<td
              style="text-align: left; vertical-align: middle; overflow-wrap: anywhere"
            >
              ${security.has_position
                ? formatCurrency(security.value_eur, "EUR", 0)
                : "-"}
            </td>`
          : ""}
        ${this.columnVisible("pnl")
          ? html`<td
              style="text-align: left; vertical-align: middle; overflow-wrap: anywhere"
            >
              ${security.has_position
                ? html`${this.renderColored(
                    security.profit_pct,
                    formatPercent(security.profit_pct, 1),
                  )}&nbsp;${this.renderColored(
                    security.profit_value_eur,
                    formatCurrency(security.profit_value_eur, "EUR", 0),
                  )}`
                : "-"}
            </td>`
          : ""}
        ${this.columnVisible("ideal")
          ? html`<td style="text-align: left; vertical-align: middle">
              ${this.renderColored(
                idealDifference,
                plainPercent(security.ideal_allocation),
              )}
            </td>`
          : ""}
        ${this.columnVisible("deviation")
          ? html`<td
              title="Current allocation minus ideal allocation; negative means underweight and positive means overweight"
              style="text-align: left; vertical-align: middle; white-space: nowrap"
            >
              ${formatPercent(-idealDifference, 1).replace("%", " pp")}
            </td>`
          : ""}
        ${this.columnVisible("ai_score")
          ? html`<td
              title="AI research rating: 0% avoid, 50% neutral, 100% prefer"
              style="text-align: left; vertical-align: middle; white-space: nowrap"
            >
              ${scorePercent(security.ai_research_multiplier, 1)}
            </td>`
          : ""}
        ${this.columnVisible("opportunity_score")
          ? html`<td
              title="Effective opportunity score after recent-dip memory and optional forecast adjustment"
              style="text-align: left; vertical-align: middle; white-space: nowrap"
            >
              ${scorePercent(security.opp_score, 1)}
            </td>`
          : ""}
        ${this.columnVisible("plan")
          ? html`<td
              style="text-align: left; vertical-align: middle; overflow-wrap: anywhere"
            >
              ${plainPercent(security.current_allocation)}
              ${allocationChange
                ? html`&nbsp;→&nbsp;${this.renderColored(
                    security.post_plan_allocation - security.current_allocation,
                    plainPercent(security.post_plan_allocation),
                  )}`
                : ""}
              <span>${this.renderRecommendation(security)}</span>
            </td>`
          : ""}
        ${this.columnVisible("trade")
          ? html`<td
              style="text-align: left; vertical-align: middle; white-space: nowrap"
            >
              ${this.inactiveOnly
                ? "Inactive"
                : html`<span class="trade-permissions"
                    ><wa-switch
                      size="xs"
                      aria-label="Allow buying ${security.symbol}"
                      .checked=${security.allow_buy === 1}
                      @change=${(event) =>
                        this.updateExecutionControl(
                          event,
                          security,
                          "allow_buy",
                        )}
                      >B</wa-switch
                    ><wa-switch
                      size="xs"
                      aria-label="Allow selling ${security.symbol}"
                      .checked=${security.allow_sell === 1}
                      @change=${(event) =>
                        this.updateExecutionControl(
                          event,
                          security,
                          "allow_sell",
                        )}
                      >S</wa-switch
                    ></span
                  >`}
            </td>`
          : ""}
      </tr>
      ${expanded ? this.renderExpandedRow(security, detailsId) : ""}
    `;
  }

  renderDetail(label, value) {
    return html`
      <div class="security-detail-field">
        <dt>${label}</dt>
        <dd>${value}</dd>
      </div>
    `;
  }

  renderPriceChart(security) {
    const values = (security.prices ?? [])
      .map((price) => Number(price.close))
      .filter(Number.isFinite);

    if (values.length < 2) {
      return html`<div>No price data</div>`;
    }

    const averageCost = Number(security.avg_cost);
    const hasAverageCost = Boolean(security.has_position) && averageCost > 0;
    const scaleValues = hasAverageCost ? [...values, averageCost] : values;

    return html`<sentinel-chart
      role="img"
      aria-label="${security.symbol} price history"
      height="6"
      min=${Math.min(...scaleValues)}
      max=${Math.max(...scaleValues)}
      threshold=${hasAverageCost ? averageCost : ""}
      .values=${values}
    ></sentinel-chart>`;
  }

  renderExpandedRow(security, detailsId) {
    const aliasBusy = this.busyAction === `aliases:${security.symbol}`;
    const multiplier =
      security.ai_research_multiplier == null
        ? Number.NaN
        : Number(security.ai_research_multiplier);

    return html`
      <tr id=${detailsId}>
        <td colspan=${this.selectedColumns.size + 1}>
          <wa-card
            class="security-details-panel"
            role="region"
            aria-label="${security.symbol} details"
          >
            ${this.renderPriceChart(security)}
            <dl class="security-detail-list">
              ${security.price_warning
                ? this.renderDetail(
                    "Warning",
                    html`<span data-tone="warning"
                      >${security.price_warning}</span
                    >`,
                  )
                : ""}
              ${this.renderDetail("Name", security.name || "-")}
              ${this.renderDetail("Geography", security.geography || "-")}
              ${this.renderDetail("Industry", security.industry || "-")}
              ${this.renderDetail("Lot", security.min_lot ?? "-")}
              ${this.renderDetail("Quantity", security.quantity ?? 0)}
              ${this.renderDetail(
                "Cool-off periods",
                html`<wa-switch
                  size="small"
                  aria-label="Cool-off periods for ${security.symbol}"
                  title="Apply global same-side and opposite-side cool-off periods to this security"
                  .checked=${security.cooldown_enabled !== 0}
                  ?disabled=${this.busyAction ===
                  `cooldown_enabled:${security.symbol}`}
                  @change=${(event) =>
                    this.updateExecutionControl(
                      event,
                      security,
                      "cooldown_enabled",
                    )}
                  >Enabled</wa-switch
                >`,
              )}
              ${this.renderDetail(
                "Price",
                formatCurrency(security.current_price, security.currency),
              )}
              ${this.renderDetail(
                "Aliases",
                html`<div class="sentinel-layout" data-align="center" data-wrap>
                  <wa-input
                    size="small"
                    id="aliases-${safeId(security.symbol)}"
                    aria-label="Aliases for ${security.symbol}"
                    .value=${security.aliases ?? ""}
                    style="inline-size: 28ch; max-inline-size: 100%"
                  ></wa-input>
                  <wa-button
                    size="small"
                    ?disabled=${aliasBusy}
                    @click=${() => this.saveAliases(security)}
                    >Save aliases</wa-button
                  >
                </div>`,
              )}
              ${this.renderDetail(
                "Forecast 4w",
                this.renderColored(
                  security.forecast_return_4w,
                  scorePercent(security.forecast_return_4w, 1),
                ),
              )}
              ${this.renderDetail(
                "Timing",
                scorePercent(security.forecast_score),
              )}
              ${this.renderDetail(
                "AI research",
                Number.isFinite(multiplier) ? multiplier.toFixed(2) : "-",
              )}
              ${security.ai_research_multiplier_source
                ? this.renderDetail(
                    "Source",
                    security.ai_research_multiplier_source,
                  )
                : ""}
              ${security.ai_research_multiplier_updated_at
                ? this.renderDetail(
                    "Updated",
                    new Date(
                      security.ai_research_multiplier_updated_at,
                    ).toLocaleString(),
                  )
                : ""}
              ${security.ai_research_multiplier_analysis
                ? this.renderDetail(
                    "Analysis",
                    security.ai_research_multiplier_analysis,
                  )
                : ""}
              ${this.renderDetail(
                "Opportunity",
                scorePercent(security.opp_score, 1),
              )}
              ${this.renderDetail("Dip", scorePercent(security.dip_score, 1))}
              ${this.renderDetail(
                "Capitulation",
                scorePercent(security.capitulation_score, 1),
              )}
              ${this.renderDetail(
                "Cycle turn",
                security.cycle_turn ? "yes" : "no",
              )}
              ${this.renderDetail(
                "Freefall blocked",
                security.freefall_block ? "yes" : "no",
              )}
              ${security.recommendation?.reason
                ? this.renderDetail("Plan", security.recommendation.reason)
                : ""}
              ${this.renderDetail(
                "Actions",
                this.inactiveOnly
                  ? html`<div
                      class="sentinel-layout"
                      data-align="center"
                      data-wrap
                    >
                      <wa-button
                        size="small"
                        ?disabled=${this.busyAction ===
                        `activate:${security.symbol}`}
                        @click=${() => this.activateSecurity(security)}
                        >Activate</wa-button
                      ><wa-button
                        size="small"
                        variant="danger"
                        title=${security.can_delete
                          ? "Permanently delete unused security"
                          : `Cannot delete: ${security.transaction_count || 0} historical transaction(s)`}
                        ?disabled=${!security.can_delete}
                        @click=${() => this.openDeleteDialog(security)}
                        >Delete Permanently</wa-button
                      >
                    </div>`
                  : html`<wa-button
                      size="small"
                      variant="danger"
                      @click=${() => this.openDeleteDialog(security)}
                      >Remove</wa-button
                    >`,
              )}
              ${this.inactiveOnly && !security.can_delete
                ? this.renderDetail(
                    "Deletion",
                    `Permanent deletion is unavailable because this security has ${security.transaction_count || 0} historical transaction(s).`,
                  )
                : ""}
            </dl>
          </wa-card>
        </td>
      </tr>
    `;
  }

  renderTable() {
    const visible = this.visibleSecurities;
    const allExpanded =
      visible.length > 0 &&
      visible.every((security) => this.expandedSymbols.has(security.symbol));

    if (visible.length === 0) {
      return html`<div>No securities match the current controls</div>`;
    }

    return html`
      <div class="securities-table-scroll">
        <table
          class="securities-table"
          aria-label=${this.inactiveOnly ? "Inactive Securities" : "Securities"}
          style="width: 100%; min-width: max-content; border-spacing: 0"
        >
          <thead>
            <tr>
              <th scope="col" style="text-align: left; vertical-align: middle">
                ${allExpanded
                  ? html`<wa-button
                      class="security-expand"
                      size="xs"
                      appearance="plain"
                      aria-label="Collapse all securities"
                      @click=${this.toggleAll}
                      >−</wa-button
                    >`
                  : html`<wa-button
                      class="security-expand"
                      size="xs"
                      appearance="plain"
                      aria-label="Expand all securities"
                      @click=${this.toggleAll}
                      >+</wa-button
                    >`}
              </th>
              ${this.columnVisible("price")
                ? html`<th
                    scope="col"
                    style="text-align: left; vertical-align: middle"
                  >
                    Price
                  </th>`
                : ""}
              ${this.renderSortableHeader("Security", "symbol")}
              ${this.columnVisible("value")
                ? this.renderSortableHeader("Value", "value")
                : ""}
              ${this.columnVisible("pnl")
                ? this.renderSortableHeader("P/L", "pnl")
                : ""}
              ${this.columnVisible("ideal")
                ? this.renderSortableHeader("Ideal", "ideal")
                : ""}
              ${this.columnVisible("deviation")
                ? this.renderSortableHeader("Deviation from ideal", "deviation")
                : ""}
              ${this.columnVisible("ai_score")
                ? this.renderSortableHeader("AI score", "ai_score")
                : ""}
              ${this.columnVisible("opportunity_score")
                ? this.renderSortableHeader(
                    "Opportunity score",
                    "opportunity_score",
                  )
                : ""}
              ${this.columnVisible("plan")
                ? this.renderSortableHeader("Plan", "recommendation")
                : ""}
              ${this.columnVisible("trade")
                ? html`<th
                    scope="col"
                    style="text-align: left; vertical-align: middle"
                  >
                    <span aria-hidden="true"></span>${this.inactiveOnly
                      ? "Status"
                      : "Trade"}
                  </th>`
                : ""}
            </tr>
          </thead>
          <tbody>
            ${visible.map((security) => this.renderSecurityRow(security))}
          </tbody>
        </table>
      </div>
    `;
  }

  renderColumnsDialog() {
    return html`
      <wa-dialog
        class="sentinel-compact-dialog"
        id="columns-dialog"
        label="Columns"
      >
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("price")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "price")}
            >Price</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            checked
            disabled
            aria-label="Security column is always visible"
            >Security</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("value")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "value")}
            >Value</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("pnl")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "pnl")}
            >P/L</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("ideal")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "ideal")}
            >Ideal</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("deviation")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "deviation")}
            >Deviation from ideal</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("ai_score")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "ai_score")}
            >AI score</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("opportunity_score")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "opportunity_score")}
            >Opportunity score</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("plan")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "plan")}
            >Plan</wa-switch
          >
        </div>
        <div>
          <wa-switch
            size="small"
            .checked=${this.columnVisible("trade")}
            ?disabled=${this.columnsBusy}
            @change=${(event) => this.toggleColumn(event, "trade")}
            >Trade</wa-switch
          >
        </div>
        ${this.errorMessage
          ? html`<div>
              <span data-tone="error">${this.errorMessage}</span>
            </div>`
          : ""}
        <div>
          <wa-button size="small" @click=${this.closeColumnsDialog}
            >Done</wa-button
          >
        </div>
      </wa-dialog>
    `;
  }

  renderAddDialog() {
    return html`
      <wa-dialog
        class="sentinel-compact-dialog"
        id="add-security-dialog"
        label="Add Security"
      >
        <form @submit=${this.addSecurity}>
          <label>
            Symbol&nbsp;<wa-input
              size="small"
              id="add-security-symbol"
              aria-label="TraderNet security symbol"
              placeholder="AAPL.US"
              required
              ?disabled=${this.busyAction === "add"}
            ></wa-input>
          </label>
          <div>
            Geography and industry will be filled by the next metadata sync.
          </div>
          ${this.addError
            ? html`<div><span data-tone="error">${this.addError}</span></div>`
            : ""}
          <div>
            <wa-button
              size="small"
              type="submit"
              ?disabled=${this.busyAction === "add"}
              >Add Security</wa-button
            >&nbsp;
            <wa-button
              size="small"
              type="button"
              ?disabled=${this.busyAction === "add"}
              @click=${this.closeAddDialog}
              >Cancel</wa-button
            >
          </div>
        </form>
      </wa-dialog>
    `;
  }

  renderDeleteDialog() {
    const security = this.deleteCandidate;

    return html`
      <wa-dialog
        class="sentinel-compact-dialog"
        id="delete-security-dialog"
        label=${this.inactiveOnly
          ? "Delete Security Permanently"
          : "Remove Security"}
      >
        ${security
          ? html`
              <div>
                ${this.inactiveOnly
                  ? `Permanently delete ${security.symbol}?`
                  : `Remove ${security.symbol} from the active universe?`}
              </div>
              ${security.has_position
                ? html`<div>
                    <span data-tone="warning"
                      >Position: ${security.quantity} shares
                      (${formatCurrency(security.value_eur, "EUR")}). It will
                      remain managed, but new buys will be disabled.</span
                    >
                  </div>`
                : ""}
              ${this.errorMessage
                ? html`<div>
                    <span data-tone="error">${this.errorMessage}</span>
                  </div>`
                : ""}
              <div>
                <wa-button
                  size="small"
                  variant="danger"
                  ?disabled=${this.busyAction === `delete:${security.symbol}`}
                  @click=${this.deleteSecurity}
                  >${this.inactiveOnly
                    ? "Delete Permanently"
                    : "Remove"}</wa-button
                >&nbsp;
                <wa-button
                  size="small"
                  ?disabled=${this.busyAction === `delete:${security.symbol}`}
                  @click=${this.closeDeleteDialog}
                  >Cancel</wa-button
                >
              </div>
            `
          : ""}
      </wa-dialog>
    `;
  }

  render() {
    let content;

    if (this.securities.loading && !this.securities.value) {
      content = html`<span>Loading securities…</span>`;
    } else if (this.securities.error) {
      content = html`<span data-tone="error"
        >Securities unavailable: ${this.securities.error.message}</span
      >`;
    } else {
      content = html`
        ${this.renderControls()} ${this.renderStats()}
        ${this.message
          ? html`<div><span data-tone="success">${this.message}</span></div>`
          : ""}
        ${this.errorMessage
          ? html`<div><span data-tone="error">${this.errorMessage}</span></div>`
          : ""}
        ${this.renderTable()}
      `;
    }

    return html`
      ${this.bare
        ? content
        : html`<wa-card
            ><span slot="header"
              >${this.inactiveOnly ? "Inactive Securities" : "Securities"}</span
            >${content}</wa-card
          >`}
      ${this.inactiveOnly
        ? ""
        : html`${this.renderColumnsDialog()} ${this.renderAddDialog()}`}
      ${this.renderDeleteDialog()}
    `;
  }
}

customElements.define("sentinel-securities", SentinelSecurities);
