import { LitElement, html } from "lit";
import { getJson, putJson } from "./api.js";
import {
  calculateFirePlan,
  calculateProjectedMonthlyIncome,
  formatFireProjection,
} from "./fire-calculator.js";
import { formatCurrency, formatPercent } from "./format.js";
import { LiveResource } from "./live-resource.js";

const CHECKPOINT_COUNT = 25;
const DEPOSIT_HISTORY_MONTHS_KEY = "strategy_deposit_history_months";

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

  const firstYear = current.getUTCFullYear() + 1;
  const month = current.getUTCMonth();
  const day = current.getUTCDate();

  return Array.from({ length: CHECKPOINT_COUNT }, (_, index) => {
    const year = firstYear + index;
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
    fireAssumptionsError: { state: true },
    monthlyExpensesDraft: { state: true },
    netDepositDraft: { state: true },
    netDepositOverride: { state: true },
    savingFireAssumptions: { state: true },
  };

  constructor() {
    super();
    this.editingNetDeposit = false;
    this.expectedInflationDraft = null;
    this.fireAssumptionsError = "";
    this.monthlyExpensesDraft = null;
    this.netDepositDraft = "";
    this.netDepositOverride = null;
    this.savingFireAssumptions = false;
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

  refreshForSetting = (event) => {
    if (event.detail?.key === DEPOSIT_HISTORY_MONTHS_KEY) {
      this.projection.refresh();
    }
  };

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener("sentinel-setting-changed", this.refreshForSetting);
  }

  disconnectedCallback() {
    window.removeEventListener(
      "sentinel-setting-changed",
      this.refreshForSetting,
    );
    super.disconnectedCallback();
  }

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
          income: calculateProjectedMonthlyIncome(
            point.projected_value_eur,
            data.expectedInflationPct,
            point.months_ahead,
          ),
        };
      })
      .filter(Boolean);
  }

  startNetDepositEdit(summary) {
    this.netDepositDraft = String(summary.avg_monthly_net_deposit_eur);
    this.editingNetDeposit = true;
    this.updateComplete.then(() =>
      this.querySelector(
        'wa-input[aria-label="Monthly net deposit assumption"]',
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

  async saveFireAssumptions(event) {
    event.preventDefault();
    if (this.savingFireAssumptions) return;

    const values = {};
    if (this.monthlyExpensesDraft !== null) {
      const expenses = Number(this.monthlyExpensesDraft);
      if (!Number.isFinite(expenses) || expenses <= 0) {
        this.fireAssumptionsError =
          "Monthly retirement expenses must be greater than zero.";
        return;
      }
      values.fire_monthly_expenses_eur = expenses;
    }
    if (this.expectedInflationDraft !== null) {
      const inflation = Number(this.expectedInflationDraft);
      if (
        this.expectedInflationDraft === "" ||
        !Number.isFinite(inflation) ||
        inflation <= -100
      ) {
        this.fireAssumptionsError =
          "Expected annual inflation must be greater than -100%.";
        return;
      }
      values.fire_expected_inflation_pct = inflation;
    }

    const entries = Object.entries(values);
    if (entries.length === 0) return;
    this.savingFireAssumptions = true;
    this.fireAssumptionsError = "";

    try {
      if (entries.length === 1) {
        const [[key, value]] = entries;
        await putJson(`/api/settings/${key}`, { value });
      } else {
        await putJson("/api/settings", { values });
      }
      this.monthlyExpensesDraft = null;
      this.expectedInflationDraft = null;
      await this.projection.refresh();
    } catch (error) {
      this.fireAssumptionsError = error.message;
    } finally {
      this.savingFireAssumptions = false;
    }
  }

  renderFireCalculator(data) {
    const fire = calculateFirePlan(
      data.monthlyExpensesEur,
      data.expectedInflationPct,
      data.projection,
      data.summary,
    );

    return html`
      ${fire
        ? html`
            <dl class="fire-outcomes">
              <div>
                <dt>Projected FIRE</dt>
                <dd data-tone=${fire.achievement ? "success" : undefined}>
                  ${formatFireProjection(fire)}
                </dd>
              </div>
              <div>
                <dt>F.U. Money today</dt>
                <dd>${formatCurrency(fire.currentTargetEur, "EUR", 0)}</dd>
              </div>
            </dl>
          `
        : html`<p>Enter monthly household expenses to calculate FIRE.</p>`}
      ${fire
        ? html`
            ${fire.achievement
              ? html`
                  <div>
                    At ${fire.expectedInflationPct.toFixed(2)}% expected annual
                    inflation,
                    ${formatCurrency(fire.monthlyExpensesEur, "EUR", 0)}/month
                    today is estimated to cost
                    ${formatCurrency(
                      fire.retirementMonthlyExpensesEur,
                      "EUR",
                      0,
                    )}/month
                    in ${String(fire.achievement.date).slice(0, 4)}.
                  </div>
                  <div>
                    F.U. Money required then:
                    ${formatCurrency(fire.retirementTargetEur, "EUR", 0)}. Its
                    initial 4% annual withdrawal is
                    ${formatCurrency(fire.annualWithdrawalEur, "EUR", 0)}/year,
                    or
                    ${formatCurrency(
                      fire.monthlyWithdrawalEur,
                      "EUR",
                      0,
                    )}/month.
                  </div>
                `
              : html`<div>
                  The portfolio does not catch the inflation-adjusted F.U. Money
                  target under the current assumptions.
                </div>`}
            <div>
              The estimate assumes the portfolio's actual Historical MWR,
              current Net/mo, and expected inflation continue. After retirement,
              withdrawals must keep rising with inflation to preserve today's
              purchasing power.
            </div>
          `
        : ""}
    `;
  }

  renderFireAssumptions(data) {
    return html`
      <form class="fire-assumptions" @submit=${this.saveFireAssumptions}>
        <label
          class="fire-assumption-field"
          title="Monthly retirement expenses in today's prices"
        >
          <span>Monthly expenses</span>
          <wa-input
            id="fire-monthly-expenses"
            size="xs"
            aria-label="Monthly retirement expenses in today's prices in EUR"
            type="number"
            min="0.01"
            step="0.01"
            .value=${this.monthlyExpensesDraft ?? data.monthlyExpensesEur ?? ""}
            ?disabled=${this.savingFireAssumptions}
            @input=${(event) =>
              (this.monthlyExpensesDraft = event.currentTarget.value)}
            ><span slot="start" aria-hidden="true">€</span></wa-input
          >
        </label>
        <label class="fire-assumption-field">
          <span>Annual inflation</span>
          <wa-input
            id="fire-inflation"
            size="xs"
            aria-label="Expected annual inflation percentage"
            type="number"
            min="-99.99"
            step="0.01"
            .value=${this.expectedInflationDraft ?? data.expectedInflationPct}
            ?disabled=${this.savingFireAssumptions}
            @input=${(event) =>
              (this.expectedInflationDraft = event.currentTarget.value)}
            ><span slot="end" aria-hidden="true">%</span></wa-input
          >
        </label>
        <wa-button
          size="xs"
          appearance="outlined"
          type="submit"
          ?disabled=${this.savingFireAssumptions ||
          (this.monthlyExpensesDraft === null &&
            this.expectedInflationDraft === null)}
          >${this.savingFireAssumptions ? "Saving…" : "Save"}</wa-button
        >
      </form>
    `;
  }

  renderNetDeposit(summary) {
    if (this.editingNetDeposit) {
      return html`
        <form style="display: inline" @submit=${this.applyNetDepositOverride}>
          <span>
            Net/mo&nbsp;<wa-input
              size="small"
              aria-label="Monthly net deposit assumption"
              type="number"
              step="0.01"
              style="inline-size: 7rem"
              .value=${this.netDepositDraft}
              @input=${(event) =>
                (this.netDepositDraft = event.currentTarget.value)}
              @keydown=${(event) => {
                if (event.key === "Escape") {
                  this.cancelNetDepositEdit();
                }
              }}
            ></wa-input
            >&nbsp;<wa-button size="small" type="submit">Apply</wa-button
            >&nbsp;<wa-button size="small" @click=${this.cancelNetDepositEdit}
              >Cancel</wa-button
            ></span
          >
        </form>
      `;
    }

    const overridden = this.netDepositOverride !== null;

    return html`
      <span>
        ${summary.deposit_window_months}M net/mo&nbsp;<wa-button
          size="xs"
          appearance="plain"
          aria-label="Edit monthly net deposit assumption"
          @click=${() => this.startNetDepositEdit(summary)}
          >${formatCurrency(
            summary.avg_monthly_net_deposit_eur,
            "EUR",
            0,
          )}</wa-button
        >${overridden
          ? html`&nbsp;actual&nbsp;${formatCurrency(
                summary.actual_avg_monthly_net_deposit_eur,
                "EUR",
                0,
              )}&nbsp;<wa-button
                size="xs"
                appearance="plain"
                aria-label="Reset monthly net deposit assumption to actual"
                @click=${this.resetNetDepositOverride}
                >Reset</wa-button
              >`
          : ""}</span
      >
    `;
  }

  renderMetrics(summary, startYear, endYear) {
    const pnlVariant = summary.total_pnl_pct >= 0 ? "success" : "error";
    const runRateVariant = Number.isFinite(summary.annualized_total_pnl_pct)
      ? summary.annualized_total_pnl_pct >= 0
        ? "success"
        : "error"
      : undefined;

    return html`
      <div
        class="sentinel-layout fire-financial-context"
        data-align="center"
        data-wrap
      >
        <span>${startYear} to ${endYear}</span>
        <span
          title="Cumulative profit: current portfolio value minus net funding; the percentage is relative to deposits minus withdrawals"
        >
          Total P/L&nbsp;<span data-tone=${pnlVariant}
            >${formatSignedCurrency(summary.total_pnl_eur)}
            (${formatPercent(summary.total_pnl_pct, 1)} of net funding)</span
          ></span
        >
        ${this.renderNetDeposit(summary)}
        <span
          title="Since-inception money-weighted annual return used as the projection growth assumption"
        >
          Historical MWR p.a.&nbsp;<span data-tone=${runRateVariant}
            >${formatPercent(summary.annualized_total_pnl_pct, 1)}</span
          ></span
        >
      </div>
    `;
  }

  renderTable(checkpoints, expectedInflationPct) {
    if (checkpoints.length === 0) {
      return html`<span>Not enough data yet</span>`;
    }

    return html`
      <div
        class="fire-projection-scroll"
        role="region"
        aria-label="Year-by-year FIRE projections"
        tabindex="0"
      >
        <table
          class="fire-projection-table"
          aria-label="Portfolio value projections"
          style="border-spacing: 0; white-space: nowrap"
        >
          <thead>
            <tr>
              <th scope="col" style="text-align: left">Year</th>
              <th scope="col" style="text-align: right">Value</th>
              <th
                scope="col"
                aria-label="Projected net deposits"
                style="text-align: right"
              >
                Net deposits
              </th>
              <th
                scope="col"
                title="Initial monthly withdrawal if retiring that year: 4% of projected portfolio value divided by 12"
                style="text-align: right"
              >
                Monthly income
              </th>
              <th
                scope="col"
                title="Projected monthly withdrawal discounted by expected annual inflation to today's purchasing power"
                style="text-align: right"
              >
                Monthly income in today's money
              </th>
            </tr>
          </thead>
          <tbody>
            ${checkpoints.toReversed().map(
              ({ date, point, projectedNetDeposits, income }) => html`
                <tr>
                  <th scope="row" style="font: inherit; text-align: left">
                    ${date.getUTCFullYear()}
                  </th>
                  <td style="text-align: right">
                    ${formatCurrency(point.projected_value_eur, "EUR", 0)}
                  </td>
                  <td style="text-align: right">
                    ${formatCurrency(projectedNetDeposits, "EUR", 0)}
                  </td>
                  <td style="text-align: right">
                    ${formatCurrency(income?.monthlyIncomeEur)}
                  </td>
                  <td style="text-align: right">
                    ${formatCurrency(income?.monthlyIncomeTodayEur)}
                  </td>
                </tr>
              `,
            )}
          </tbody>
        </table>
      </div>
      <div style="color: var(--wa-color-text-quiet); font-size: 0.75em">
        Monthly income assumes retiring in that year and withdrawing 4% of the
        projected value annually, divided by 12. Today's money accounts for
        ${Number(expectedInflationPct).toFixed(2)}% expected annual inflation.
        The default is 2.11%, the mean Greece all-items HICP inflation for
        2016–2025 (Eurostat).
      </div>
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
    ${this.renderMetrics(data.summary, startYear, endYear)}
    ${this.renderTable(checkpoints, data.expectedInflationPct)}`;
  }

  render() {
    let content;

    if (this.projection.loading && !this.projection.value) {
      content = html`<span>Loading projection…</span>`;
    } else if (this.projection.error) {
      content = html`<span data-tone="error">Projection unavailable</span>`;
    } else if (
      !this.projection.value?.summary ||
      !this.projection.value?.projection?.length
    ) {
      content = html`<span>Not enough data yet</span>`;
    } else {
      content = this.renderProjection(this.projection.value);
    }

    return html`
      <wa-card>
        <div slot="header" class="fire-header">
          <span>FIRE (Financial Independence, Retire Early)</span>
          ${this.projection.value
            ? this.renderFireAssumptions(this.projection.value)
            : ""}
        </div>
        ${this.fireAssumptionsError
          ? html`<div role="alert" data-tone="error">
              ${this.fireAssumptionsError}
            </div>`
          : ""}
        ${content}
      </wa-card>
    `;
  }
}

customElements.define("sentinel-portfolio-value", SentinelPortfolioValue);
