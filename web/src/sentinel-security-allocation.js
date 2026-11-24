import { LitElement, html, svg } from "lit";
import { repeat } from "lit/directives/repeat.js";
import { getJson } from "./api.js";
import { formatCurrency } from "./format.js";
import { LiveResource } from "./live-resource.js";
import { storeWidgetCollapsed, widgetCollapsed } from "./widget-state.js";

const TARGET_SERIES = [
  { key: "targetWeight", style: "target", label: "12-month target" },
  { key: "idealWeight", style: "ideal", label: "Ideal allocation" },
];

function weightFor(value, total) {
  return total > 0 && Number.isFinite(value) ? (value / total) * 100 : null;
}

function valueFor(weight, total) {
  return total > 0 && Number.isFinite(weight) ? (weight / 100) * total : null;
}

function weightLabel(weight) {
  return Number.isFinite(weight) ? `${Number(weight.toFixed(2))}%` : "—";
}

function scaleTicks(highest) {
  const interval = Math.max((highest || 4) / 4, 0.01);
  const magnitude = 10 ** Math.floor(Math.log10(interval));
  const step =
    [1, 1.25, 1.5, 2, 2.5, 3, 5, 10].find((n) => n * magnitude >= interval) *
    magnitude;
  return Array.from(
    { length: Math.ceil((highest || 4) / step) + 1 },
    (_, index) => index * step,
  );
}

function targetPath(rows, key, scale) {
  let command = "M";
  return rows
    .map((row, index) => {
      if (!Number.isFinite(row[key])) {
        command = "M";
        return "";
      }
      const point = `${command}${scale(row[key])},${index + 0.5}`;
      command = "L";
      return point;
    })
    .join(" ");
}

export class SentinelSecurityAllocation extends LitElement {
  static properties = {
    sortBy: { state: true },
    showTargets: { state: true },
  };

  constructor() {
    super();
    this.sortBy = "currentWeight";
    this.showTargets = true;
  }

  allocation = new LiveResource(
    this,
    async (signal) => {
      const [securities, planner] = await Promise.all([
        getJson("/api/unified?period=1Y", { signal }),
        getJson("/api/planner/recommendations", { signal }),
      ]);
      return { securities, planner };
    },
    { interval: 60_000 },
  );

  createRenderRoot() {
    return this;
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener(
      "sentinel-setting-changed",
      this.refreshForCashSetting,
    );
  }

  disconnectedCallback() {
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
      this.allocation.refresh();
    }
  };

  storeCollapsed(event) {
    if (event.target === event.currentTarget) {
      storeWidgetCollapsed("security-allocation", !event.currentTarget.open);
    }
  }

  get rows() {
    const { securities = [], planner = {} } = this.allocation.value ?? {};
    const { plan, summary } = planner;
    const targets = new Map(
      (plan?.targets ?? []).map((target) => [target.symbol, target]),
    );
    const recommendations = new Map(
      (planner.recommendations ?? []).map((trade) => [trade.symbol, trade]),
    );
    const total = plan?.current_total_value_eur;
    const terminal = plan?.terminal_portfolio_value_eur;
    const afterPlanTotal = total - (summary?.total_fees ?? 0);
    const rows = [];

    for (const security of securities) {
      const target = targets.get(security.symbol);
      const trade = recommendations.get(security.symbol);
      const current = security.value_eur ?? 0;
      const delta = trade?.value_delta_eur ?? 0;
      const targetWeight = target?.target_allocation_pct;
      const idealWeight =
        target?.model_target_allocation_pct ?? security.ideal_allocation;
      const hasPosition = security.has_position && current > 0;
      const hasTarget =
        this.showTargets && (targetWeight > 0 || idealWeight > 0);
      if (!hasPosition && !delta && !hasTarget) {
        continue;
      }

      const planned = Math.max(0, current + delta);
      const currentWeight =
        security.current_allocation ?? weightFor(current, total) ?? 0;
      rows.push({
        id: `allocation-security-${encodeURIComponent(security.symbol)}`,
        symbol: security.symbol,
        current,
        planned,
        delta,
        currentWeight,
        plannedWeight:
          security.post_plan_allocation ??
          weightFor(planned, afterPlanTotal) ??
          currentWeight,
        targetWeight,
        targetValue: target?.target_value_eur,
        idealWeight,
        idealValue:
          target?.model_target_value_eur ?? valueFor(idealWeight, terminal),
        targetGap: target?.gap_eur,
        quantityDelta: target?.quantity_delta,
        sellLocked: target?.sell_locked,
      });
    }

    const cash = plan?.current_cash_eur ?? 0;
    const plannedCash = Math.max(0, summary?.cash_after_plan ?? cash);
    const targetCash = plan?.target_cash_value_eur;
    if (cash > 0 || plannedCash > 0 || (this.showTargets && targetCash > 0)) {
      const idealCashWeight = plan?.targets
        ? Math.max(
            0,
            100 -
              plan.targets.reduce(
                (sum, target) =>
                  sum +
                  (target.model_target_allocation_pct ??
                    target.target_allocation_pct ??
                    0),
                0,
              ),
          )
        : null;
      const currentWeight = weightFor(cash, total) ?? 0;
      rows.push({
        id: "allocation-cash",
        symbol: "CASH",
        current: cash,
        planned: plannedCash,
        delta: plannedCash - cash,
        currentWeight,
        plannedWeight: weightFor(plannedCash, afterPlanTotal) ?? currentWeight,
        targetWeight: plan?.target_cash_allocation_pct,
        targetValue: targetCash,
        idealWeight: idealCashWeight,
        idealValue: valueFor(idealCashWeight, terminal),
        targetGap: plan?.cash_gap_eur,
      });
    }

    return rows.sort(
      (left, right) =>
        (right[this.sortBy] ?? -1) - (left[this.sortBy] ?? -1) ||
        right.currentWeight - left.currentWeight ||
        left.symbol.localeCompare(right.symbol),
    );
  }

  renderBar(row, index, scale) {
    const base =
      row.delta < 0
        ? Math.min(row.currentWeight, row.plannedWeight)
        : row.currentWeight;
    const end =
      row.delta > 0
        ? Math.max(row.currentWeight, row.plannedWeight)
        : row.currentWeight;
    return html`
      <div
        class="allocation-bar"
        style="grid-row: ${index + 1}; --allocation-bar-base: ${scale(base)}%"
      >
        <span class="allocation-held"></span>
        ${end > base
          ? html`<span
              class=${row.delta > 0 ? "allocation-add" : "allocation-remove"}
              style="inline-size: ${scale(end - base)}%"
            ></span>`
          : ""}
      </div>
    `;
  }

  renderChart(rows) {
    const series = this.showTargets ? TARGET_SERIES : [];
    const tooltipTrigger = globalThis.matchMedia?.("(hover: none)").matches
      ? "click"
      : "hover focus";
    const highest = Math.max(
      0,
      ...rows.map((row) =>
        Math.max(
          row.currentWeight,
          row.plannedWeight,
          ...series.map(({ key }) => row[key] ?? 0),
        ),
      ),
    );
    const ticks = scaleTicks(highest);
    const scale = (weight) => (weight / ticks.at(-1)) * 100;
    return html`
      <figure
        class="allocation-figure"
        style="--allocation-count: ${rows.length}"
      >
        <figcaption>Portfolio weight</figcaption>
        <div class="allocation-axis" aria-hidden="true">
          ${ticks.map(
            (tick) =>
              html`<span style="inset-inline-start: ${scale(tick)}%">
                ${weightLabel(tick)}
              </span>`,
          )}
        </div>
        <div class="allocation-tickers">
          ${repeat(
            rows,
            (row) => row.id,
            (row) =>
              html`<wa-button id=${row.id} appearance="plain" size="small"
                >${row.symbol}</wa-button
              >`,
          )}
        </div>
        <div class="allocation-plot" aria-hidden="true">
          ${ticks.map(
            (tick) =>
              html`<span
                class="allocation-gridline"
                style="inset-inline-start: ${scale(tick)}%"
              ></span>`,
          )}
          ${rows.map((row, index) => this.renderBar(row, index, scale))}
          ${series.length
            ? svg`<svg
                class="allocation-lines"
                viewBox="0 0 100 ${rows.length}"
                preserveAspectRatio="none"
              >
                ${series.map(
                  ({ key, style }) => svg`<path
                    class="allocation-${style}"
                    d=${targetPath(rows, key, scale)}
                  />`,
                )}
              </svg>`
            : ""}
          ${series.length
            ? rows.map(
                (row, index) =>
                  html`<div
                    class="allocation-points"
                    style="grid-row: ${index + 1}"
                  >
                    ${series.map(({ key, style }) =>
                      Number.isFinite(row[key])
                        ? html`<span
                            class="allocation-point allocation-${style}"
                            style="inset-inline-start: ${scale(row[key])}%"
                          ></span>`
                        : "",
                    )}
                  </div>`,
              )
            : ""}
        </div>
        ${repeat(
          rows,
          (row) => row.id,
          (row) => this.renderTooltip(row, tooltipTrigger),
        )}
      </figure>
    `;
  }

  renderTooltip(row, trigger) {
    const entries = [
      ["Current", row.currentWeight, row.current],
      ["After plan", row.plannedWeight, row.planned],
    ];
    if (this.showTargets) {
      entries.push(
        ["12-month target", row.targetWeight, row.targetValue],
        ["Ideal allocation", row.idealWeight, row.idealValue],
      );
    }
    return html`
      <wa-tooltip for=${row.id} trigger=${trigger}>
        <strong>${row.symbol}</strong>
        <dl class="allocation-tooltip-values">
          ${entries.map(
            ([label, weight, value]) => html`
              <dt>${label}</dt>
              <dd>${weightLabel(weight)}</dd>
              <dd>${Number.isFinite(value) ? formatCurrency(value) : "—"}</dd>
            `,
          )}
        </dl>
        ${this.showTargets && Number.isFinite(row.targetGap)
          ? html`<div>
              Target gap
              ${row.targetGap > 0 ? "+" : ""}${formatCurrency(row.targetGap)}
              ${row.quantityDelta
                ? html` ·
                  ${row.quantityDelta > 0
                    ? "+"
                    : ""}${row.quantityDelta.toLocaleString()}
                  shares`
                : ""}
            </div>`
          : ""}
        ${this.showTargets && row.sellLocked
          ? html`<div>Selling disabled</div>`
          : ""}
      </wa-tooltip>
    `;
  }

  renderLegend() {
    const entries = [
      { style: "held", label: "Current holding" },
      { style: "add", label: "Plan increase" },
      { style: "remove", label: "Plan decrease" },
      ...(this.showTargets ? TARGET_SERIES : []),
    ];
    return html`
      <ul class="allocation-legend" aria-label="Chart legend">
        ${entries.map(
          ({ style, label }) =>
            html`<li>
              <span
                class="allocation-swatch allocation-${style}"
                aria-hidden="true"
              ></span>
              ${label}
            </li>`,
        )}
      </ul>
    `;
  }

  render() {
    if (this.allocation.error || !this.allocation.value) {
      return "";
    }

    const rows = this.rows;
    return html`
      <wa-details
        ?open=${!widgetCollapsed("security-allocation")}
        @wa-after-show=${this.storeCollapsed}
        @wa-after-hide=${this.storeCollapsed}
      >
        <span slot="summary">Security Allocation</span>
        <div class="allocation-toolbar">
          ${this.renderLegend()}
          <div class="allocation-controls">
            <wa-select
              size="small"
              aria-label="Sort securities by"
              .value=${this.sortBy}
              @change=${(event) => {
                this.sortBy = event.currentTarget.value;
              }}
            >
              <wa-option value="currentWeight">Current weight</wa-option>
              <wa-option value="targetWeight">12-month target</wa-option>
              <wa-option value="idealWeight">Ideal allocation</wa-option>
            </wa-select>
            <wa-switch
              size="small"
              .checked=${this.showTargets}
              @change=${(event) => {
                this.showTargets = event.currentTarget.checked;
              }}
              >Show targets</wa-switch
            >
          </div>
        </div>
        ${rows.length
          ? this.renderChart(rows)
          : html`<p class="allocation-empty">No allocation data available</p>`}
      </wa-details>
    `;
  }
}

customElements.define(
  "sentinel-security-allocation",
  SentinelSecurityAllocation,
);
