import { LitElement, html } from "lit";
import { formatCurrency, formatPercent } from "./format.js";
import { dateInputValue, formatNumber } from "./modal-utils.js";

const phaseLabels = {
  prepare_db: "Preparing database…",
  discover_symbols: "Discovering securities…",
  download_prices: "Downloading historical data…",
  calculate_scores: "Calculating scores…",
  simulate: "Running simulation…",
};

class SentinelBacktest extends LitElement {
  static properties = {
    startDate: { state: true },
    endDate: { state: true },
    initialCapital: { state: true },
    monthlyDeposit: { state: true },
    rebalanceFrequency: { state: true },
    useExistingUniverse: { state: true },
    pickRandom: { state: true },
    randomCount: { state: true },
    symbols: { state: true },
    status: { state: true },
    progress: { state: true },
    currentDate: { state: true },
    portfolioValue: { state: true },
    errorMessage: { state: true },
    phase: { state: true },
    currentItem: { state: true },
    itemsDone: { state: true },
    itemsTotal: { state: true },
    result: { state: true },
  };

  constructor() {
    super();
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const fiveYearsAgo = new Date();
    fiveYearsAgo.setFullYear(fiveYearsAgo.getFullYear() - 5);

    this.startDate = dateInputValue(fiveYearsAgo);
    this.endDate = dateInputValue(yesterday);
    this.initialCapital = 10_000;
    this.monthlyDeposit = 500;
    this.rebalanceFrequency = "weekly";
    this.useExistingUniverse = true;
    this.pickRandom = true;
    this.randomCount = 10;
    this.symbols = "";
    this.reset();
  }

  createRenderRoot() {
    return this;
  }

  disconnectedCallback() {
    if (this.status === "running") {
      this.eventSource?.close();
      fetch("/api/backtest/cancel", { method: "POST" }).catch(() => {});
    }
    super.disconnectedCallback();
  }

  reset() {
    this.eventSource?.close();
    this.eventSource = undefined;
    this.status = "idle";
    this.progress = 0;
    this.currentDate = "";
    this.portfolioValue = 0;
    this.errorMessage = "";
    this.phase = "";
    this.currentItem = "";
    this.itemsDone = 0;
    this.itemsTotal = 0;
    this.result = undefined;
  }

  fieldValue(event) {
    return event.currentTarget.value;
  }

  startBacktest(event) {
    event.preventDefault();
    this.reset();
    this.status = "running";

    const parameters = new URLSearchParams({
      start_date: this.startDate,
      end_date: this.endDate,
      initial_capital: String(this.initialCapital),
      monthly_deposit: String(this.monthlyDeposit),
      rebalance_frequency: this.rebalanceFrequency,
      use_existing_universe: String(this.useExistingUniverse),
      pick_random: String(this.pickRandom),
      random_count: String(this.randomCount),
      symbols: this.symbols,
    });
    const source = new EventSource(`/api/backtest/run?${parameters}`);
    this.eventSource = source;

    source.addEventListener("progress", (eventSourceEvent) => {
      const data = JSON.parse(eventSourceEvent.data);
      this.progress = data.progress_pct ?? 0;
      this.currentDate = data.current_date ?? "";
      this.portfolioValue = data.portfolio_value ?? 0;
      this.phase = data.phase ?? "";
      this.currentItem = data.current_item ?? "";
      this.itemsDone = data.items_done ?? 0;
      this.itemsTotal = data.items_total ?? 0;

      if (data.status === "error") {
        this.status = "error";
        this.errorMessage = data.message || "Unknown error";
        source.close();
      } else if (data.status === "cancelled") {
        this.status = "idle";
        source.close();
      }
    });
    source.addEventListener("result", (eventSourceEvent) => {
      this.result = JSON.parse(eventSourceEvent.data);
      this.status = "completed";
      source.close();
    });
    source.addEventListener("error", () => {
      if (source.readyState !== EventSource.CLOSED) {
        this.status = "error";
        this.errorMessage = "Connection lost";
        source.close();
      }
    });
  }

  async cancelBacktest() {
    this.eventSource?.close();
    this.eventSource = undefined;

    try {
      await fetch("/api/backtest/cancel", { method: "POST" });
    } catch {
      // The local stream is already closed; cancellation is best effort.
    }

    this.status = "idle";
  }

  renderIdle() {
    return html`
      <form @submit=${this.startBacktest}>
        <div>
          <label
            >Start date&nbsp;<wa-input
              size="small"
              type="date"
              .value=${this.startDate}
              max=${this.endDate}
              required
              @change=${(event) => (this.startDate = this.fieldValue(event))}
            ></wa-input
          ></label>
        </div>
        <div>
          <label
            >End date&nbsp;<wa-input
              size="small"
              type="date"
              .value=${this.endDate}
              min=${this.startDate}
              max=${dateInputValue(new Date(Date.now() - 86_400_000))}
              required
              @change=${(event) => (this.endDate = this.fieldValue(event))}
            ></wa-input
          ></label>
        </div>
        <div>
          <label
            >Initial capital (EUR)&nbsp;<wa-input
              size="small"
              type="number"
              .value=${this.initialCapital}
              min="100"
              max="10000000"
              step="1000"
              required
              @change=${(event) =>
                (this.initialCapital = Number(this.fieldValue(event)))}
            ></wa-input
          ></label>
          <div>Starting portfolio value in EUR</div>
        </div>
        <div>
          <label
            >Monthly deposit (EUR)&nbsp;<wa-input
              size="small"
              type="number"
              .value=${this.monthlyDeposit}
              min="0"
              max="100000"
              step="100"
              required
              @change=${(event) =>
                (this.monthlyDeposit = Number(this.fieldValue(event)))}
            ></wa-input
          ></label>
          <div>Amount to add on the first of each month</div>
        </div>
        <div>
          <label
            >Rebalance frequency&nbsp;<wa-select
              size="small"
              .value=${this.rebalanceFrequency}
              @change=${(event) =>
                (this.rebalanceFrequency = this.fieldValue(event))}
            >
              <wa-option value="daily">Daily</wa-option>
              <wa-option value="weekly">Weekly (Recommended)</wa-option>
              <wa-option value="monthly">Monthly</wa-option>
            </wa-select></label
          >
        </div>
        <div aria-hidden="true">&nbsp;</div>
        <wa-card
          ><span slot="header">Securities Selection</span>
          <div>
            <wa-switch
              size="small"
              .checked=${this.useExistingUniverse}
              @change=${(event) =>
                (this.useExistingUniverse = event.currentTarget.checked)}
              >Use existing universe</wa-switch
            >
          </div>
          <div>Use all active securities from the current database</div>
          ${!this.useExistingUniverse
            ? html`
                <div>
                  <wa-switch
                    size="small"
                    .checked=${this.pickRandom}
                    @change=${(event) =>
                      (this.pickRandom = event.currentTarget.checked)}
                    >Pick random securities</wa-switch
                  >
                </div>
                ${this.pickRandom
                  ? html`<label
                      >Number of securities&nbsp;<wa-input
                        size="small"
                        type="number"
                        .value=${this.randomCount}
                        min="1"
                        max="100"
                        @change=${(event) =>
                          (this.randomCount = Number(this.fieldValue(event)))}
                      ></wa-input
                    ></label>`
                  : html`<label
                      >Symbols&nbsp;<wa-input
                        size="small"
                        .value=${this.symbols}
                        placeholder="AAPL.US, MSFT.US, GOOGL.US"
                        style="inline-size: 40ch; max-inline-size: 100%"
                        @input=${(event) =>
                          (this.symbols = this.fieldValue(event))}
                      ></wa-input
                    ></label>`}
              `
            : ""}
        </wa-card>
        <div aria-hidden="true">&nbsp;</div>
        <wa-button size="small" type="submit">Run Backtest</wa-button>
      </form>
    `;
  }

  renderRunning() {
    return html`
      <div aria-live="polite">
        <div>${phaseLabels[this.phase] ?? "Starting backtest…"}</div>
        <wa-progress-bar
          label="Backtest progress"
          value=${this.progress}
        ></wa-progress-bar>
        ${this.phase === "download_prices" && this.itemsTotal > 0
          ? html`<div>
              ${this.currentItem ? `Processing: ${this.currentItem} · ` : ""}
              ${this.itemsDone} / ${this.itemsTotal} symbols
            </div>`
          : ""}
        ${this.phase === "simulate"
          ? html`<div>
              Simulating: ${this.currentDate} ·
              ${Number(this.progress).toFixed(1)}%
            </div>`
          : ""}
        ${this.portfolioValue > 0 && this.phase === "simulate"
          ? html`<div>
              Portfolio value: ${formatCurrency(this.portfolioValue, "EUR", 0)}
            </div>`
          : ""}
        <div aria-hidden="true">&nbsp;</div>
        <wa-button size="small" variant="danger" @click=${this.cancelBacktest}
          >Cancel</wa-button
        >
      </div>
    `;
  }

  renderResult() {
    const snapshots = this.result?.snapshots ?? [];
    const values = snapshots.map((snapshot) => snapshot.total_value);

    return html`
      <div>
        Total invested ${formatCurrency(this.result.total_deposits, "EUR", 0)} ·
        Final value ${formatCurrency(this.result.final_value, "EUR", 0)} ·
        <span data-tone=${this.result.total_return >= 0 ? "success" : "error"}
          >Return ${formatCurrency(this.result.total_return, "EUR", 0)}
          (${formatPercent(this.result.total_return_pct, 2)})</span
        >
      </div>
      <div>
        <span data-tone=${this.result.cagr >= 0 ? "success" : "error"}
          >CAGR ${formatPercent(this.result.cagr, 2)}</span
        >

        <span data-tone="warning"
          >Max drawdown -${formatNumber(this.result.max_drawdown, 2)}%</span
        >
        Sharpe ${formatNumber(this.result.sharpe_ratio, 2)}
      </div>
      <div aria-hidden="true">&nbsp;</div>
      <wa-card
        ><span slot="header">Equity Curve</span>
        ${values.length > 1
          ? html`<sentinel-chart
              role="img"
              height="6"
              aria-label="Backtest equity curve"
              .values=${values}
            ></sentinel-chart>`
          : "No equity curve data"}
      </wa-card>
      ${this.result.security_performance?.length
        ? html`
            <div aria-hidden="true">&nbsp;</div>
            <wa-card
              ><span slot="header">Security Performance</span>
              <div style="overflow: auto; min-width: 0">
                <table style="border-collapse: collapse; width: 100%">
                  <thead>
                    <tr>
                      <th style="text-align: left">Symbol</th>
                      <th style="text-align: left">Invested</th>
                      <th style="text-align: left">Final value</th>
                      <th style="text-align: left">Return</th>
                      <th style="text-align: left">Trades</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${this.result.security_performance.map(
                      (security) => html`
                        <tr>
                          <td style="text-align: left; vertical-align: top">
                            ${security.symbol}<br />${security.name ?? ""}
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            ${formatCurrency(security.total_invested, "EUR", 0)}
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            ${formatCurrency(security.final_value, "EUR", 0)}
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            <span
                              data-tone=${security.total_return >= 0
                                ? "success"
                                : "error"}
                              >${formatPercent(security.return_pct, 2)}</span
                            >
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            ${security.num_buys} buys, ${security.num_sells}
                            sells
                          </td>
                        </tr>
                      `,
                    )}
                  </tbody>
                </table>
              </div>
            </wa-card>
          `
        : ""}
      <div>
        Total trades: ${this.result.trades?.length ?? 0} ·
        <wa-button size="small" @click=${this.reset}
          >Run Another Backtest</wa-button
        >
      </div>
    `;
  }

  render() {
    if (this.status === "running") {
      return this.renderRunning();
    }

    if (this.status === "error") {
      return html`
        <span data-tone="error">Backtest failed: ${this.errorMessage}</span>
        <div>
          <wa-button size="small" @click=${this.reset}>Try Again</wa-button>
        </div>
      `;
    }

    if (this.status === "completed" && this.result) {
      return this.renderResult();
    }

    return this.renderIdle();
  }
}

customElements.define("sentinel-backtest", SentinelBacktest);
