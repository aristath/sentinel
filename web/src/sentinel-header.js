import { LitElement, html } from "lit";
import { getJson } from "./api.js";
import { LiveResource } from "./live-resource.js";
import "./sentinel-backtest.js";
import "./sentinel-research.js";
import "./sentinel-scheduler.js";
import "./sentinel-settings.js";
import "./sentinel-trades.js";

const actions = [
  {
    id: "backtest",
    label: "Backtest",
    heading: "Backtest",
    researchOnly: true,
  },
  { id: "trades", label: "Trades", heading: "Trade History" },
  { id: "scheduler", label: "Scheduler", heading: "Scheduler" },
  { id: "research", label: "Research", heading: "Research Pipeline" },
  { id: "settings", label: "Settings", heading: "Settings" },
];

class SentinelHeader extends LitElement {
  static properties = {
    activeModal: { state: true },
  };

  constructor() {
    super();
    this.activeModal = undefined;
  }

  health = new LiveResource(
    this,
    (signal) => getJson("/api/health", { signal }),
    { interval: 30_000 },
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

  openModal(id) {
    this.activeModal = id;
  }

  closeModal(id) {
    if (this.activeModal === id) {
      this.activeModal = undefined;
    }
  }

  async requestModalClose(event) {
    if (event.target !== event.currentTarget) return;
    const dialog = event.currentTarget;
    if (this.confirmedClose === dialog) {
      this.confirmedClose = undefined;
      return;
    }
    const tasks = dialog.querySelector("sentinel-tasks");
    if (!tasks?.dirty) return;

    event.preventDefault();
    if (this.confirmingClose) return;
    this.confirmingClose = true;
    try {
      if ((await tasks.confirmClose()) && dialog.isConnected) {
        this.confirmedClose = dialog;
        dialog.open = false;
      }
    } finally {
      this.confirmingClose = false;
    }
  }

  get visibleActions() {
    const live = this.health.value?.trading_mode === "live";

    return actions.filter((action) => !action.researchOnly || !live);
  }

  renderAction(action) {
    const modalId = `sentinel-${action.id}-modal`;

    return html`
      <wa-button
        size="xs"
        appearance="plain"
        variant="neutral"
        aria-controls=${modalId}
        aria-expanded=${this.activeModal === action.id ? "true" : "false"}
        @click=${() => this.openModal(action.id)}
        >${action.label}</wa-button
      >
    `;
  }

  renderModalContent(id) {
    switch (id) {
      case "backtest":
        return html`<sentinel-backtest></sentinel-backtest>`;
      case "trades":
        return html`<sentinel-trades></sentinel-trades>`;
      case "scheduler":
        return html`<sentinel-scheduler></sentinel-scheduler>`;
      case "research":
        return html`<sentinel-research></sentinel-research>`;
      case "settings":
        return html`<sentinel-settings></sentinel-settings>`;
      default:
        return "";
    }
  }

  renderModal() {
    const action = actions.find(({ id }) => id === this.activeModal);

    if (!action) {
      return "";
    }

    return html`
      <wa-dialog
        id=${`sentinel-${action.id}-modal`}
        label=${action.heading}
        open
        @wa-hide=${this.requestModalClose}
        @wa-after-hide=${(event) => {
          if (event.target === event.currentTarget) this.closeModal(action.id);
        }}
        >${this.renderModalContent(action.id)}</wa-dialog
      >
    `;
  }

  render() {
    return html`
      <header>
        <div class="sentinel-toolbar">
          <nav aria-label="Application">
            <div
              class="sentinel-layout sentinel-app-nav"
              data-align="center"
              data-wrap
            >
              ${this.visibleActions.map((action) => this.renderAction(action))}
            </div>
          </nav>
        </div>
        ${this.renderModal()}
      </header>
    `;
  }
}

customElements.define("sentinel-header", SentinelHeader);
