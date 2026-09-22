import { LitElement, html } from "lit";
import { getJson, putJson } from "./api.js";
import { calculateFirePlan } from "./fire-calculator.js";
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
    expectedInflationDraft: { state: true },
    expectedInflationError: { state: true },
    monthlyExpensesDraft: { state: true },
    monthlyExpensesError: { state: true },
    netDepositDraft: { state: true },
    netDepositOverride: { state: true },
    savingExpectedInflation: { state: true },
    savingMonthlyExpenses: { state: true },
  };

  constructor() {
    super();
    this.editingNetDeposit = false;
    this.expectedInflationDraft = null;
    this.expectedInflationError = "";
    this.monthlyExpensesDraft = null;
    this.monthlyExpensesError = "";
    this.netDepositDraft = "";
    this.netDepositOverride = null;
    this.savingExpectedInflation = false;
    this.savingMonthlyExpenses = false;
  }

  projection = new LiveResource(
    this,
    async (signal) => {
      const params = new URLSearchParams({ years: "25" });

      if (this.netDepositOverride !== null) {
        params.set(
          "avg_monthly_net_deposit_eur",
          String(this.netDepositOverride),
        );
      }

      const [projection, settings] = await Promise.all([
        getJson(`/api/portfolio/value-projection?${params}`, { signal }),
        getJson("/api/settings", { signal }),
      ]);

      return {
        ...projection,
        expectedInflationPct: settings.fire_expected_inflation_pct,
        monthlyExpensesEur: settings.fire_monthly_expenses_eur,
      };
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

  async applyMonthlyExpenses(event, data) {
    event.preventDefault();
    const value = Number(
      this.monthlyExpensesDraft ?? data.monthlyExpensesEur,
    );

    if (!Number.isFinite(value) || value <= 0) {
      this.monthlyExpensesError =
        "Monthly retirement expenses must be greater than zero.";
      return;
    }

    this.savingMonthlyExpenses = true;
    this.monthlyExpensesError = "";

    try {
      await putJson("/api/settings/fire_monthly_expenses_eur", { value });
      this.monthlyExpensesDraft = null;
      await this.projection.refresh();
    } catch (error) {
      this.monthlyExpensesError = error.message;
    } finally {
      this.savingMonthlyExpenses = false;
    }
  }

  async applyExpectedInflation(event, data) {
    event.preventDefault();
    const value = Number(
      this.expectedInflationDraft ?? data.expectedInflationPct,
    );

    if (!Number.isFinite(value) || value <= -100) {
      this.expectedInflationError =
        "Expected annual inflation must be greater than -100%.";
      return;
    }

    this.savingExpectedInflation = true;
    this.expectedInflationError = "";

    try {
      await putJson("/api/settings/fire_expected_inflation_pct", { value });
      this.expectedInflationDraft = null;
      await this.projection.refresh();
    } catch (error) {
      this.expectedInflationError = error.message;
    } finally {
      this.savingExpectedInflation = false;
    }
  }

  renderFireCalculator(data) {
    const fire = calculateFirePlan(
      data.monthlyExpensesEur,
      data.expectedInflationPct,
      data.projection,
      data.summary,
    );
    const fieldValue =
      this.monthlyExpensesDraft ?? data.monthlyExpensesEur ?? "";

    return html`
      <form @submit=${(event) => this.applyMonthlyExpenses(event, data)}>
        <tui-flex align="baseline" wrap>
          <label
            >Monthly retirement expenses in today's prices&nbsp;<tui-input
              aria-label="Estimated monthly expenses on retirement in EUR"
              type="number"
              min="0.01"
              step="0.01"
              size="8"
              value=${fieldValue}
              ?disabled=${this.savingMonthlyExpenses}
              @input=${(event) =>
                (this.monthlyExpensesDraft = event.currentTarget.value)}
            ></tui-input
          ></label>
          <span>&nbsp;</span><tui-button
            type="submit"
            ?disabled=${this.savingMonthlyExpenses}
            >${this.savingMonthlyExpenses ? "Saving…" : "Save & calculate"}</tui-button
          >
        </tui-flex>
      </form>
      ${this.monthlyExpensesError
        ? html`<tui-text variant="error"
            >${this.monthlyExpensesError}</tui-text
          >`
        : ""}
      <form @submit=${(event) => this.applyExpectedInflation(event, data)}>
        <tui-flex align="baseline" wrap>
          <label
            >Expected annual inflation&nbsp;<tui-input
              aria-label="Expected annual inflation percentage"
              type="number"
              min="-99.99"
              step="0.01"
              size="6"
              value=${this.expectedInflationDraft ??
              data.expectedInflationPct}
              ?disabled=${this.savingExpectedInflation}
              @input=${(event) =>
                (this.expectedInflationDraft = event.currentTarget.value)}
            ></tui-input
            >%</label
          >
          <span>&nbsp;</span><tui-button
            type="submit"
            ?disabled=${this.savingExpectedInflation}
            >${this.savingExpectedInflation ? "Saving…" : "Save inflation"}</tui-button
          >
        </tui-flex>
        <div style="color: var(--tui-disabled-color); font-size: 0.75em">
          Default: 2.11%, mean Greece all-items HICP inflation for 2016–2025
          (Eurostat).
        </div>
      </form>
      ${this.expectedInflationError
        ? html`<tui-text variant="error"
            >${this.expectedInflationError}</tui-text
          >`
        : ""}
      ${fire
        ? html`
            <div aria-hidden="true">&nbsp;</div>
            <tui-flex wrap>
              <span style="white-space: nowrap"
                >F.U. Money today&nbsp;<tui-text variant="success"
                  >${formatCurrency(fire.currentTargetEur, "EUR", 0)}</tui-text
                ></span
              >
              <span style="white-space: nowrap"
                >&nbsp;&nbsp;Projected FIRE&nbsp;<tui-text variant="success"
                  >${fire.achievement
                    ? fire.achievement.months_ahead === 0
                      ? "Funded now"
                      : String(fire.achievement.date).slice(0, 4)
                    : "Not reached under current assumptions"}</tui-text
                ></span
              >
            </tui-flex>
            ${fire.achievement
              ? html`
                  <div>
                    At ${fire.expectedInflationPct.toFixed(2)}% expected annual
                    inflation, ${formatCurrency(
                      fire.monthlyExpensesEur,
                      "EUR",
                      0,
                    )}/month today is estimated to cost
                    ${formatCurrency(
                      fire.retirementMonthlyExpensesEur,
                      "EUR",
                      0,
                    )}/month in
                    ${String(fire.achievement.date).slice(0, 4)}.
                  </div>
                  <div>
                    F.U. Money required then:
                    ${formatCurrency(
                      fire.retirementTargetEur,
                      "EUR",
                      0,
                    )}. Its initial 4% annual withdrawal is
                    ${formatCurrency(
                      fire.annualWithdrawalEur,
                      "EUR",
                      0,
                    )}/year, or
                    ${formatCurrency(
                      fire.monthlyWithdrawalEur,
                      "EUR",
                      0,
                    )}/month.
                  </div>
                `
              : html`<div>
                  The portfolio does not catch the inflation-adjusted F.U.
                  Money target under the current assumptions.
                </div>`}
            <div>
              The estimate assumes the portfolio's actual Historical MWR,
              current Net/mo, and expected inflation continue. After retirement,
              withdrawals must keep rising with inflation to preserve today's
              purchasing power.
            </div>
          `
        : html`<div>Enter monthly household expenses to calculate FIRE.</div>`}
    `;
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

    return html`${this.renderFireCalculator(data)}
    <div aria-hidden="true">&nbsp;</div>
    ${this.renderMetrics(data.summary, startYear, endYear)}
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

    return html`<tui-box
      heading="FIRE (Financial Independence, Retire Early)"
      border="single"
      >${content}</tui-box
    >`;
  }
}

customElements.define("sentinel-portfolio-value", SentinelPortfolioValue);
