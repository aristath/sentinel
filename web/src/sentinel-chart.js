import { LitElement, css, html, svg } from "lit";

class SentinelChart extends LitElement {
  static properties = {
    values: { attribute: false },
    min: { type: Number },
    max: { type: Number },
    threshold: { type: String },
    height: { type: Number },
    compact: { type: Boolean, reflect: true },
  };

  static styles = css`
    :host {
      display: block;
      min-inline-size: 0;
    }

    :host([compact]) {
      display: inline-block;
      inline-size: 4.5rem;
      vertical-align: middle;
    }

    svg {
      display: block;
      inline-size: 100%;
    }

    path {
      fill: none;
      stroke-width: 1.5;
      stroke-linecap: round;
      stroke-linejoin: round;
      vector-effect: non-scaling-stroke;
    }
  `;

  constructor() {
    super();
    this.values = [];
    this.height = 4;
    this.compact = false;
  }

  render() {
    const values = this.values.filter(Number.isFinite);
    if (values.length < 2) return "";

    const minimum = this.min ?? Math.min(...values);
    const maximum = this.max ?? Math.max(...values);
    const y = (value) =>
      maximum === minimum
        ? 25
        : 2 + (46 * (maximum - value)) / (maximum - minimum);
    const points = values
      .map(
        (value, index) =>
          `${index === 0 ? "M" : "L"}${2 + (196 * index) / (values.length - 1)},${y(value)}`,
      )
      .join(" ");
    const threshold = this.threshold ? Number(this.threshold) : NaN;

    return html`
      <svg
        aria-hidden="true"
        viewBox="0 0 200 50"
        preserveAspectRatio="none"
        style="block-size: ${this.compact ? 1.4 : this.height * 1.25}rem"
      >
        ${Number.isFinite(threshold)
          ? this.renderThreshold(points, y(threshold))
          : svg`
          <path d=${points} stroke="var(--wa-color-text-quiet)"></path>
        `}
      </svg>
    `;
  }

  renderThreshold(points, position) {
    const y = Math.max(0, Math.min(position, 50));
    return svg`
      <defs>
        <clipPath id="above"><rect width="200" height=${y}></rect></clipPath>
        <clipPath id="below"><rect y=${y} width="200" height=${50 - y}></rect></clipPath>
      </defs>
      <path
        d="M0,${y} H200"
        stroke="var(--wa-color-surface-border)"
        stroke-dasharray="2 3"
      ></path>
      <path d=${points} clip-path="url(#above)" stroke="var(--wa-color-success-on-normal)"></path>
      <path d=${points} clip-path="url(#below)" stroke="var(--wa-color-danger-on-normal)"></path>
    `;
  }
}

customElements.define("sentinel-chart", SentinelChart);
