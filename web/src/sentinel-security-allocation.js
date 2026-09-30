import { LitElement, html } from "lit";
import { getJson } from "./api.js";
import { formatCurrency } from "./format.js";
import { LiveResource } from "./live-resource.js";
import { storeWidgetCollapsed, widgetCollapsed } from "./widget-state.js";

function percent(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

export class SentinelSecurityAllocation extends LitElement {
  static properties = {
    sortBy: { state: true },
    showIdeal: { state: true },
    compact: { state: true },
  };

  constructor() {
    super();
    this.sortBy = "allocation";
    this.showIdeal = true;
    this.compact = false;
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
    if (typeof ResizeObserver !== "undefined") {
      this.resizeObserver = new ResizeObserver(([entry]) => {
        const compact = entry.contentRect.width <= 520;
        if (compact !== this.compact) {
          this.compact = compact;
        }
      });
      this.resizeObserver.observe(this);
    }
  }

  disconnectedCallback() {
    this.resizeObserver?.disconnect();
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
    storeWidgetCollapsed("security-allocation", !event.currentTarget.open);
  }

  changeSort(event) {
    this.sortBy = event.currentTarget.value;
  }

  changeIdeal(event) {
    this.showIdeal = event.currentTarget.checked;
  }

  get rows() {
    const securities = this.allocation.value?.securities || [];
    const planner = this.allocation.value?.planner || {};
    const recommendations = planner.recommendations || [];
    const longTermPlan = planner.plan;
    const targets = new Map(
      (longTermPlan?.targets || []).map((target) => [target.symbol, target]),
    );

    const rows = securities
      .filter((security) => {
        const hasPosition = security.has_position && security.value_eur > 0;
        const hasRecommendation = recommendations.some(
          (recommendation) => recommendation.symbol === security.symbol,
        );
        const hasIdeal = this.showIdeal && targets.has(security.symbol);
        return hasPosition || hasRecommendation || hasIdeal;
      })
      .map((security) => {
        const recommendation = recommendations.find(
          (candidate) => candidate.symbol === security.symbol,
        );
        const delta = recommendation ? recommendation.value_delta_eur : 0;
        const target = targets.get(security.symbol);
        const current = security.value_eur || 0;
        const final = current + delta;
        const ideal = Number(
          target?.target_value_eur ??
            recommendation?.target_value_eur ??
            current,
        );
        const modelIdeal = Number(target?.model_target_value_eur ?? ideal);

        if (final <= 0 && current <= 0 && ideal <= 0) {
          return undefined;
        }

        return {
          symbol: security.symbol,
          current,
          final: Math.max(0, final),
          delta,
          ideal,
          currentAllocation: security.current_allocation || 0,
          postPlanAllocation:
            security.post_plan_allocation ?? security.current_allocation ?? 0,
          idealAllocation:
            target?.target_allocation_pct ?? security.ideal_allocation ?? 0,
          targetGap: Number(target?.gap_eur || 0),
          quantityDelta: Number(target?.quantity_delta || 0),
          modelIdeal,
          sellLocked: Boolean(target?.sell_locked),
          isBuy: delta > 0,
          isSell: delta < 0,
          maxBar: this.showIdeal
            ? Math.max(current, final, ideal)
            : Math.max(current, final),
        };
      })
      .filter(Boolean);

    const currentCash = Number(longTermPlan?.current_cash_eur || 0);
    const targetCash = Number(longTermPlan?.target_cash_value_eur || 0);
    if (currentCash > 0 || targetCash > 0) {
      const currentTotal = Number(longTermPlan?.current_total_value_eur || 0);
      const plannedCash = Number.isFinite(
        Number(planner.summary?.cash_after_plan),
      )
        ? Math.max(0, Number(planner.summary.cash_after_plan))
        : currentCash;
      const delta = plannedCash - currentCash;
      rows.push({
        symbol: "CASH",
        current: currentCash,
        final: plannedCash,
        delta,
        ideal: targetCash,
        currentAllocation:
          currentTotal > 0 ? (currentCash / currentTotal) * 100 : 0,
        postPlanAllocation:
          currentTotal > 0 ? (plannedCash / currentTotal) * 100 : 0,
        idealAllocation: Number(
          longTermPlan?.target_cash_allocation_pct || 0,
        ),
        targetGap: Number(longTermPlan?.cash_gap_eur || 0),
        quantityDelta: 0,
        modelIdeal: targetCash,
        sellLocked: false,
        isBuy: delta > 0,
        isSell: delta < 0,
        maxBar: this.showIdeal
          ? Math.max(currentCash, plannedCash, targetCash)
          : Math.max(currentCash, plannedCash),
      });
    }

    rows.sort((left, right) =>
      this.sortBy === "ideal"
        ? right.ideal - left.ideal
        : Math.max(right.final, right.current) -
          Math.max(left.final, left.current),
    );

    return rows;
  }

  renderRow(row, maximum) {
    const grayWidth =
      maximum > 0
        ? ((row.isBuy ? row.final - row.delta : row.final) / maximum) * 100
        : 0;
    const deltaWidth = maximum > 0 ? (Math.abs(row.delta) / maximum) * 100 : 0;
    const idealPosition = maximum > 0 ? (row.ideal / maximum) * 100 : 0;
    const targetGapText = `${row.targetGap >= 0 ? "+" : "-"}${formatCurrency(Math.abs(row.targetGap), "EUR")}`;
    const quantityText =
      Math.abs(row.quantityDelta || 0) > 0.0001
        ? `; ${row.quantityDelta > 0 ? "+" : "-"}${Math.abs(row.quantityDelta).toLocaleString()} shares`
        : "";
    const idealTitle = row.sellLocked
      ? `No-sell holding remains unchanged; model target: ${formatCurrency(row.modelIdeal, "EUR")}`
      : `12-month target: ${formatCurrency(row.ideal, "EUR")}; gap: ${targetGapText}${quantityText}`;

    return html`
      <tr>
        <td
          title=${row.symbol}
          style="width: ${this.compact ? "62px" : "76px"}; padding: 4px 8px 4px 0; font-size: 0.75em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis"
        >
          ${row.symbol}
        </td>
        <td style="width: 100%; padding: 4px 8px 4px 0">
          <div
            style="position: relative; display: flex; width: 100%; height: 16px; overflow: hidden; background: color-mix(in srgb, var(--tui-color) 8%, transparent); border: 1px solid color-mix(in srgb, var(--tui-color) 30%, transparent)"
          >
            ${grayWidth > 0
              ? html`<div
                  style="height: 100%; width: ${grayWidth}%; background: var(--tui-disabled-color)"
                ></div>`
              : ""}
            ${row.isBuy && deltaWidth > 0
              ? html`<div
                  style="height: 100%; width: ${deltaWidth}%; background: var(--tui-success-color)"
                ></div>`
              : ""}
            ${row.isSell && deltaWidth > 0
              ? html`<div
                  style="height: 100%; width: ${deltaWidth}%; background: var(--tui-error-color)"
                ></div>`
              : ""}
            ${this.showIdeal
              ? html`<div
                  title=${idealTitle}
                  style="position: absolute; left: ${idealPosition}%; top: -2px; bottom: -2px; width: 2px; background: light-dark(blue, deepskyblue); transform: translateX(-1px)"
                ></div>`
              : ""}
          </div>
        </td>
        <td
          style="width: ${this.compact ? "118px" : "174px"}; padding: 4px 0; color: var(--tui-disabled-color); font-size: 0.6875em; text-align: right; white-space: ${this.compact ? "normal" : "nowrap"}"
        >
          ${this.compact
            ? ""
            : html`<div>
                <span>${percent(row.currentAllocation)}</span>
                <span style="padding: 0 4px">→</span>
                <span
                  style="color: ${row.isBuy
                    ? "var(--tui-success-color)"
                    : row.isSell
                      ? "var(--tui-error-color)"
                      : "inherit"}; font-weight: ${row.isBuy || row.isSell
                    ? "600"
                    : "inherit"}"
                  >${percent(row.postPlanAllocation)}</span
                >
                <span style="padding-left: 4px; color: light-dark(blue, deepskyblue)"
                  >/ ${percent(row.idealAllocation)}</span
                >
              </div>`}
          <div
            style="margin-top: 2px; color: var(--tui-disabled-color); font-size: ${this.compact ? "0.82em" : "0.91em"}"
          >
            ${formatCurrency(row.ideal, "EUR")} ·
            ${row.sellLocked ? "unchanged" : targetGapText}
          </div>
        </td>
      </tr>
    `;
  }

  legend(color, label, ideal = false) {
    return html`<span
      style="display: inline-flex; align-items: center; gap: 0.5ch; white-space: nowrap"
    >
      <span
        aria-hidden="true"
        style="display: inline-block; flex: 0 0 auto; width: ${ideal
          ? "2px"
          : "12px"}; height: ${ideal
          ? "12px"
          : "10px"}; background: ${color}; border: ${ideal
          ? "none"
          : "1px solid color-mix(in srgb, var(--tui-color) 30%, transparent)"}"
      ></span>
      <span style="color: var(--tui-disabled-color); font-size: 0.75em"
        >${label}</span
      >
    </span>`;
  }

  render() {
    if (
      (this.allocation.loading && !this.allocation.value) ||
      this.allocation.error ||
      !this.allocation.value
    ) {
      return "";
    }

    const rows = this.rows;
    const maximum = Math.max(...rows.map((row) => row.maxBar), 0);

    return html`
      <details
        ?open=${!widgetCollapsed("security-allocation")}
        @toggle=${this.storeCollapsed}
      >
        <summary style="cursor: pointer; font-weight: 600">
          Security Allocation
        </summary>
        <tui-box heading="Security Allocation" border="single">
          <div style="display: grid; gap: 0.75em">
            <div
              style="display: flex; justify-content: space-between; align-items: baseline; gap: 1ch; flex-wrap: wrap"
            >
              <span
                style="color: var(--tui-disabled-color); font-size: 0.75em; font-weight: 600; text-transform: uppercase"
                >Security Allocation</span
              >
              <span style="display: inline-flex; gap: 1ch; align-items: baseline">
                <tui-radio-buttonset
                  aria-label="Security allocation sorting"
                  value=${this.sortBy}
                  @change=${this.changeSort}
                >
                  <tui-radio-button value="allocation"
                    >By allocation</tui-radio-button
                  >
                  <tui-radio-button value="ideal">By ideal</tui-radio-button>
                </tui-radio-buttonset>
                <tui-toggle
                  ?checked=${this.showIdeal}
                  @change=${this.changeIdeal}
                  >Ideal</tui-toggle
                >
              </span>
            </div>
            ${rows.length > 0
              ? html`<div style="min-width: 0; overflow-x: auto">
                  <table
                    aria-label="Security Allocation"
                    style="width: 100%; border-collapse: collapse; table-layout: ${this
                      .compact
                      ? "auto"
                      : "fixed"}"
                  >
                    <tbody>
                      ${rows.map((row) => this.renderRow(row, maximum))}
                    </tbody>
                  </table>
                </div>`
              : html`<div
                  style="padding: 2em 0; color: var(--tui-disabled-color); text-align: center"
                >
                  No allocation data available
                </div>`}
            <div
              style="display: flex; gap: 1em; flex-wrap: wrap; padding-top: 4px"
            >
              ${this.legend("var(--tui-disabled-color)", "Current holding")}
              ${this.legend("var(--tui-success-color)", "Today's increase")}
              ${this.legend("var(--tui-error-color)", "Today's decrease")}
              ${this.showIdeal
                ? this.legend(
                    "light-dark(blue, deepskyblue)",
                    "12-month target",
                    true,
                  )
                : ""}
            </div>
          </div>
        </tui-box>
      </details>
    `;
  }
}

customElements.define(
  "sentinel-security-allocation",
  SentinelSecurityAllocation,
);
