import { LitElement, html } from "lit";
import { getJson } from "./api.js";
import { formatCurrency } from "./format.js";
import { LiveResource } from "./live-resource.js";

class SentinelPlannerStatus extends LitElement {
  planner = new LiveResource(
    this,
    (signal) => getJson("/api/planner/recommendations", { signal }),
    { interval: 60_000 },
  );

  createRenderRoot() {
    return this;
  }

  refreshForCashSetting = (event) => {
    if (
      event.detail?.key === "simulated_cash_eur" ||
      event.detail?.key === "trading_mode"
    ) {
      this.planner.refresh();
    }
  };

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

  renderRecommendation(recommendation, index) {
    const isSell = recommendation.action === "sell";
    const percentage =
      isSell && recommendation.current_value_eur > 0
        ? ` ${Math.round(
            (Math.abs(recommendation.value_delta_eur) /
              recommendation.current_value_eur) *
              100,
          )}%`
        : "";
    const variant = isSell ? "error" : "success";

    return html`
      <tui-text variant=${variant} title=${recommendation.reason ?? ""}
        >${index > 0 ? html`<span aria-hidden="true">&nbsp;&nbsp;</span>` : ""}${recommendation.action.toUpperCase()}
        ${formatCurrency(Math.abs(recommendation.value_delta_eur))}${percentage}
        ${recommendation.symbol}</tui-text
      >
    `;
  }

  targetItems(plan) {
    if (!plan) {
      return [];
    }

    const cashTarget = {
      symbol: "CASH",
      target_value_eur: Number(plan.target_cash_value_eur ?? 0),
      gap_eur: Number(plan.cash_gap_eur ?? 0),
      isCash: true,
    };
    const targets = [...(plan.targets ?? [])];

    if (
      cashTarget.target_value_eur > 0 ||
      Number(plan.current_cash_eur ?? 0) > 0
    ) {
      targets.push(cashTarget);
    }

    return targets
      .filter((target) => Math.abs(Number(target.gap_eur ?? 0)) > 0.005)
      .sort(
        (left, right) =>
          Math.abs(Number(right.gap_eur)) - Math.abs(Number(left.gap_eur)),
      )
      .slice(0, 6);
  }

  renderTarget(target, index) {
    const gap = Number(target.gap_eur ?? 0);
    const quantityDelta = Number(target.quantity_delta ?? 0);
    const quantity =
      !target.isCash && Math.abs(quantityDelta) > 0.0001
        ? html`&nbsp;·&nbsp;${quantityDelta > 0 ? "+" : "-"}${Math.abs(quantityDelta).toLocaleString()}
          sh`
        : "";
    const title = target.isCash
      ? "Cash left after deploying all affordable whole-lot purchases"
      : `AI research ${target.ai_research_multiplier == null ? "-" : Number(target.ai_research_multiplier).toFixed(2)}, opportunity ${Number(
          target.opportunity_score ?? 0,
        ).toFixed(2)}`;

    return html`
      <span title=${title}
        >${index > 0 ? html`<span aria-hidden="true">&nbsp;&nbsp;</span>` : ""}${target.symbol}&nbsp;${formatCurrency(target.target_value_eur)}
        (${gap >= 0 ? "+" : "-"}${formatCurrency(Math.abs(gap))}${quantity})</span
      >
    `;
  }

  renderPlanner(planner) {
    const recommendations = planner.recommendations ?? [];
    const plan = planner.plan;
    const summary = planner.summary;
    const targets = this.targetItems(plan);
    const cycleLabel = summary?.valid_for_minutes
      ? `Next ${summary.valid_for_minutes} min:`
      : "Next cycle:";
    const gapLabel = `${plan?.horizon_months ?? 12} mo gaps:`;

    return html`
      <tui-flex wrap>
        <span>${cycleLabel}&nbsp;</span>
        ${
          recommendations.length > 0
            ? recommendations.map((recommendation, index) =>
                this.renderRecommendation(recommendation, index),
              )
            : html`<span>No pending actions</span>`
        }
      </tui-flex>
      <tui-flex wrap>
        <span>${gapLabel}&nbsp;</span>
        ${
          targets.length > 0
            ? targets.map((target, index) => this.renderTarget(target, index))
            : html`<span>Target unavailable</span>`
        }
      </tui-flex>
      ${
        plan
          ? html`
              <tui-flex wrap>
                <span
                  >${formatCurrency(plan.terminal_portfolio_value_eur)} by
                  ${plan.horizon_end_date}</span
                >
                <span aria-hidden="true">&nbsp;·&nbsp;</span>
                <span
                  >${formatCurrency(plan.avg_monthly_net_deposit_eur)}/mo</span
                >
                <span aria-hidden="true">&nbsp;·&nbsp;</span>
                <span>${(plan.targets ?? []).length} securities</span>
                ${
                  summary
                    ? html`
                        <span aria-hidden="true">&nbsp;·&nbsp;</span>
                        <span
                          >cash after today
                          ${formatCurrency(summary.cash_after_plan)}</span
                        >
                      `
                    : ""
                }
              </tui-flex>
            `
          : ""
      }
    `;
  }

  render() {
    let content;

    if (this.planner.loading && !this.planner.value) {
      content = html`<span>Loading plan…</span>`;
    } else if (this.planner.error) {
      content = html`<tui-text variant="error">Plan unavailable</tui-text>`;
    } else {
      content = this.renderPlanner(this.planner.value);
    }

    return html`<tui-box heading="Plan" border="single">${content}</tui-box>`;
  }
}

customElements.define("sentinel-planner-status", SentinelPlannerStatus);
