import { LitElement, html } from "lit";
import { getJson, postJson } from "./api.js";
import { LiveResource } from "./live-resource.js";
import { formatDateTime, formatNumber } from "./modal-utils.js";

class SentinelTrades extends LitElement {
  static properties = {
    page: { state: true },
    symbol: { state: true },
    side: { state: true },
    startDate: { state: true },
    endDate: { state: true },
    syncing: { state: true },
    actionError: { state: true },
  };

  constructor() {
    super();
    this.page = 1;
    this.symbol = "";
    this.side = "";
    this.startDate = "";
    this.endDate = "";
    this.syncing = false;
    this.actionError = "";
  }

  pageSize = 20;

  securities = new LiveResource(
    this,
    (signal) => getJson("/api/securities", { signal }),
    { interval: 60_000 },
  );

  trades = new LiveResource(
    this,
    (signal) => getJson(this.tradesPath, { signal }),
    { interval: 30_000 },
  );

  createRenderRoot() {
    return this;
  }

  get tradesPath() {
    const parameters = new URLSearchParams({
      limit: String(this.pageSize),
      offset: String((this.page - 1) * this.pageSize),
    });

    if (this.symbol) parameters.set("symbol", this.symbol);
    if (this.side) parameters.set("side", this.side);
    if (this.startDate) parameters.set("start_date", this.startDate);
    if (this.endDate) parameters.set("end_date", this.endDate);
    return `/api/trades?${parameters}`;
  }

  changeFilter(name, value) {
    this[name] = value;
    this.page = 1;
    this.trades.refresh();
  }

  changePage(page) {
    this.page = page;
    this.trades.refresh();
  }

  async syncTrades() {
    this.syncing = true;
    this.actionError = "";

    try {
      await postJson("/api/trades/sync");
      await this.trades.refresh();
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.syncing = false;
    }
  }

  renderControls() {
    const symbols = (this.securities.value ?? [])
      .map((security) => security.symbol)
      .sort();

    return html`
      <div class="sentinel-layout" data-align="baseline" data-wrap>
        <label
          >Symbol&nbsp;<wa-select
            size="small"
            .value=${this.symbol}
            @change=${(event) =>
              this.changeFilter("symbol", event.currentTarget.value)}
          >
            <wa-option value="">All symbols</wa-option>
            ${symbols.map(
              (symbol) =>
                html`<wa-option value=${symbol}>${symbol}</wa-option>`,
            )}
          </wa-select></label
        >

        <label
          >Side&nbsp;<wa-select
            size="small"
            .value=${this.side}
            @change=${(event) =>
              this.changeFilter("side", event.currentTarget.value)}
          >
            <wa-option value="">All</wa-option>
            <wa-option value="BUY">Buy</wa-option>
            <wa-option value="SELL">Sell</wa-option>
          </wa-select></label
        >

        <label
          >From&nbsp;<wa-input
            size="small"
            type="date"
            .value=${this.startDate}
            @change=${(event) =>
              this.changeFilter("startDate", event.currentTarget.value)}
          ></wa-input
        ></label>

        <label
          >To&nbsp;<wa-input
            size="small"
            type="date"
            .value=${this.endDate}
            @change=${(event) =>
              this.changeFilter("endDate", event.currentTarget.value)}
          ></wa-input
        ></label>

        <wa-button
          size="small"
          ?disabled=${this.syncing}
          @click=${this.syncTrades}
          >${this.syncing ? "Syncing…" : "Sync from Broker"}</wa-button
        >
      </div>
    `;
  }

  renderTable() {
    const trades = this.trades.value?.trades ?? [];

    if (trades.length === 0) {
      return html`<div>No trades found</div>`;
    }

    return html`
      <div style="overflow: auto; min-width: 0">
        <table style="border-collapse: collapse; width: 100%">
          <thead>
            <tr>
              <th style="text-align: left">Date</th>
              <th style="text-align: left">Symbol</th>
              <th style="text-align: left">Side</th>
              <th style="text-align: left">Qty</th>
              <th style="text-align: left">Price</th>
              <th style="text-align: left">Value</th>
              <th style="text-align: left">Commission</th>
              <th style="text-align: left">Currency</th>
            </tr>
          </thead>
          <tbody>
            ${trades.map((trade) => {
              const raw = trade.raw_data ?? {};
              const quantity = Number(raw.q ?? trade.quantity ?? 0);
              const price = Number(raw.p ?? trade.price ?? 0);
              const value = Number(raw.v ?? quantity * price);
              const commission = Number(
                raw.commiss_exchange ?? trade.commission ?? 0,
              );
              const currency = raw.curr_c ?? trade.commission_currency ?? "-";

              return html`
                <tr>
                  <td style="text-align: left; vertical-align: top">
                    ${formatDateTime(trade.executed_at, { seconds: true })}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${trade.symbol}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    <span
                      data-tone=${trade.side === "BUY" ? "success" : "error"}
                      >${trade.side}</span
                    >
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatNumber(quantity, 0)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatNumber(price, 2)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatNumber(value, 2)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatNumber(commission, 2)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${currency}
                  </td>
                </tr>
              `;
            })}
          </tbody>
        </table>
      </div>
    `;
  }

  renderPagination() {
    const total = this.trades.value?.total ?? this.trades.value?.count ?? 0;
    const pages = Math.max(1, Math.ceil(total / this.pageSize));

    if (pages === 1) {
      return "";
    }

    return html`
      <div>
        <wa-button
          size="small"
          ?disabled=${this.page <= 1}
          @click=${() => this.changePage(this.page - 1)}
          >Previous</wa-button
        >
        Page ${this.page} / ${pages}
        <wa-button
          size="small"
          ?disabled=${this.page >= pages}
          @click=${() => this.changePage(this.page + 1)}
          >Next</wa-button
        >
      </div>
    `;
  }

  render() {
    if (this.securities.loading && !this.securities.value) {
      return html`<div>Loading trade filters…</div>`;
    }

    return html`
      ${this.renderControls()}
      <div aria-hidden="true">&nbsp;</div>
      ${this.trades.loading && !this.trades.value
        ? html`<div>Loading trades…</div>`
        : this.trades.error
          ? html`<span data-tone="error"
              >Error loading trades: ${this.trades.error.message}</span
            >`
          : this.renderTable()}
      ${this.renderPagination()}
      ${this.actionError
        ? html`<span data-tone="error">${this.actionError}</span>`
        : ""}
    `;
  }
}

customElements.define("sentinel-trades", SentinelTrades);
