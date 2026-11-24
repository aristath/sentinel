import { LitElement, html } from "lit";
import { getJson } from "./api.js";
import { formatCurrency } from "./format.js";
import { LiveResource } from "./live-resource.js";

const rowStyle = `
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.25rem 1rem;
`;
const labelStyle = "flex: 0 0 6.5rem; font-weight: 600";
const listStyle = `
  display: flex; flex: 1 1 21rem; flex-wrap: wrap; align-items: baseline;
  gap: 0.375rem 1rem; min-inline-size: 0; margin: 0; padding: 0; list-style: none;
`;
const planHeading = html`
  <h2
    id="sentinel-plan-title"
    style="${labelStyle}; font-size: 1rem; line-height: 1.25; margin: 0"
  >
    Plan
  </h2>
`;

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

  renderRecommendation(recommendation) {
    const isSell = recommendation.action === "sell";
    const waitingForMarket = recommendation.market_open === false;
    const percentage =
      isSell && recommendation.current_value_eur > 0
        ? `${Math.round(
            (Math.abs(recommendation.value_delta_eur) /
              recommendation.current_value_eur) *
              100,
          )}%`
        : "";
    const variant = waitingForMarket
      ? "neutral"
      : isSell
        ? "danger"
        : "success";
    const title = [
      waitingForMarket ? "Waiting for market to open" : "",
      recommendation.reason ?? "",
    ]
      .filter(Boolean)
      .join(" · ");

    return html`
      <li
        title=${title}
        style="
          display: inline-flex; flex-wrap: wrap; align-items: center;
          gap: 0.15rem 0.35rem; min-inline-size: 0;
        "
      >
        <wa-badge variant=${variant} appearance="filled"
          >${isSell ? "Sell" : "Buy"}</wa-badge
        >
        <strong style="font-weight: 650">${recommendation.symbol}</strong>
        <span>${formatCurrency(Math.abs(recommendation.value_delta_eur))}</span>
        ${percentage
          ? html`<span style="color: var(--wa-color-text-quiet)"
              >(${percentage})</span
            >`
          : ""}
        ${waitingForMarket
          ? html`<span
              style="color: var(--wa-color-text-quiet); font-size: 0.75rem"
              >Market closed</span
            >`
          : ""}
      </li>
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
      );
  }

  renderTarget(target) {
    const gap = Number(target.gap_eur ?? 0);
    const quantityDelta = Number(target.quantity_delta ?? 0);
    const quantity =
      !target.isCash && Math.abs(quantityDelta) > 0.0001
        ? `${quantityDelta > 0 ? "+" : "-"}${Math.abs(quantityDelta).toLocaleString()} sh`
        : "";
    const title = target.isCash
      ? "Cash left after deploying all affordable whole-lot purchases"
      : `AI research ${target.ai_research_multiplier == null ? "-" : Number(target.ai_research_multiplier).toFixed(2)}, opportunity ${Number(
          target.opportunity_score ?? 0,
        ).toFixed(2)}`;

    return html`
      <li class="plan-target" title=${title}>
        <strong style="font-weight: 600">${target.symbol}</strong>
        <span title="Target value"
          >${formatCurrency(target.target_value_eur)}</span
        >
        <span class="plan-target-gap" title="Gap to target"
          >${gap >= 0 ? "+" : "-"}${formatCurrency(Math.abs(gap))}</span
        >
        <span class="plan-target-quantity" title="Share change"
          >${quantity}</span
        >
      </li>
    `;
  }

  renderPlanner(planner) {
    const recommendations = planner.recommendations ?? [];
    const plan = planner.plan;
    const summary = planner.summary;
    const targets = this.targetItems(plan);
    const gapLabel = `${plan?.horizon_months ?? 12} mo gaps`;

    return html`
      <div style=${rowStyle}>
        ${planHeading}
        <ul
          class="plan-inline-list"
          role="list"
          aria-label="Current plan"
          style=${listStyle}
        >
          ${recommendations.length > 0
            ? recommendations.map((recommendation) =>
                this.renderRecommendation(recommendation),
              )
            : html`<li style="color: var(--wa-color-text-quiet)">
                No pending actions
              </li>`}
        </ul>
      </div>
      ${plan
        ? html`
            <div style="${rowStyle} color: var(--wa-color-text-quiet)">
              <span id="sentinel-plan-projection-label" style=${labelStyle}
                >Projection</span
              >
              <ul
                class="plan-inline-list"
                role="list"
                aria-labelledby="sentinel-plan-projection-label"
                style=${listStyle}
              >
                <li>
                  <strong
                    style="color: var(--wa-color-text-normal); font-weight: 650"
                    >${formatCurrency(
                      plan.terminal_portfolio_value_eur,
                    )}</strong
                  >
                  by
                  <time datetime=${plan.horizon_end_date}
                    >${plan.horizon_end_date}</time
                  >
                </li>
                <li>${formatCurrency(plan.avg_monthly_net_deposit_eur)}/mo</li>
                <li>${(plan.targets ?? []).length} securities</li>
                ${summary
                  ? html`<li>
                      Cash after trades
                      ${formatCurrency(summary.cash_after_plan)}
                    </li>`
                  : ""}
              </ul>
            </div>
          `
        : ""}
      <div>
        <div class="plan-targets-header">
          <span id="sentinel-plan-gap-label" style="font-weight: 600"
            >${gapLabel}</span
          >
          ${targets.length > 0
            ? html`<span class="plan-target-gap"
                >Target value · Gap · Shares</span
              >`
            : ""}
        </div>
        <ul
          role="list"
          aria-labelledby="sentinel-plan-gap-label"
          class="plan-targets"
        >
          ${targets.length > 0
            ? targets.map((target) => this.renderTarget(target))
            : html`<li>Target unavailable</li>`}
        </ul>
      </div>
    `;
  }

  render() {
    const loading = this.planner.loading && !this.planner.value;
    const error = this.planner.error;

    return html`
      <wa-card appearance="outlined">
        <section
          aria-labelledby="sentinel-plan-title"
          style="
          display: grid;
          gap: 0.45rem;
          overflow-wrap: anywhere;
        "
        >
          ${loading || error
            ? html`
                <div style=${rowStyle}>
                  ${planHeading}
                  <span
                    role="status"
                    style="color: ${error
                      ? "var(--wa-color-danger-on-normal)"
                      : "var(--wa-color-text-quiet)"}"
                  >
                    ${error ? "Plan unavailable" : "Loading plan…"}
                  </span>
                </div>
              `
            : this.renderPlanner(this.planner.value)}
        </section>
      </wa-card>
    `;
  }
}

customElements.define("sentinel-planner-status", SentinelPlannerStatus);
