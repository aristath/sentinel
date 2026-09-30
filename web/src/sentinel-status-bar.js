import { LitElement, html } from "lit";
import { getJson, putJson } from "./api.js";
import { LiveResource } from "./live-resource.js";

class SentinelStatusBar extends LitElement {
  static properties = {
    selectedMode: { state: true },
    modePending: { state: true },
  };

  constructor() {
    super();
    this.selectedMode = undefined;
    this.modePending = false;
  }

  version = new LiveResource(
    this,
    (signal) => getJson("/api/version", { signal }),
    { interval: 0 },
  );

  health = new LiveResource(
    this,
    (signal) => getJson("/api/health", { signal }),
    { interval: 30_000 },
  );

  markets = new LiveResource(
    this,
    (signal) => getJson("/api/markets/status", { signal }),
    { interval: 60_000 },
  );

  refreshHealth = () => this.health.refresh();

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener("sentinel-setting-changed", this.refreshHealth);
  }

  disconnectedCallback() {
    window.removeEventListener("sentinel-setting-changed", this.refreshHealth);
    super.disconnectedCallback();
  }

  createRenderRoot() {
    return this;
  }

  get versionText() {
    return this.version.value?.version ?? "version unavailable";
  }

  renderBrokerStatus() {
    if (this.health.error) {
      return html`<tui-text variant="error">broker: unavailable</tui-text>`;
    }

    if (!this.health.value) {
      return html`<span>broker: connecting</span>`;
    }

    return this.health.value.broker_connected
      ? html`<tui-text variant="success">broker: connected</tui-text>`
      : html`<tui-text variant="error">broker: disconnected</tui-text>`;
  }

  renderMarkets() {
    if (this.markets.error || this.markets.value?.markets?.length === 0) {
      return html`<tui-text variant="error">markets unavailable</tui-text>`;
    }

    if (!this.markets.value) {
      return html`<span>markets loading</span>`;
    }

    return this.markets.value.markets.map(
      (market, index) => html`
        ${index > 0 ? html`<span aria-hidden="true">&nbsp;</span>` : ""}
        <tui-text variant=${market.is_open ? "success" : "error"}
          >${market.name}</tui-text
        >
      `,
    );
  }

  updated() {
    const backendMode = this.health.value?.trading_mode;

    if (!this.modePending && backendMode && backendMode !== this.selectedMode) {
      this.selectedMode = backendMode;
    }
  }

  async changeMode(event) {
    const previousMode = this.health.value?.trading_mode;
    this.selectedMode = event.currentTarget.value;
    this.modePending = true;

    try {
      await putJson("/api/settings/trading_mode", {
        value: this.selectedMode,
      });
      await this.health.refresh();
      window.dispatchEvent(
        new CustomEvent("sentinel-setting-changed", {
          detail: { key: "trading_mode", value: this.selectedMode },
        }),
      );
    } catch (error) {
      this.selectedMode = previousMode;
      console.error("Unable to update trading mode", error);
    } finally {
      this.modePending = false;
    }
  }

  render() {
    return html`
      <footer>
        <tui-bar>
          <tui-flex align="baseline" justify="between" wrap>
            <span>Sentinel ${this.versionText}</span>
            <tui-flex align="baseline" wrap>
              <tui-radio-buttonset
                aria-label="Trading mode"
                value=${this.selectedMode ?? this.health.value?.trading_mode ?? "research"}
                ?disabled=${this.modePending}
                inverted
                @change=${this.changeMode}
              >
                <tui-radio-button value="research">Research</tui-radio-button>
                <tui-radio-button value="live">Live</tui-radio-button>
              </tui-radio-buttonset>
              <span aria-hidden="true">&nbsp;│&nbsp;</span>
              ${this.renderBrokerStatus()}
              <span aria-hidden="true">&nbsp;│&nbsp;</span>
              ${this.renderMarkets()}
            </tui-flex>
          </tui-flex>
        </tui-bar>
      </footer>
    `;
  }
}

customElements.define("sentinel-status-bar", SentinelStatusBar);
