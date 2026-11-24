import { LitElement, html } from "lit";
import { getJson, putJson } from "./api.js";
import { formatCurrency } from "./format.js";
import { LiveResource } from "./live-resource.js";

class SentinelPortfolioStatus extends LitElement {
  static properties = {
    cashDraft: { state: true },
    cashError: { state: true },
    cashPending: { state: true },
    editingCash: { state: true },
  };

  constructor() {
    super();
    this.cashDraft = "";
    this.cashError = "";
    this.cashPending = false;
    this.editingCash = false;
  }

  portfolio = new LiveResource(
    this,
    (signal) => getJson("/api/portfolio", { signal }),
    { interval: 60_000 },
  );

  cashFlows = new LiveResource(
    this,
    (signal) => getJson("/api/cashflows", { signal }),
    { interval: 300_000 },
  );

  settings = new LiveResource(
    this,
    (signal) => getJson("/api/settings", { signal }),
    { interval: 0 },
  );

  refreshForSetting = (event) => {
    if (
      event.detail?.source !== this &&
      (event.detail?.key === "simulated_cash_eur" ||
        event.detail?.key === "trading_mode")
    ) {
      this.settings.refresh();
      this.portfolio.refresh();
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

  renderCashBreakdown(cash) {
    const balances = Object.entries(cash ?? {}).filter(
      ([, amount]) => amount !== 0,
    );

    if (balances.length === 0) {
      return "";
    }

    return html`&nbsp;(${balances.map(
      ([currency, amount], index) =>
        html`${index > 0 ? ", " : ""}${currency}&nbsp;${formatCurrency(
          amount,
          currency,
        )}`,
    )})`;
  }

  get isResearchMode() {
    return this.settings.value?.trading_mode === "research";
  }

  get simulatedCash() {
    return this.settings.value?.simulated_cash_eur;
  }

  get cashIsSimulated() {
    return (
      this.isResearchMode &&
      this.simulatedCash !== null &&
      this.simulatedCash !== undefined
    );
  }

  startCashEdit() {
    this.cashDraft = String(
      this.cashIsSimulated
        ? this.simulatedCash
        : (this.portfolio.value?.total_cash_eur ?? 0),
    );
    this.cashError = "";
    this.editingCash = true;
    this.updateComplete.then(() =>
      this.querySelector(
        'wa-input[aria-label="Simulated cash in EUR"]',
      )?.select(),
    );
  }

  cancelCashEdit() {
    this.cashDraft = "";
    this.cashError = "";
    this.editingCash = false;
  }

  async setCashOverride(value) {
    this.cashPending = true;
    this.cashError = "";

    try {
      await putJson("/api/settings/simulated_cash_eur", { value });
      this.settings.value = {
        ...this.settings.value,
        simulated_cash_eur: value,
      };
      this.cancelCashEdit();
      await this.portfolio.refresh();
      window.dispatchEvent(
        new CustomEvent("sentinel-setting-changed", {
          detail: { key: "simulated_cash_eur", value, source: this },
        }),
      );
    } catch (error) {
      this.cashError = error.message;
    } finally {
      this.cashPending = false;
    }
  }

  async saveCash(event) {
    event.preventDefault();
    const draft = this.cashDraft.trim();
    const value = draft === "" ? null : Number(draft);

    if (value !== null && !Number.isFinite(value)) {
      this.cashError = "Cash must be a finite number.";
      return;
    }

    await this.setCashOverride(value);
  }

  renderCash(portfolio) {
    if (this.editingCash && this.isResearchMode) {
      return html`
        <form
          class="sentinel-layout"
          data-align="center"
          data-wrap
          @submit=${this.saveCash}
        >
          <label class="sentinel-layout" data-align="center">
            <span>Cash</span>
            <wa-input
              size="small"
              aria-label="Simulated cash in EUR"
              type="number"
              step="any"
              style="inline-size: 12ch; max-inline-size: 100%"
              .value=${this.cashDraft}
              ?disabled=${this.cashPending}
              @input=${(event) => (this.cashDraft = event.currentTarget.value)}
              @keydown=${(event) => {
                if (event.key === "Escape") this.cancelCashEdit();
              }}
            ></wa-input>
          </label>
          <wa-button size="small" type="submit" ?disabled=${this.cashPending}
            >${this.cashPending ? "Saving…" : "Apply"}</wa-button
          >
          <wa-button
            size="small"
            type="button"
            ?disabled=${this.cashPending}
            @click=${this.cancelCashEdit}
            >Cancel</wa-button
          >
        </form>
      `;
    }

    return html`
      <div class="sentinel-layout" data-align="baseline" data-wrap>
        <span
          >Cash&nbsp;<strong>${formatCurrency(
            portfolio.total_cash_eur,
          )}</strong>${this.cashIsSimulated
            ? ""
            : this.renderCashBreakdown(portfolio.cash)}</span
        >
        ${this.cashIsSimulated
          ? html`<span data-tone="warning">[simulated]</span>`
          : ""}
        ${this.isResearchMode
          ? html`
              <wa-button
                size="xs"
                appearance="plain"
                aria-label="Edit simulated cash"
                title="Change the cash used by research-mode planning"
                ?disabled=${this.cashPending}
                @click=${this.startCashEdit}
                >Edit</wa-button
              >
              ${this.cashIsSimulated
                ? html`<wa-button
                    size="xs"
                    appearance="plain"
                    aria-label="Use real cash"
                    title="Clear the simulated cash override"
                    ?disabled=${this.cashPending}
                    @click=${() => this.setCashOverride(null)}
                    >Use real</wa-button
                  >`
                : ""}
            `
          : ""}
      </div>
      ${this.cashError
        ? html`<span data-tone="error">${this.cashError}</span>`
        : ""}
    `;
  }

  renderPortfolio() {
    const portfolio = this.portfolio.value;
    const totalProfit = Number(this.cashFlows.value?.total_profit);
    const valueVariant =
      totalProfit > 0 ? "success" : totalProfit < 0 ? "error" : undefined;

    return html`
      <div class="sentinel-layout" data-align="baseline" data-wrap>
        <span
          >Value&nbsp;<strong
            ><span data-tone=${valueVariant}
              >${formatCurrency(portfolio.total_value_eur)}</span
            ></strong
          ></span
        >

        ${this.renderCash(portfolio)}
      </div>
    `;
  }

  renderCashFlows() {
    const cashFlows = this.cashFlows.value;

    if (!cashFlows) {
      return "";
    }

    const totalFees = cashFlows.fees + cashFlows.taxes;
    return html`
      <div class="sentinel-layout" data-align="baseline" data-wrap>
        <span
          >Deposits&nbsp;<strong
            >${formatCurrency(cashFlows.deposits)}</strong
          ></span
        >

        <span
          >Withdrawals&nbsp;<strong
            >${formatCurrency(cashFlows.withdrawals)}</strong
          ></span
        >

        <span
          >Dividends&nbsp;<strong
            >${formatCurrency(cashFlows.dividends)}</strong
          ></span
        >

        <span>Fees&nbsp;<strong>${formatCurrency(totalFees)}</strong></span>
        <span aria-hidden="true">&nbsp;&nbsp;—&nbsp;&nbsp;</span>
        <span
          >Total Profit&nbsp;<strong
            ><span data-tone="warning"
              >${formatCurrency(cashFlows.total_profit)}</span
            ></strong
          ></span
        >
      </div>
    `;
  }

  render() {
    let content;

    if (this.portfolio.loading && !this.portfolio.value) {
      content = html`<span>Loading portfolio…</span>`;
    } else if (this.portfolio.error) {
      content = html`<span data-tone="error">Portfolio unavailable</span>`;
    } else {
      content = this.renderPortfolio();
    }

    return html`<section aria-label="Portfolio status">
      ${content}${this.renderCashFlows()}
    </section>`;
  }
}

customElements.define("sentinel-portfolio-status", SentinelPortfolioStatus);
