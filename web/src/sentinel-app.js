import { LitElement, html } from "lit";

class SentinelApp extends LitElement {
  createRenderRoot() {
    return this;
  }

  render() {
    return html`
      <div
        class="sentinel-layout"
        data-direction="column"
        style="height: 100dvh; overflow: hidden"
      >
        <sentinel-header
          style="display: block; flex: 0 0 auto"
        ></sentinel-header>
        <main style="flex: 1 1 auto; min-height: 0; overflow: auto">
          <sentinel-portfolio-status
            style="display: block"
          ></sentinel-portfolio-status>
          <sentinel-planner-status
            style="display: block"
          ></sentinel-planner-status>
          <sentinel-portfolio-value
            style="display: block"
          ></sentinel-portfolio-value>
          <sentinel-portfolio-pnl
            style="display: block"
          ></sentinel-portfolio-pnl>
          <sentinel-securities style="display: block"></sentinel-securities>
          <sentinel-inactive-securities
            style="display: block"
          ></sentinel-inactive-securities>
          <sentinel-risk-return style="display: block"></sentinel-risk-return>
          <sentinel-security-allocation
            style="display: block"
          ></sentinel-security-allocation>
        </main>
        <sentinel-status-bar
          style="display: block; flex: 0 0 auto"
        ></sentinel-status-bar>
      </div>
    `;
  }
}

customElements.define("sentinel-app", SentinelApp);
