import { LitElement, html } from "lit";
import { getJson } from "./api.js";
import { formatCurrency, formatPercent } from "./format.js";
import { LiveResource } from "./live-resource.js";

const CHECKPOINT_COUNT = 5;
const CHECKPOINT_INTERVAL = 5;

function formatSignedCurrency(value, currency = "EUR", fractionDigits = 0) {
  if (value === null || value === undefined) {
    return "-";
  }

  return `${value > 0 ? "+" : ""}${formatCurrency(
    value,
    currency,
    fractionDigits,
  )}`;
}

function checkpointDates(currentDate) {
  const current = new Date(`${currentDate}T00:00:00Z`);

  if (Number.isNaN(current.getTime())) {
    return [];
  }

  const firstYear =
    Math.floor(current.getUTCFullYear() / CHECKPOINT_INTERVAL) *
      CHECKPOINT_INTERVAL +
    5;
  const month = current.getUTCMonth();
  const day = current.getUTCDate();

  return Array.from({ length: CHECKPOINT_COUNT }, (_, index) => {
    const year = firstYear + index * CHECKPOINT_INTERVAL;
    const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
    return new Date(Date.UTC(year, month, Math.min(day, lastDay)));
  });
}

function closestProjection(projection, target) {
  let closest;
  let closestDistance = Number.POSITIVE_INFINITY;

  for (const point of projection) {
    const date = Date.parse(`${point.date}T00:00:00Z`);
    const distance = Math.abs(date - target.getTime());

    if (Number.isFinite(date) && distance < closestDistance) {
      closest = point;
      closestDistance = distance;
    }
  }

  return closest;
}

class SentinelPortfolioValue extends LitElement {
  static properties = {
    editingNetDeposit: { state: true },
    netDepositDraft: { state: true },
    netDepositOverride: { state: true },
  };

  constructor() {
    super();
    this.editingNetDeposit = false;
    this.netDepositDraft = "";
    this.netDepositOverride = null;
  }

  projection = new LiveResource(
    this,
    (signal) => {
      const params = new URLSearchParams({ years: "25" });

      if (this.netDepositOverride !== null) {
        params.set(
          "avg_monthly_net_deposit_eur",
          String(this.netDepositOverride),
        );
      }

      return getJson(`/api/portfolio/value-projection?${params}`, { signal });
    },
    { interval: 300_000 },
  );

  createRenderRoot() {
    return this;
  }

  projectionRows(data) {
    return checkpointDates(data.summary.current_date)
      .map((date) => {
        const point = closestProjection(data.projection, date);

        if (!point) {
          return undefined;
        }

        return {
          date,
          point,
          projectedNetDeposits:
            data.summary.current_net_deposits_eur +
            data.summary.avg_monthly_net_deposit_eur * point.months_ahead,
        };
      })
      .filter(Boolean);
  }

  startNetDepositEdit(summary) {
    this.netDepositDraft = String(summary.avg_monthly_net_deposit_eur);
    this.editingNetDeposit = true;
    this.updateComplete.then(() =>
      this.querySelector(
        'tui-input[aria-label="Monthly net deposit assumption"]',
      )?.select(),
    );
  }

  cancelNetDepositEdit() {
    this.editingNetDeposit = false;
    this.netDepositDraft = "";
  }

  applyNetDepositOverride(event) {
    event.preventDefault();
    const value = Number(this.netDepositDraft);

    if (!Number.isFinite(value)) {
      return;
    }

    this.netDepositOverride = value;
    this.cancelNetDepositEdit();
    this.projection.refresh();
  }

  resetNetDepositOverride() {
    this.netDepositOverride = null;
    this.cancelNetDepositEdit();
    this.projection.refresh();
  }

  renderNetDeposit(summary) {
    if (this.editingNetDeposit) {
      return html`
        <form
          style="display: inline"
          @submit=${this.applyNetDepositOverride}
        >
          <span style="white-space: nowrap"
            >&nbsp;&nbsp;Net/mo&nbsp;<tui-input
              aria-label="Monthly net deposit assumption"
              type="number"
              step="0.01"
              size="8"
              value=${this.netDepositDraft}
              @input=${(event) =>
                (this.netDepositDraft = event.currentTarget.value)}
              @keydown=${(event) => {
                if (event.key === "Escape") {
                  this.cancelNetDepositEdit();
                }
              }}
            ></tui-input
            >&nbsp;<tui-button type="submit">Apply</tui-button
            >&nbsp;<tui-button @click=${this.cancelNetDepositEdit}
              >Cancel</tui-button
            ></span
          >
        </form>
      `;
    }

    const overridden = this.netDepositOverride !== null;

    return html`
      <span style="white-space: nowrap"
        >&nbsp;&nbsp;${summary.deposit_window_months}M net/mo&nbsp;<tui-button
          aria-label="Edit monthly net deposit assumption"
          @click=${() => this.startNetDepositEdit(summary)}
          >${formatCurrency(
            summary.avg_monthly_net_deposit_eur,
            "EUR",
            0,
          )}</tui-button
        >${overridden
          ? html`&nbsp;actual&nbsp;${formatCurrency(
                summary.actual_avg_monthly_net_deposit_eur,
                "EUR",
                0,
              )}&nbsp;<tui-button
                aria-label="Reset monthly net deposit assumption to actual"
                @click=${this.resetNetDepositOverride}
                >Reset</tui-button
              >`
          : ""}</span
      >
    `;
  }

  renderMetrics(summary, startYear, endYear) {
    const pnlVariant = summary.total_pnl_pct >= 0 ? "success" : "error";
    const runRateVariant =
      Number.isFinite(summary.annualized_total_pnl_pct)
        ? summary.annualized_total_pnl_pct >= 0
          ? "success"
          : "error"
        : undefined;

    return html`
      <tui-flex wrap>
        <span style="white-space: nowrap">${startYear} to ${endYear}</span>
        <span
          title="Cumulative profit: current portfolio value minus net funding; the percentage is relative to deposits minus withdrawals"
          style="white-space: nowrap"
          >&nbsp;&nbsp;Total P/L&nbsp;<tui-text variant=${pnlVariant}
            >${formatSignedCurrency(summary.total_pnl_eur)}
            (${formatPercent(summary.total_pnl_pct, 1)} of net funding)</tui-text
          ></span
        >
        ${this.renderNetDeposit(summary)}
        <span
          title="Since-inception money-weighted annual return used as the projection growth assumption"
          style="white-space: nowrap"
          >&nbsp;&nbsp;Historical MWR p.a.&nbsp;<tui-text variant=${runRateVariant}
            >${formatPercent(summary.annualized_total_pnl_pct, 1)}</tui-text
          ></span
        >
      </tui-flex>
    `;
  }

  renderTable(checkpoints) {
    if (checkpoints.length === 0) {
      return html`<span>Not enough data yet</span>`;
    }

    return html`
      <table aria-label="Portfolio value projections" style="border-spacing: 0">
        <thead>
          <tr>
            <th scope="col" style="text-align: left">Year&nbsp;&nbsp;</th>
            <th scope="col" style="text-align: right">Value&nbsp;&nbsp;</th>
            <th
              scope="col"
              aria-label="Projected net deposits"
              style="text-align: right"
            >
              Net deposits
            </th>
          </tr>
        </thead>
        <tbody>
          ${checkpoints.map(
            ({ date, point, projectedNetDeposits }) => html`
              <tr>
                <th scope="row" style="font: inherit; text-align: left">
                  ${date.getUTCFullYear()}&nbsp;&nbsp;
                </th>
                <td style="text-align: right">
                  ${formatCurrency(point.projected_value_eur, "EUR", 0)}&nbsp;&nbsp;
                </td>
                <td style="text-align: right">
                  ${formatCurrency(projectedNetDeposits, "EUR", 0)}
                </td>
              </tr>
            `,
          )}
        </tbody>
      </table>
    `;
  }

  renderProjection(data) {
    const checkpoints = this.projectionRows(data);

    if (checkpoints.length === 0) {
      return html`<span>Not enough data yet</span>`;
    }

    const startYear = String(data.summary.start_date).slice(0, 4);
    const endYear = checkpoints.at(-1).date.getUTCFullYear();

    return html`${this.renderMetrics(data.summary, startYear, endYear)}
    ${this.renderTable(checkpoints)}`;
  }

  render() {
    let content;

    if (this.projection.loading && !this.projection.value) {
      content = html`<span>Loading projection…</span>`;
    } else if (this.projection.error) {
      content = html`<tui-text variant="error"
        >Projection unavailable</tui-text
      >`;
    } else if (
      !this.projection.value?.summary ||
      !this.projection.value?.projection?.length
    ) {
      content = html`<span>Not enough data yet</span>`;
    } else {
      content = this.renderProjection(this.projection.value);
    }

    return html`<tui-box heading="Portfolio value" border="single"
      >${content}</tui-box
    >`;
  }
}

customElements.define("sentinel-portfolio-value", SentinelPortfolioValue);
