import { LitElement, html } from "lit";
import { getJson } from "./api.js";
import { LiveResource } from "./live-resource.js";
import { storeWidgetCollapsed, widgetCollapsed } from "./widget-state.js";

function clamp01(value) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(1, value));
}

function percent(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function number(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return Number(value).toFixed(digits);
}

export class SentinelRiskReturn extends LitElement {
  composition = new LiveResource(
    this,
    (signal) => getJson("/api/portfolio/composition", { signal }),
    { interval: 5 * 60_000 },
  );

  createRenderRoot() {
    return this;
  }

  storeCollapsed(event) {
    if (event.target === event.currentTarget) {
      storeWidgetCollapsed("risk-return", !event.currentTarget.open);
    }
  }

  metricRows(metrics) {
    const rows = [
      {
        label: "Last year",
        subLabel: "1Y return — money made (or lost) after subtracting deposits",
        value: metrics.return_1y,
        formatted: percent(metrics.return_1y),
        min: -0.3,
        max: 0.3,
        reference: 0,
        minLabel: "-30%",
        maxLabel: "+30%",
        referenceLabel: "break-even",
        goodDirection: "high",
      },
      {
        label: "Since the beginning",
        subLabel: `CAGR — annualized growth since first deposit (${number(metrics.inception_years || 0, 1)} years)`,
        value: metrics.return_since_inception_cagr,
        formatted: percent(metrics.return_since_inception_cagr),
        min: -0.3,
        max: 0.3,
        reference: 0,
        minLabel: "-30%",
        maxLabel: "+30%",
        referenceLabel: "break-even",
        goodDirection: "high",
      },
      {
        label: "Bumpiness",
        subLabel: "Annual volatility — how wild the daily price swings are",
        value: metrics.volatility,
        formatted: percent(metrics.volatility),
        min: 0,
        max: 0.4,
        reference: 0.18,
        minLabel: "calm",
        maxLabel: "wild",
        referenceLabel: "typical",
        goodDirection: "low",
      },
      {
        label: "Worst drop",
        subLabel: "Max drawdown — biggest dip from peak to bottom",
        value: metrics.max_drawdown,
        formatted: percent(metrics.max_drawdown),
        min: 0,
        max: 0.5,
        reference: 0.2,
        minLabel: "no dips",
        maxLabel: "crash",
        referenceLabel: "tolerable",
        goodDirection: "low",
      },
      {
        label: "Reward for the bumps",
        subLabel: "Sharpe ratio — return per unit of risk, vs cash",
        value: metrics.sharpe,
        formatted: number(metrics.sharpe),
        min: -1,
        max: 3,
        reference: 1,
        minLabel: "-1",
        maxLabel: "3",
        referenceLabel: "good",
        goodDirection: "high",
      },
      {
        label: "All in one basket?",
        subLabel: "Concentration (HHI) — 0 spread evenly, 1 single position",
        value: metrics.hhi,
        formatted: number(metrics.hhi, 3),
        min: 0,
        max: 1,
        reference: 0.1,
        minLabel: "spread",
        maxLabel: "all-in",
        referenceLabel: "diversified",
        goodDirection: "low",
      },
    ];

    if (
      (this.composition.value?.home_markets || []).length > 0 &&
      (metrics.home_coverage_pct || 0) > 0
    ) {
      const coverage = `covers ${percent(metrics.home_coverage_pct, 0)} of holdings`;
      rows.push(
        {
          label: "Tracks home markets?",
          subLabel: `Beta vs each holding's own market index, value-weighted (${coverage})`,
          value: metrics.beta_vs_home,
          formatted: number(metrics.beta_vs_home),
          min: -1,
          max: 2,
          reference: 1,
          minLabel: "-1",
          maxLabel: "+2",
          referenceLabel: "in step",
          goodDirection: "neutral",
        },
        {
          label: "Beating home markets?",
          subLabel: `Alpha — value-weighted outperformance vs each holding's home index (${coverage})`,
          value: metrics.alpha_1y_vs_home,
          formatted: percent(metrics.alpha_1y_vs_home),
          min: -0.2,
          max: 0.2,
          reference: 0,
          minLabel: "-20%",
          maxLabel: "+20%",
          referenceLabel: "matches",
          goodDirection: "high",
        },
      );
    }

    return rows;
  }

  metricColor(row) {
    if (row.goodDirection === "neutral" || !Number.isFinite(row.value)) {
      return "var(--wa-color-text-normal)";
    }
    const good =
      row.goodDirection === "high"
        ? row.value >= row.reference
        : row.value <= row.reference;
    return good
      ? "var(--wa-color-success-on-normal)"
      : "var(--wa-color-danger-on-normal)";
  }

  renderMetric(row, index) {
    const span = row.max - row.min;
    const referencePosition =
      span > 0 ? clamp01((row.reference - row.min) / span) : 0.5;
    const valuePosition =
      span > 0 && Number.isFinite(row.value)
        ? clamp01((row.value - row.min) / span)
        : referencePosition;
    const color = this.metricColor(row);
    const tooltipTarget = `risk-return-metric-${index}`;

    return html`
      <div class="risk-metric">
        <dt>
          <wa-button
            id=${tooltipTarget}
            class="risk-metric-label"
            size="xs"
            appearance="plain"
          >
            ${row.label}
          </wa-button>
          <wa-tooltip for=${tooltipTarget}>
            <div>${row.subLabel}</div>
            <div>
              Scale ${row.minLabel} to ${row.maxLabel} · Marker
              ${row.referenceLabel}
            </div>
          </wa-tooltip>
        </dt>
        <dd>
          <span style="color: ${color}">${row.formatted}</span>
          <span
            class="risk-metric-gauge"
            aria-hidden="true"
            style="
              --risk-reference: ${referencePosition * 100}%;
              --risk-value: ${valuePosition * 100}%;
              --risk-value-color: ${color};
            "
          ></span>
        </dd>
      </div>
    `;
  }

  renderHomeMarkets(data) {
    const markets = data.home_markets || [];
    if (markets.length === 0 || !(data.metrics.home_coverage_pct > 0)) {
      return html`<p class="risk-market-empty">
        Benchmarks not yet synced — home-market comparison will populate on next
        sync cycle.
      </p>`;
    }

    return html`
      <table class="risk-market-table">
        <caption>
          Home markets
        </caption>
        <thead>
          <tr>
            <th scope="col">Market</th>
            <th scope="col">Weight</th>
            <th scope="col">Alpha</th>
            <th scope="col">Beta</th>
          </tr>
        </thead>
        <tbody>
          ${markets.map(
            (market) => html`
              <tr>
                <th scope="row">${market.group}</th>
                <td>${percent(market.weight_pct, 0)}</td>
                <td
                  data-tone=${!Number.isFinite(market.alpha_1y)
                    ? ""
                    : market.alpha_1y >= 0
                      ? "success"
                      : "error"}
                >
                  ${percent(market.alpha_1y)}
                </td>
                <td>${number(market.beta)}</td>
              </tr>
            `,
          )}
        </tbody>
      </table>
    `;
  }

  render() {
    const data = this.composition.value;
    if (
      (this.composition.loading && !data) ||
      this.composition.error ||
      !data?.metrics
    ) {
      return "";
    }

    return html`
      <wa-details
        ?open=${!widgetCollapsed("risk-return")}
        @wa-after-show=${this.storeCollapsed}
        @wa-after-hide=${this.storeCollapsed}
      >
        <span slot="summary">Risk / Return</span>
        <div class="risk-return-layout">
          <dl class="risk-metrics">
            ${this.metricRows(data.metrics).map((row, index) =>
              this.renderMetric(row, index),
            )}
          </dl>
          ${this.renderHomeMarkets(data)}
        </div>
      </wa-details>
    `;
  }
}

customElements.define("sentinel-risk-return", SentinelRiskReturn);
