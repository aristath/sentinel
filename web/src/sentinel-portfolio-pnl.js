import { LitElement, html } from "lit";
import { getJson } from "./api.js";
import { formatPercent } from "./format.js";
import { LiveResource } from "./live-resource.js";

const PERIODS = ["1D", "1W", "1M", "3M", "6M", "1Y", "YTD", "All"];

function lastFinite(values) {
  return values.findLast(Number.isFinite);
}

function formatPnl(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  const sign = value >= 0 ? "+" : "-";
  const absolute = Math.abs(value);

  if (absolute >= 1_000_000) {
    return `${sign}€${(absolute / 1_000_000).toFixed(1)}M`;
  }

  if (absolute >= 1_000) {
    return `${sign}€${(absolute / 1_000).toFixed(1)}K`;
  }

  return `${sign}€${absolute.toFixed(0)}`;
}

function valueVariant(value) {
  if (value > 0) {
    return "success";
  }

  if (value < 0) {
    return "error";
  }

  return undefined;
}

class SentinelPortfolioPnl extends LitElement {
  static properties = {
    pnlPeriod: { state: true },
  };

  constructor() {
    super();
    this.pnlPeriod = "1Y";
  }

  performance = new LiveResource(
    this,
    async (signal) => {
      const [periods, history] = await Promise.all([
        getJson("/api/portfolio/period-stats", { signal }),
        getJson(`/api/portfolio/pnl-history?period=${this.pnlPeriod}`, {
          signal,
        }),
      ]);

      return {
        sinceInceptionMoneyWeightedReturn:
          periods.since_inception_money_weighted_return_pct,
        periodStats: periods.period_stats,
        snapshots: history.snapshots,
        summary: history.summary,
      };
    },
    { interval: 300_000 },
  );

  createRenderRoot() {
    return this;
  }

  renderValue(value, formatted) {
    const variant = valueVariant(value);

    return variant
      ? html`<tui-text variant=${variant}>${formatted}</tui-text>`
      : html`<span>${formatted}</span>`;
  }

  renderSummary(summary, sinceInceptionMoneyWeightedReturn) {
    return html`
      <tui-flex align="baseline" justify="between" wrap>
        <span
          title="Annual investor-return target"
          style="white-space: nowrap"
          >Target p.a.&nbsp;${this.renderValue(
            summary.target_ann_return,
            formatPercent(summary.target_ann_return, 1),
          )}</span
        >
        <tui-flex align="baseline" wrap>
          <span
            title="Money-weighted annual return using the date and amount of every deposit and withdrawal"
            style="white-space: nowrap"
            >Overall yearly return&nbsp;${this.renderValue(
              sinceInceptionMoneyWeightedReturn,
              formatPercent(sinceInceptionMoneyWeightedReturn, 1),
            )}</span
          >
          <span
            title="Money-weighted annual return over the last 365 days, using the opening value and every deposit and withdrawal"
            style="white-space: nowrap"
            >&nbsp;│&nbsp;Last 365 days&nbsp;${this.renderValue(
              summary.trailing_365d_money_weighted_return_pct,
              formatPercent(
                summary.trailing_365d_money_weighted_return_pct,
                1,
              ),
            )}</span
          >
        </tui-flex>
      </tui-flex>
    `;
  }

  renderTable(periodStats) {
    return html`
      <table
        aria-label="Portfolio performance by period"
        style="border-spacing: 0"
      >
        <thead>
          <tr>
            <th scope="col" style="text-align: left">Period&nbsp;&nbsp;</th>
            <th scope="col" style="text-align: right">P/L&nbsp;&nbsp;</th>
            <th scope="col" style="text-align: right">Return</th>
          </tr>
        </thead>
        <tbody>
          ${PERIODS.map((period) => {
            const row = periodStats[period] ?? {};

            return html`
              <tr>
                <th scope="row" style="font: inherit; text-align: left">
                  ${period}&nbsp;&nbsp;
                </th>
                <td style="text-align: right">
                  ${this.renderValue(row.portfolio_eur, formatPnl(row.portfolio_eur))}&nbsp;&nbsp;
                </td>
                <td style="text-align: right">
                  ${this.renderValue(row.portfolio_pct, formatPercent(row.portfolio_pct, 1))}
                </td>
              </tr>
            `;
          })}
        </tbody>
      </table>
    `;
  }

  changePeriod(event) {
    this.pnlPeriod = event.currentTarget.value;
    this.performance.refresh();
  }

  renderControls() {
    return html`
      <tui-flex align="baseline" wrap>
        <span>Range&nbsp;</span>
        <tui-radio-buttonset
          aria-label="P/L chart period"
          value=${this.pnlPeriod}
          @change=${this.changePeriod}
        >
          <tui-radio-button value="3M">3M</tui-radio-button>
          <tui-radio-button value="6M">6M</tui-radio-button>
          <tui-radio-button value="1Y">1Y</tui-radio-button>
          <tui-radio-button value="ALL">ALL</tui-radio-button>
        </tui-radio-buttonset>
      </tui-flex>
    `;
  }

  renderChartRow(label, values, latest, minimum, maximum, threshold) {
    const comparison =
      Number.isFinite(latest) && Number.isFinite(threshold)
        ? latest - threshold
        : undefined;
    const graph = html`<tui-chart
      aria-label="${label} annualized return trend"
      height="4"
      min=${minimum}
      max=${maximum}
      threshold=${threshold ?? ""}
      above-variant="success"
      below-variant="error"
      .values=${values}
    ></tui-chart>`;

    return html`
      <tui-flex align="start">
        <span
          data-chart-space
          style="display: block; flex: 1 1 0; min-width: 0; white-space: nowrap"
          >${graph}</span
        >
        <span style="white-space: nowrap"
          >&nbsp;${
            Number.isFinite(comparison)
              ? this.renderValue(comparison, formatPercent(latest, 1))
              : formatPercent(latest, 1)
          }</span
        >
      </tui-flex>
    `;
  }

  renderChart(snapshots, summary) {
    if (!snapshots || snapshots.length < 2) {
      return html`<span>Not enough data yet</span>`;
    }

    const actual = snapshots.map((snapshot) =>
      snapshot.rolling_365d_money_weighted_return_pct === null
        ? undefined
        : Number(snapshot.rolling_365d_money_weighted_return_pct),
    );
    const target = Number(summary.target_ann_return);
    const scaleValues = actual.filter(Number.isFinite);
    const dataMinimum = Math.min(...scaleValues, target);
    const dataMaximum = Math.max(...scaleValues, target);
    const extent =
      Math.max(1, target - dataMinimum, dataMaximum - target) * 1.2;
    const minimum = target - extent;
    const maximum = target + extent;
    const actualLatest = lastFinite(actual);

    return this.renderChartRow(
      "365d MWR",
      actual,
      actualLatest,
      minimum,
      maximum,
      target,
    );
  }

  render() {
    let content;

    if (this.performance.loading && !this.performance.value) {
      content = html`<span>Loading performance…</span>`;
    } else if (this.performance.error) {
      content = html`<tui-text variant="error"
        >Portfolio P&amp;L unavailable</tui-text
      >`;
    } else if (
      !this.performance.value?.periodStats ||
      !this.performance.value?.summary
    ) {
      content = html`<span>Not enough data yet</span>`;
    } else {
      content = html`
        ${this.renderSummary(
          this.performance.value.summary,
          this.performance.value.sinceInceptionMoneyWeightedReturn,
        )}
        ${this.renderControls()}
        ${this.renderChart(
          this.performance.value.snapshots,
          this.performance.value.summary,
        )}
        ${this.renderTable(this.performance.value.periodStats)}
      `;
    }

    return html`<tui-box heading="Portfolio P&amp;L" border="single"
      >${content}</tui-box
    >`;
  }
}

customElements.define("sentinel-portfolio-pnl", SentinelPortfolioPnl);
