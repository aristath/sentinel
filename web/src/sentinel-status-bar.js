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
      return html`<span data-tone="error">broker: unavailable</span>`;
    }

    if (!this.health.value) {
      return html`<span>broker: connecting</span>`;
    }

    return this.health.value.broker_connected
      ? html`<span data-tone="success">broker: connected</span>`
      : html`<span data-tone="error">broker: disconnected</span>`;
  }

  renderMarkets() {
    if (this.markets.error || this.markets.value?.markets?.length === 0) {
      return html`<span data-tone="error">markets unavailable</span>`;
    }

    if (!this.markets.value) {
      return html`<span>markets loading</span>`;
    }

    return html`
      <div class="sentinel-layout" data-align="center" data-wrap>
        ${this.markets.value.markets.map(
          (market) => html`
            <span data-tone=${market.is_open ? "success" : "error"}
              >${market.name}</span
            >
          `,
        )}
      </div>
    `;
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
        <div class="sentinel-toolbar">
          <div
            class="sentinel-layout sentinel-status-line"
            data-align="center"
            data-wrap
          >
            <wa-radio-group
              size="xs"
              orientation="horizontal"
              aria-label="Trading mode"
              .value=${this.selectedMode ??
              this.health.value?.trading_mode ??
              "research"}
              ?disabled=${this.modePending}
              @change=${this.changeMode}
            >
              <wa-radio appearance="button" value="research">Research</wa-radio>
              <wa-radio appearance="button" value="live">Live</wa-radio>
            </wa-radio-group>

            ${this.renderBrokerStatus()} ${this.renderMarkets()}
            <span class="sentinel-version">Sentinel ${this.versionText}</span>
          </div>
        </div>
      </footer>
    `;
  }
}

customElements.define("sentinel-status-bar", SentinelStatusBar);
