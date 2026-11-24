import { LitElement, html } from "lit";
import { getJson } from "./api.js";
import { LiveResource } from "./live-resource.js";
import { storeWidgetCollapsed, widgetCollapsed } from "./widget-state.js";

export class SentinelInactiveSecurities extends LitElement {
  static properties = {
    detailsRequested: { state: true },
    period: { state: true },
  };

  constructor() {
    super();
    this.detailsRequested = !widgetCollapsed("inactive-securities");
    this.period = "1Y";
    this.periodChanged = (event) => {
      this.period = event.detail?.period || "1Y";
      const table = this.querySelector("sentinel-securities");
      if (table) {
        table.period = this.period;
        table.securities.refresh();
      }
    };
    this.securityListChanged = (event) => {
      this.summaries.refresh();
      const table = this.querySelector("sentinel-securities");
      if (table && event.target !== table) {
        table.securities.refresh();
      }
    };
  }

  summaries = new LiveResource(
    this,
    (signal) => getJson("/api/securities", { signal }),
    { interval: 60_000 },
  );

  createRenderRoot() {
    return this;
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener(
      "sentinel-security-period-change",
      this.periodChanged,
    );
    window.addEventListener(
      "sentinel-security-list-change",
      this.securityListChanged,
    );
  }

  disconnectedCallback() {
    window.removeEventListener(
      "sentinel-security-period-change",
      this.periodChanged,
    );
    window.removeEventListener(
      "sentinel-security-list-change",
      this.securityListChanged,
    );
    super.disconnectedCallback();
  }

  toggleDetails(event) {
    const open = event.currentTarget.open;
    storeWidgetCollapsed("inactive-securities", !open);
    if (open && !this.detailsRequested) {
      this.detailsRequested = true;
    }
  }

  render() {
    if (this.summaries.loading && !this.summaries.value) {
      return "";
    }
    if (this.summaries.error) {
      return "";
    }

    const count = (this.summaries.value || []).filter(
      (security) => !security.active,
    ).length;
    if (count === 0) {
      return "";
    }

    return html`
      <wa-details
        ?open=${!widgetCollapsed("inactive-securities")}
        @wa-after-show=${this.toggleDetails}
        @wa-after-hide=${this.toggleDetails}
      >
        <span slot="summary"> Inactive Securities (${count}) </span>
        ${this.detailsRequested
          ? html`<wa-card>
              <sentinel-securities
                inactive-only
                bare
                .period=${this.period}
              ></sentinel-securities>
            </wa-card>`
          : ""}
      </wa-details>
    `;
  }
}

customElements.define(
  "sentinel-inactive-securities",
  SentinelInactiveSecurities,
);
