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
  "plan",
  "trade",
];

function plainPercent(value, fractionDigits = 1) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(fractionDigits)}%` : "-";
}

function scorePercent(value, fractionDigits = 0) {
  const number = Number(value);
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
  }

  disconnectedCallback() {
    window.removeEventListener(
      "sentinel-security-list-change",
      this.securityListChanged,
    );
    super.disconnectedCallback();
  }

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
    const valid = Array.isArray(configured)
      ? configured.filter((column) => DEFAULT_COLUMNS.includes(column))
      : [];

    const selected = new Set(valid.length > 0 ? valid : DEFAULT_COLUMNS);
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

    return [
      "background:light-dark(black,white)",
      "color:light-dark(white,black)",
      "--tui-color:light-dark(white,black)",
      "--tui-background:light-dark(black,white)",
      "--tui-success-color:light-dark(white,black)",
      "--tui-warning-color:light-dark(white,black)",
      "--tui-error-color:light-dark(white,black)",
    ].join(";");
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
      ? html`<tui-text variant=${variant}>${formatted}</tui-text>`
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

  async updatePermission(event, security, field) {
    const value = event.currentTarget.checked ? 1 : 0;
    const previous = security[field];

    this.errorMessage = "";
    this.message = "";
    this.updateLocalSecurity(security.symbol, { [field]: value });

    try {
      await putJson(`/api/securities/${encodeURIComponent(security.symbol)}`, {
        [field]: value,
      });
      this.message = `${security.symbol} ${field === "allow_buy" ? "buy" : "sell"} permission updated`;
    } catch (error) {
      this.updateLocalSecurity(security.symbol, { [field]: previous });
      this.errorMessage = error.message;
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
    this.querySelector("#add-security-dialog")?.showModal();
  }

  openColumnsDialog() {
    this.errorMessage = "";
    this.querySelector("#columns-dialog")?.showModal();
  }

  closeColumnsDialog() {
    this.querySelector("#columns-dialog")?.close();
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
      event.currentTarget.setAttribute("checked", "");
      this.errorMessage = "At least one table column must remain visible";
      return;
    }

    const ordered = DEFAULT_COLUMNS.filter((candidate) => next.has(candidate));
    this.visibleColumns = ordered;
    this.columnsBusy = true;
    this.errorMessage = "";

    try {
      await putJson(`/api/settings/${COLUMN_SETTING_KEY}`, { value: ordered });
      this.columnSettings.value = {
        ...this.columnSettings.value,
        [COLUMN_SETTING_KEY]: ordered,
      };
    } catch (error) {
      this.visibleColumns = [...previous];
      this.errorMessage = error.message;
    } finally {
      this.columnsBusy = false;
    }
  }

  closeAddDialog() {
    this.querySelector("#add-security-dialog")?.close();
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
    this.querySelector("#delete-security-dialog")?.showModal();
  }

  closeDeleteDialog() {
    this.querySelector("#delete-security-dialog")?.close();
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
      <tui-flex align="baseline" wrap>
        <span>Period&nbsp;</span>
        <tui-radio-buttonset
          aria-label="Security price period"
          value=${this.period}
          @change=${this.changePeriod}
        >
          <tui-radio-button value="1M">1M</tui-radio-button>
          <tui-radio-button value="1Y">1Y</tui-radio-button>
          <tui-radio-button value="5Y">5Y</tui-radio-button>
          <tui-radio-button value="10Y">10Y</tui-radio-button>
        </tui-radio-buttonset>
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <label>
          Search&nbsp;<tui-input
            type="search"
            aria-label="Search securities"
            placeholder="symbol or name"
            size="14"
            @input=${this.changeSearch}
          ></tui-input>
        </label>
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <tui-button @click=${this.openColumnsDialog}>Columns</tui-button>
        <span aria-hidden="true">&nbsp;│&nbsp;</span>
        <tui-button @click=${this.openAddDialog}>Add Security</tui-button>
      </tui-flex>
    `;
  }

  renderStats() {
    if (this.inactiveOnly) {
      return "";
    }

    const stats = this.stats;

    return html`
      <div>
        ${stats.total} securities&nbsp;│&nbsp;${stats.positions}
        positions&nbsp;│&nbsp;
        <tui-text variant="success">${stats.buys} buy signals</tui-text
        >&nbsp;│&nbsp;
        <tui-text variant="error">${stats.sells} sell signals</tui-text
        >&nbsp;│&nbsp; ${this.visibleSecurities.length} shown
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
        style="text-align: left; vertical-align: top"
      >
        <span aria-hidden="true">│&nbsp;</span
        ><tui-button @click=${() => this.changeSort(column)}
          >${label}</tui-button
        ><span aria-hidden="true">${this.sortMarker(column)}</span>
      </th>
    `;
  }

  renderRecommendation(security) {
    const recommendation = security.recommendation;

    if (!recommendation) {
      return html`<span>-</span>`;
    }

    const variant = recommendation.action === "buy" ? "success" : "error";
    return html`<tui-text variant=${variant}
      >${recommendation.action.toUpperCase()}
      ${formatCurrency(Math.abs(recommendation.value_delta_eur), "EUR")}</tui-text
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

    return html`<tui-sparkline
      aria-label=${label}
      columns="8"
      min=${minimum}
      max=${maximum}
      threshold=${hasAverageCost ? averageCost : ""}
      above-variant=${hasAverageCost ? "success" : ""}
      below-variant=${hasAverageCost ? "error" : ""}
      .values=${values}
    ></tui-sparkline>`;
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
        <td style="vertical-align: top">
          ${
            expanded
              ? html`<tui-button
                  aria-label="Collapse ${security.symbol}"
                  aria-expanded="true"
                  aria-controls=${detailsId}
                  @click=${() => this.toggleExpanded(security.symbol)}
                  >−</tui-button
                >`
              : html`<tui-button
                  aria-label="Expand ${security.symbol}"
                  aria-expanded="false"
                  aria-controls=${detailsId}
                  @click=${() => this.toggleExpanded(security.symbol)}
                  >+</tui-button
                >`
          }
        </td>
        ${
          this.columnVisible("price")
            ? html`<td style="vertical-align: top; white-space: nowrap">
                <span aria-hidden="true">│&nbsp;</span>
                ${this.renderPriceSparkline(security)}
              </td>`
            : ""
        }
        <th
          scope="row"
          style="font: inherit; text-align: left; vertical-align: top; overflow-wrap: anywhere"
        >
          <span aria-hidden="true">│&nbsp;</span>
          ${security.price_warning ? html`<tui-text variant="warning">!&nbsp;</tui-text>` : ""}<span
            style="white-space: nowrap"
            >${security.symbol}</span
          >
        </th>
        ${
          this.columnVisible("value")
            ? html`<td
                style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
              >
                <span aria-hidden="true">│&nbsp;</span>
                ${security.has_position ? formatCurrency(security.value_eur, "EUR", 0) : "-"}
              </td>`
            : ""
        }
        ${
          this.columnVisible("pnl")
            ? html`<td
                style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
              >
                <span aria-hidden="true">│&nbsp;</span>
                ${
                  security.has_position
                    ? html`${this.renderColored(
                        security.profit_pct,
                        formatPercent(security.profit_pct, 1),
                      )}&nbsp;${this.renderColored(
                        security.profit_value_eur,
                        formatCurrency(security.profit_value_eur, "EUR", 0),
                      )}`
                    : "-"
                }
              </td>`
            : ""
        }
        ${
          this.columnVisible("ideal")
            ? html`<td style="text-align: left; vertical-align: top">
                <span aria-hidden="true">│&nbsp;</span>
                ${this.renderColored(
                  idealDifference,
                  plainPercent(security.ideal_allocation),
                )}
              </td>`
            : ""
        }
        ${
          this.columnVisible("plan")
            ? html`<td
                style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
              >
                <span aria-hidden="true">│&nbsp;</span>
                ${plainPercent(security.current_allocation)}
                ${
                  allocationChange
                    ? html`&nbsp;→&nbsp;${this.renderColored(
                        security.post_plan_allocation -
                          security.current_allocation,
                        plainPercent(security.post_plan_allocation),
                      )}`
                    : ""
                }
                <div>${this.renderRecommendation(security)}</div>
              </td>`
            : ""
        }
        ${
          this.columnVisible("trade")
            ? html`<td
                style="text-align: left; vertical-align: top; white-space: nowrap"
              >
                <span aria-hidden="true">│&nbsp;</span>
                ${
                  this.inactiveOnly
                    ? "Inactive"
                    : html`<tui-toggle
                          aria-label="Allow buying ${security.symbol}"
                          ?checked=${security.allow_buy === 1}
                          @change=${(event) =>
                            this.updatePermission(
                              event,
                              security,
                              "allow_buy",
                            )}
                          >B</tui-toggle
                        >&nbsp;<tui-toggle
                          aria-label="Allow selling ${security.symbol}"
                          ?checked=${security.allow_sell === 1}
                          @change=${(event) =>
                            this.updatePermission(
                              event,
                              security,
                              "allow_sell",
                            )}
                          >S</tui-toggle
                        >`
                }
              </td>`
            : ""
        }
      </tr>
      ${expanded ? this.renderExpandedRow(security, detailsId) : ""}
    `;
  }

  renderDetailRow(label, value) {
    return html`
      <tr>
        <th
          scope="row"
          style="font: inherit; text-align: left; vertical-align: top; white-space: nowrap; padding-right: 1ch"
        >
          ${label}
        </th>
        <td
          style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
        >
          <span aria-hidden="true">│&nbsp;</span>${value}
        </td>
      </tr>
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

    return html`<tui-chart
      aria-label="${security.symbol} price history"
      height="6"
      min=${Math.min(...scaleValues)}
      max=${Math.max(...scaleValues)}
      threshold=${hasAverageCost ? averageCost : ""}
      above-variant=${hasAverageCost ? "success" : ""}
      below-variant=${hasAverageCost ? "error" : ""}
      .values=${values}
    ></tui-chart>`;
  }

  renderExpandedRow(security, detailsId) {
    const aliasBusy = this.busyAction === `aliases:${security.symbol}`;
    const multiplier = Number(security.ai_research_multiplier);

    return html`
      <tr id=${detailsId}>
        <td
          colspan=${this.selectedColumns.size + 1}
          style="overflow-wrap: anywhere"
        >
          <tui-box border="single" aria-label="${security.symbol} details">
            ${this.renderPriceChart(security)}
            <table style="width: 100%; border-spacing: 0">
              <tbody>
                ${
                  security.price_warning
                    ? this.renderDetailRow(
                        "Warning",
                        html`<tui-text variant="warning"
                          >${security.price_warning}</tui-text
                        >`,
                      )
                    : ""
                }
                ${this.renderDetailRow("Name", security.name || "-")}
                ${this.renderDetailRow("Geography", security.geography || "-")}
                ${this.renderDetailRow("Industry", security.industry || "-")}
                ${this.renderDetailRow("Lot", security.min_lot ?? "-")}
                ${this.renderDetailRow("Quantity", security.quantity ?? 0)}
                ${this.renderDetailRow(
                  "Price",
                  formatCurrency(security.current_price, security.currency),
                )}
                ${this.renderDetailRow(
                  "Aliases",
                  html`<tui-input
                      id="aliases-${safeId(security.symbol)}"
                      aria-label="Aliases for ${security.symbol}"
                      value=${security.aliases ?? ""}
                      size="28"
                    ></tui-input
                    >&nbsp;<tui-button
                      ?disabled=${aliasBusy}
                      @click=${() => this.saveAliases(security)}
                      >Save aliases</tui-button
                    >`,
                )}
                ${this.renderDetailRow(
                  "Forecast 4w",
                  this.renderColored(
                    security.forecast_return_4w,
                    scorePercent(security.forecast_return_4w, 1),
                  ),
                )}
                ${this.renderDetailRow(
                  "Timing",
                  scorePercent(security.forecast_score),
                )}
                ${this.renderDetailRow(
                  "AI research",
                  Number.isFinite(multiplier) ? multiplier.toFixed(2) : "-",
                )}
                ${
                  security.ai_research_multiplier_source
                    ? this.renderDetailRow(
                        "Source",
                        security.ai_research_multiplier_source,
                      )
                    : ""
                }
                ${
                  security.ai_research_multiplier_updated_at
                    ? this.renderDetailRow(
                        "Updated",
                        new Date(
                          security.ai_research_multiplier_updated_at,
                        ).toLocaleString(),
                      )
                    : ""
                }
                ${
                  security.ai_research_multiplier_analysis
                    ? this.renderDetailRow(
                        "Analysis",
                        security.ai_research_multiplier_analysis,
                      )
                    : ""
                }
                ${this.renderDetailRow(
                  "Opportunity",
                  scorePercent(security.opp_score, 1),
                )}
                ${this.renderDetailRow(
                  "Dip",
                  scorePercent(security.dip_score, 1),
                )}
                ${this.renderDetailRow(
                  "Capitulation",
                  scorePercent(security.capitulation_score, 1),
                )}
                ${this.renderDetailRow(
                  "Cycle turn",
                  security.cycle_turn ? "yes" : "no",
                )}
                ${this.renderDetailRow(
                  "Freefall blocked",
                  security.freefall_block ? "yes" : "no",
                )}
                ${
                  security.recommendation?.reason
                    ? this.renderDetailRow(
                        "Plan",
                        security.recommendation.reason,
                      )
                    : ""
                }
                ${this.renderDetailRow(
                  "Actions",
                  this.inactiveOnly
                    ? html`<tui-button
                          ?disabled=${this.busyAction ===
                          `activate:${security.symbol}`}
                          @click=${() => this.activateSecurity(security)}
                          >Activate</tui-button
                        >&nbsp;<tui-button
                          variant="error"
                          title=${security.can_delete
                            ? "Permanently delete unused security"
                            : `Cannot delete: ${security.transaction_count || 0} historical transaction(s)`}
                          ?disabled=${!security.can_delete}
                          @click=${() => this.openDeleteDialog(security)}
                          >Delete Permanently</tui-button
                        >`
                    : html`<tui-button
                        variant="error"
                        @click=${() => this.openDeleteDialog(security)}
                        >Remove</tui-button
                      >`,
                )}
                ${
                  this.inactiveOnly && !security.can_delete
                    ? this.renderDetailRow(
                        "Deletion",
                        `Permanent deletion is unavailable because this security has ${security.transaction_count || 0} historical transaction(s).`,
                      )
                    : ""
                }
              </tbody>
            </table>
          </tui-box>
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
      <div style="width: 100%; min-width: 0; overflow-x: auto">
        <table
          aria-label=${this.inactiveOnly ? "Inactive Securities" : "Securities"}
          style="width: 100%; border-spacing: 0"
        >
          <thead>
            <tr>
            <th scope="col" style="text-align: left; vertical-align: top">
              ${
                allExpanded
                  ? html`<tui-button
                      aria-label="Collapse all securities"
                      @click=${this.toggleAll}
                      >−</tui-button
                    >`
                  : html`<tui-button
                      aria-label="Expand all securities"
                      @click=${this.toggleAll}
                      >+</tui-button
                    >`
              }
            </th>
            ${
              this.columnVisible("price")
                ? html`<th
                    scope="col"
                    style="text-align: left; vertical-align: top"
                  >
                    <span aria-hidden="true">│&nbsp;</span>Price
                  </th>`
                : ""
            }
            ${this.renderSortableHeader("Security", "symbol")}
            ${this.columnVisible("value") ? this.renderSortableHeader("Value", "value") : ""}
            ${this.columnVisible("pnl") ? this.renderSortableHeader("P/L", "pnl") : ""}
            ${this.columnVisible("ideal") ? this.renderSortableHeader("Ideal", "ideal") : ""}
            ${this.columnVisible("plan") ? this.renderSortableHeader("Plan", "recommendation") : ""}
            ${
              this.columnVisible("trade")
                ? html`<th
                    scope="col"
                    style="text-align: left; vertical-align: top"
                  >
                    <span aria-hidden="true">│&nbsp;</span
                    >${this.inactiveOnly ? "Status" : "Trade"}
                  </th>`
                : ""
            }
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
      <dialog
        id="columns-dialog"
        aria-label="Choose table columns"
        style="color: var(--tui-color); background: var(--tui-background); border: 0; padding: 0; max-width: calc(100% - 2ch)"
      >
        <tui-box heading="Columns" border="single">
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("price")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "price")}
              >Price</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              checked
              disabled
              aria-label="Security column is always visible"
              >Security</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("value")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "value")}
              >Value</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("pnl")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "pnl")}
              >P/L</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("ideal")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "ideal")}
              >Ideal</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("plan")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "plan")}
              >Plan</tui-toggle
            >
          </div>
          <div>
            <tui-toggle
              ?checked=${this.columnVisible("trade")}
              ?disabled=${this.columnsBusy}
              @change=${(event) => this.toggleColumn(event, "trade")}
              >Trade</tui-toggle
            >
          </div>
          ${
            this.errorMessage
              ? html`<div>
                  <tui-text variant="error">${this.errorMessage}</tui-text>
                </div>`
              : ""
          }
          <div>
            <tui-button @click=${this.closeColumnsDialog}>Done</tui-button>
          </div>
        </tui-box>
      </dialog>
    `;
  }

  renderAddDialog() {
    return html`
      <dialog
        id="add-security-dialog"
        aria-label="Add Security"
        style="color: var(--tui-color); background: var(--tui-background); border: 0; padding: 0; max-width: calc(100% - 2ch)"
      >
        <tui-box heading="Add Security" border="single">
          <form @submit=${this.addSecurity}>
            <label>
              Symbol&nbsp;<tui-input
                id="add-security-symbol"
                aria-label="TraderNet security symbol"
                placeholder="AAPL.US"
                required
                ?disabled=${this.busyAction === "add"}
              ></tui-input>
            </label>
            <div>
              Geography and industry will be filled by the next metadata sync.
            </div>
            ${this.addError ? html`<div><tui-text variant="error">${this.addError}</tui-text></div>` : ""}
            <div>
              <tui-button type="submit" ?disabled=${this.busyAction === "add"}
                >Add Security</tui-button
              >&nbsp;
              <tui-button
                type="button"
                ?disabled=${this.busyAction === "add"}
                @click=${this.closeAddDialog}
                >Cancel</tui-button
              >
            </div>
          </form>
        </tui-box>
      </dialog>
    `;
  }

  renderDeleteDialog() {
    const security = this.deleteCandidate;

    return html`
      <dialog
        id="delete-security-dialog"
        aria-label=${this.inactiveOnly
          ? "Delete Security Permanently"
          : "Remove Security"}
        style="color: var(--tui-color); background: var(--tui-background); border: 0; padding: 0; max-width: calc(100% - 2ch)"
      >
        <tui-box
          heading=${this.inactiveOnly
            ? "Delete Security Permanently"
            : "Remove Security"}
          border="single"
        >
          ${
            security
              ? html`
                  <div>
                    ${this.inactiveOnly
                      ? `Permanently delete ${security.symbol}?`
                      : `Remove ${security.symbol} from the active universe?`}
                  </div>
                  ${
                    security.has_position
                      ? html`<div>
                          <tui-text variant="warning"
                            >Position: ${security.quantity} shares
                            (${formatCurrency(security.value_eur, "EUR")}). It
                            will remain managed, but new buys will be
                            disabled.</tui-text
                          >
                        </div>`
                      : ""
                  }
                  ${
                    this.errorMessage
                      ? html`<div>
                          <tui-text variant="error"
                            >${this.errorMessage}</tui-text
                          >
                        </div>`
                      : ""
                  }
                  <div>
                    <tui-button
                      variant="error"
                      ?disabled=${this.busyAction === `delete:${security.symbol}`}
                      @click=${this.deleteSecurity}
                      >${this.inactiveOnly
                        ? "Delete Permanently"
                        : "Remove"}</tui-button
                    >&nbsp;
                    <tui-button
                      ?disabled=${this.busyAction === `delete:${security.symbol}`}
                      @click=${this.closeDeleteDialog}
                      >Cancel</tui-button
                    >
                  </div>
                `
              : ""
          }
        </tui-box>
      </dialog>
    `;
  }

  render() {
    let content;

    if (this.securities.loading && !this.securities.value) {
      content = html`<span>Loading securities…</span>`;
    } else if (this.securities.error) {
      content = html`<tui-text variant="error"
        >Securities unavailable: ${this.securities.error.message}</tui-text
      >`;
    } else {
      content = html`
        ${this.renderControls()} ${this.renderStats()}
        ${this.message ? html`<div><tui-text variant="success">${this.message}</tui-text></div>` : ""}
        ${this.errorMessage ? html`<div><tui-text variant="error">${this.errorMessage}</tui-text></div>` : ""}
        ${this.renderTable()}
      `;
    }

    return html`
      ${this.bare
        ? content
        : html`<tui-box
            heading=${this.inactiveOnly
              ? "Inactive Securities"
              : "Securities"}
            border="single"
            >${content}</tui-box
          >`}
      ${this.inactiveOnly
        ? ""
        : html`${this.renderColumnsDialog()} ${this.renderAddDialog()}`}
      ${this.renderDeleteDialog()}
    `;
  }
}

customElements.define("sentinel-securities", SentinelSecurities);
