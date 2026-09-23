import { LitElement, html } from "lit";
import { getJson, putJson } from "./api.js";
import { LiveResource } from "./live-resource.js";

const tradingFields = [
  {
    key: "trading_mode",
    label: "Trading Mode",
    description: "Research mode simulates trades without executing",
    type: "select",
    default: "research",
    options: [
      ["research", "Research (Paper Trading)"],
      ["live", "Live Trading"],
    ],
  },
  {
    key: "max_position_pct",
    label: "Max Position %",
    description: "Maximum allocation to a single security",
    type: "number",
    default: 20,
    min: 5,
    max: 100,
  },
  {
    key: "min_position_pct",
    label: "Min Position %",
    description: "Minimum allocation to maintain a position",
    type: "number",
    default: 2,
    min: 0.5,
    max: 20,
    step: 0.5,
  },
  {
    key: "target_cash_pct",
    label: "Target Cash %",
    description: "Target cash allocation in portfolio",
    type: "number",
    default: 0,
    min: 0,
    max: 50,
  },
  {
    key: "min_cash_buffer",
    label: "Min Cash Buffer %",
    description: "Minimum cash to keep as safety buffer",
    type: "number",
    default: 0.005,
    min: 0,
    max: 10,
    step: 0.01,
    scale: 100,
  },
  {
    key: "min_trade_value",
    label: "Min Trade Value (EUR)",
    description: "Minimum trade value in EUR",
    type: "number",
    default: 100,
    min: 10,
    max: 10000,
  },
];

const feeFields = [
  {
    key: "transaction_fee_fixed",
    label: "Fixed Transaction Fee (EUR)",
    description: "Fixed fee per trade",
    type: "number",
    default: 2,
    min: 0,
    max: 50,
    step: 0.01,
  },
  {
    key: "transaction_fee_percent",
    label: "Variable Transaction Fee %",
    description: "Fee as percentage of trade value",
    type: "number",
    default: 0.2,
    min: 0,
    max: 5,
    step: 0.01,
  },
];

const strategyDraftFields = [
  [
    "strategy_min_opp_score",
    "Minimum Opportunity Score",
    0.55,
    0,
    1,
    0.001,
    "Minimum opp score required to enter opportunity sleeve",
  ],
  [
    "strategy_ideal_qualifying_threshold",
    "Ideal Qualification Threshold",
    0.65,
    0,
    1,
    0.001,
    "Minimum AI research multiplier required for an ideal target",
  ],
  [
    "strategy_core_timing_min_score",
    "Core Timing Score",
    0.3,
    0,
    1,
    0.001,
    "Minimum opportunity score for a normally timed core buy",
  ],
  [
    "strategy_core_timing_min_dip_score",
    "Core Timing Dip",
    0.2,
    0,
    1,
    0.001,
    "Minimum dip score for a normally timed core buy",
  ],
  [
    "strategy_fallback_wait_days",
    "Fallback Wait",
    30,
    0,
    365,
    1,
    "Days without an executable opportunity before one convergence buy",
  ],
  [
    "strategy_entry_t1_dd",
    "Entry T1 Drawdown",
    -0.1,
    -0.9,
    0,
    0.001,
    "First opportunity tranche threshold (dd252)",
  ],
  [
    "strategy_entry_t2_dd",
    "Entry T2 Drawdown",
    -0.16,
    -0.9,
    0,
    0.001,
    "Second opportunity tranche threshold (dd252)",
  ],
  [
    "strategy_entry_t3_dd",
    "Entry T3 Drawdown",
    -0.22,
    -0.9,
    0,
    0.001,
    "Third opportunity tranche threshold (dd252)",
  ],
  [
    "strategy_entry_memory_days",
    "Entry Memory Days",
    45,
    1,
    252,
    1,
    "Keep recent-dip memory active for post-turn entries",
  ],
  [
    "strategy_memory_max_boost",
    "Memory Max Boost",
    0.12,
    0,
    0.5,
    0.001,
    "Maximum boost added to opp score from recent dip memory",
  ],
  [
    "strategy_opportunity_addon_threshold",
    "Opportunity Add-On Threshold",
    0.75,
    0,
    1,
    0.001,
    "Allow add-on buys for held opportunity names above this score",
  ],
  [
    "strategy_max_opportunity_buys_per_cycle",
    "Max Opportunity Buys / Cycle",
    1,
    0,
    50,
    1,
    "Hard cap on total opportunity buys per rebalance cycle",
  ],
  [
    "strategy_max_new_opportunity_buys_per_cycle",
    "Max New Opportunity Buys / Cycle",
    1,
    0,
    50,
    1,
    "Hard cap on opening new opportunity positions per cycle",
  ],
].map(([key, label, defaultValue, min, max, step, description]) => ({
  key,
  label,
  default: defaultValue,
  min,
  max,
  step,
  description,
  type: "number",
}));

const strategyFields = [
  [
    "strategy_deposit_history_months",
    "Deposit History Months",
    12,
    1,
    36,
    1,
    "Months of deposits and withdrawals used to calculate monthly net contributions",
  ],
  [
    "rebalance_threshold_pct",
    "Rebalance Threshold %",
    5,
    1,
    20,
    1,
    "Minimum deviation to trigger rebalance",
  ],
  [
    "strategy_lot_standard_max_pct",
    "Standard Lot Max %",
    0.08,
    0,
    100,
    0.01,
    "Max ticket size treated as standard lot class",
    100,
  ],
  [
    "strategy_lot_coarse_max_pct",
    "Coarse Lot Max %",
    0.3,
    0,
    100,
    0.01,
    "Max ticket size treated as coarse lot class",
    100,
  ],
  [
    "strategy_coarse_max_new_lots_per_cycle",
    "Coarse Max New Lots",
    1,
    1,
    10,
    1,
    "Max new coarse lots per rebalance cycle",
  ],
  [
    "strategy_opportunity_cooloff_days",
    "Opportunity Cool-Off Days",
    7,
    0,
    365,
    1,
    "Minimum days between opposite actions for opportunity sleeve",
  ],
  [
    "strategy_core_cooloff_days",
    "Core Cool-Off Days",
    21,
    0,
    365,
    1,
    "Minimum days between opposite actions for core sleeve",
  ],
  [
    "strategy_same_side_cooloff_days",
    "Same-Side Cool-Off Days",
    15,
    0,
    365,
    1,
    "Minimum days between same-side actions",
  ],
  [
    "strategy_rotation_time_stop_days",
    "Rotation Time-Stop Days",
    90,
    1,
    365,
    1,
    "Exit opportunity positions if the thesis stalls beyond this horizon",
  ],
].map(([key, label, defaultValue, min, max, step, description, scale]) => ({
  key,
  label,
  default: defaultValue,
  min,
  max,
  step,
  description,
  scale,
  type: "number",
}));

const forecastFields = [
  {
    key: "forecasting_enabled",
    label: "Forecast timing",
    description: "Use stored forecasts as a bounded opportunity-score modifier",
    type: "toggle",
    default: true,
  },
  {
    key: "forecasting_service_url",
    label: "Forecasting Service URL",
    type: "text",
    default: "http://127.0.0.1:8010",
  },
  {
    key: "forecasting_provider",
    label: "Provider",
    type: "select",
    default: "toto2",
    options: [
      ["toto2", "Toto 2.0"],
      ["naive", "Naive local test provider"],
    ],
  },
  {
    key: "forecasting_model_id",
    label: "Model ID",
    type: "text",
    default: "Datadog/Toto-2.0-1B",
  },
  {
    key: "forecasting_horizon_weeks",
    label: "Horizon (weeks)",
    description: "Forecast horizon in weekly steps",
    type: "number",
    default: 4,
    min: 1,
    max: 52,
  },
  {
    key: "forecasting_context_weeks",
    label: "Context (weeks)",
    description: "Maximum weekly return history sent to the model",
    type: "number",
    default: 520,
    min: 104,
    max: 1040,
  },
  {
    key: "forecasting_min_history_weeks",
    label: "Minimum History (weeks)",
    type: "number",
    default: 104,
    min: 52,
    max: 520,
  },
  {
    key: "forecasting_max_group_variates",
    label: "Max Group Variates",
    description: "Maximum securities in one grouped multivariate request",
    type: "number",
    default: 32,
    min: 1,
    max: 256,
  },
  {
    key: "forecasting_stale_after_days",
    label: "Stale Price Limit (days)",
    type: "number",
    default: 21,
    min: 1,
    max: 120,
  },
  {
    key: "forecasting_max_missing_ratio",
    label: "Max Missing Input %",
    description: "Forecast run fails above this unusable-symbol ratio",
    type: "number",
    default: 0.25,
    min: 0,
    max: 100,
    step: 0.1,
    scale: 100,
  },
  {
    key: "forecasting_score_max_age_days",
    label: "Score Freshness (days)",
    description: "Planner ignores forecast scores older than this",
    type: "number",
    default: 14,
    min: 1,
    max: 90,
  },
  {
    key: "forecasting_timing_weight",
    label: "Timing Weight",
    description: "Maximum absolute opportunity-score adjustment",
    type: "number",
    default: 0.15,
    min: 0,
    max: 0.5,
    step: 0.001,
  },
];

const researchGroups = [
  [
    "Model and research tools",
    [
      { key: "ai_llm_base_url", label: "LLM URL", type: "text", default: "" },
      { key: "ai_llm_model", label: "Model", type: "model", default: "" },
      {
        key: "ai_llm_api_key",
        label: "LLM API key",
        type: "password",
        default: "",
      },
      {
        key: "ai_searxng_base_url",
        label: "Search URL",
        type: "text",
        default: "",
      },
      {
        key: "ai_browser_search_base_url",
        label: "Search fallback",
        type: "text",
        default: "",
      },
      {
        key: "ai_firefox_mcp_base_url",
        label: "Firefox MCP",
        type: "text",
        default: "",
      },
      {
        key: "ai_url_summarizer_base_url",
        label: "URL summarizer",
        type: "text",
        default: "",
      },
    ],
  ],
  [
    "Research memory",
    [
      {
        key: "ai_pg_host",
        label: "PostgreSQL host",
        type: "text",
        default: "",
      },
      {
        key: "ai_pg_port",
        label: "PostgreSQL port",
        type: "number",
        default: 5432,
        min: 1,
        max: 65535,
      },
      { key: "ai_pg_database", label: "Database", type: "text", default: "" },
      { key: "ai_pg_user", label: "Database user", type: "text", default: "" },
      {
        key: "ai_pg_password",
        label: "Database password",
        type: "password",
        default: "",
      },
      {
        key: "ai_embed_base_url",
        label: "Embedding URL",
        type: "text",
        default: "",
      },
      {
        key: "ai_embed_model",
        label: "Embedding model",
        type: "text",
        default: "",
      },
      {
        key: "ai_embed_dims",
        label: "Embedding dimensions",
        type: "number",
        default: 768,
        min: 1,
      },
      {
        key: "ai_memory_user_id",
        label: "Memory user",
        type: "text",
        default: "",
      },
      {
        key: "ai_memory_collection",
        label: "Memory collection",
        type: "text",
        default: "",
      },
    ],
  ],
  [
    "Cadence and limits",
    [
      {
        key: "ai_dedup_similarity_threshold",
        label: "Dedup similarity",
        type: "number",
        default: 0.96,
        min: 0,
        max: 1,
        step: 0.01,
      },
      {
        key: "ai_llm_timeout_seconds",
        label: "LLM timeout (seconds)",
        type: "number",
        default: 3600,
        min: 1,
      },
      {
        key: "ai_max_tool_calls",
        label: "Maximum tool calls",
        type: "number",
        default: 40,
        min: 1,
        max: 100,
      },
      {
        key: "ai_max_tool_loop_iterations",
        label: "Maximum tool rounds",
        type: "number",
        default: 40,
        min: 1,
        max: 100,
      },
    ],
  ],
];

const apiFields = [
  {
    key: "tradernet_api_key",
    label: "Tradernet API Key",
    description: "Your Tradernet public API key",
    type: "text",
    default: "",
  },
  {
    key: "tradernet_api_secret",
    label: "Tradernet API Secret",
    description: "Your Tradernet private API secret",
    type: "password",
    default: "",
  },
  {
    key: "freedom24_login",
    label: "Freedom24 Login",
    description: "Email used to sign in at freedom24.com",
    type: "text",
    default: "",
  },
  {
    key: "freedom24_password",
    label: "Freedom24 Password",
    description: "Web login password, not your API secret",
    type: "password",
    default: "",
  },
];

const backupFields = [
  {
    key: "r2_account_id",
    label: "R2 Account ID",
    description: "Your Cloudflare account ID",
    type: "text",
    default: "",
  },
  {
    key: "r2_access_key",
    label: "R2 Access Key",
    description: "R2 API token access key",
    type: "text",
    default: "",
  },
  {
    key: "r2_secret_key",
    label: "R2 Secret Key",
    description: "R2 API token secret key",
    type: "password",
    default: "",
  },
  {
    key: "r2_bucket_name",
    label: "R2 Bucket Name",
    description: "Name of the R2 bucket to store backups",
    type: "text",
    default: "",
  },
  {
    key: "r2_backup_retention_days",
    label: "Retention Days",
    description: "Automatically delete backups older than this",
    type: "number",
    default: 30,
    min: 1,
    max: 365,
  },
];

class SentinelSettings extends LitElement {
  static properties = {
    tab: { state: true },
    strategyDraft: { state: true },
    busyKey: { state: true },
    notice: { state: true },
    actionError: { state: true },
  };

  constructor() {
    super();
    this.tab = "trading";
    this.strategyDraft = undefined;
    this.busyKey = "";
    this.notice = "";
    this.actionError = "";
  }

  settings = new LiveResource(
    this,
    (signal) => getJson("/api/settings", { signal }),
    { interval: 0 },
  );

  models = new LiveResource(
    this,
    (signal) => getJson("/api/ai/models", { signal }),
    { interval: 0 },
  );

  createRenderRoot() {
    return this;
  }

  updated() {
    if (this.settings.value && !this.strategyDraft) {
      this.strategyDraft = Object.fromEntries(
        strategyDraftFields.map((field) => [
          field.key,
          Number(this.settings.value[field.key] ?? field.default),
        ]),
      );
    }
  }

  displayValue(field, source = this.settings.value) {
    const value = source?.[field.key] ?? field.default;
    return field.scale ? Number(value) * field.scale : value;
  }

  parseValue(field, value) {
    if (field.type !== "number") return value;
    const number = Number(value);
    return field.scale ? number / field.scale : number;
  }

  async updateSetting(field, value) {
    const parsed = this.parseValue(field, value);
    const previous = this.settings.value?.[field.key];
    this.busyKey = field.key;
    this.notice = "";
    this.actionError = "";
    this.settings.value = { ...this.settings.value, [field.key]: parsed };
    this.requestUpdate();

    try {
      await putJson(`/api/settings/${encodeURIComponent(field.key)}`, {
        value: parsed,
      });
      this.notice = `${field.label} saved`;
      window.dispatchEvent(
        new CustomEvent("sentinel-setting-changed", {
          detail: { key: field.key, value: parsed },
        }),
      );
    } catch (error) {
      this.settings.value = { ...this.settings.value, [field.key]: previous };
      this.actionError = error.message;
      this.requestUpdate();
    } finally {
      this.busyKey = "";
    }
  }

  changeStrategy(field, value) {
    this.strategyDraft = {
      ...this.strategyDraft,
      [field.key]: Number(value),
    };
  }

  async applyStrategy() {
    this.busyKey = "strategy";
    this.notice = "";
    this.actionError = "";

    try {
      await putJson("/api/settings", { values: this.strategyDraft });
      this.settings.value = {
        ...this.settings.value,
        ...this.strategyDraft,
      };
      this.notice = "Strategy tuning saved";
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.busyKey = "";
    }
  }

  renderField(field, source = this.settings.value, strategy = false) {
    const value = this.displayValue(field, source);
    const disabled = this.busyKey !== "";
    let control;

    if (field.type === "toggle") {
      control = html`<tui-toggle
        ?checked=${Boolean(value)}
        ?disabled=${disabled}
        @change=${(event) =>
          this.updateSetting(field, event.currentTarget.checked)}
        >${field.label}</tui-toggle
      >`;
    } else if (field.type === "select") {
      control = html`<label
        >${field.label}&nbsp;<tui-select
          value=${value}
          ?disabled=${disabled}
          @change=${(event) =>
            this.updateSetting(field, event.currentTarget.value)}
        >
          ${field.options.map(
            ([optionValue, label]) => html`
              <option value=${optionValue}>${label}</option>
            `,
          )}
        </tui-select></label
      >`;
    } else {
      const type =
        field.type === "password"
          ? "password"
          : field.type === "number"
            ? "number"
            : "text";
      control = html`<label
        ><span>${field.label}</span>
        <tui-input
          block
          type=${type}
          value=${value ?? ""}
          min=${field.min ?? ""}
          max=${field.max ?? ""}
          step=${field.step ?? (field.type === "number" ? 1 : "")}
          list=${field.type === "model" ? "sentinel-ai-models" : ""}
          ?disabled=${disabled}
          @change=${(event) =>
            strategy
              ? this.changeStrategy(field, event.currentTarget.value)
              : this.updateSetting(field, event.currentTarget.value)}
        ></tui-input
      ></label>`;
    }

    return html`
      <div style="min-width: 0; overflow-wrap: anywhere">
        ${control}
        ${field.description ? html`<div>${field.description}</div>` : ""}
      </div>
    `;
  }

  renderFields(fields, source = this.settings.value, strategy = false) {
    return fields.map(
      (field, index) => html`
        ${index > 0 ? html`<div aria-hidden="true">&nbsp;</div>` : ""}
        ${this.renderField(field, source, strategy)}
      `,
    );
  }

  renderResearch() {
    return html`
      <datalist id="sentinel-ai-models">
        ${(this.models.value?.models ?? []).map(
          (model) => html`<option value=${model}></option>`,
        )}
      </datalist>
      ${researchGroups.map(
        ([heading, fields], index) => html`
          ${index > 0 ? html`<div aria-hidden="true">&nbsp;</div>` : ""}
          <tui-box heading=${heading} border="single">
            <tui-flex align="start" wrap>
              ${fields.map(
                (field) => html`
                  <div style="flex: 1 1 38ch; min-width: 0">
                    ${this.renderField(field)}
                  </div>
                `,
              )}
            </tui-flex>
            ${
              heading === "Model and research tools"
                ? html`<div>
                    <tui-button @click=${() => this.models.refresh()}
                      >Refresh available models</tui-button
                    >
                    ${
                      this.models.error
                        ? html`<tui-text variant="error"
                            >${this.models.error.message}</tui-text
                          >`
                        : ""
                    }
                  </div>`
                : ""
            }
          </tui-box>
        `,
      )}
    `;
  }

  renderPanel() {
    switch (this.tab) {
      case "fees":
        return this.renderFields(feeFields);
      case "strategy":
        return html`
          <tui-box heading="Strategy Tuning" border="single">
            ${this.renderFields(strategyDraftFields, this.strategyDraft, true)}
            <div aria-hidden="true">&nbsp;</div>
            <tui-button
              ?disabled=${this.busyKey !== ""}
              @click=${this.applyStrategy}
              >Apply Strategy Tuning</tui-button
            >
          </tui-box>
          <div aria-hidden="true">&nbsp;</div>
          ${this.renderFields(strategyFields)}
        `;
      case "forecasting":
        return this.renderFields(forecastFields);
      case "research":
        return this.renderResearch();
      case "api":
        return html`
          ${this.renderFields(apiFields.slice(0, 2))}
          <div aria-hidden="true">&nbsp;</div>
          <tui-box heading="Freedom24 web login" border="single">
            <div>
              Used only to fetch PRAAMS portfolio-structure data not exposed by
              the public API.
            </div>
            ${this.renderFields(apiFields.slice(2))}
          </tui-box>
        `;
      case "backup":
        return html`
          <div>
            Back up the database, runtime state, task definitions, and research
            artifacts to Cloudflare R2.
          </div>
          <div aria-hidden="true">&nbsp;</div>
          ${this.renderFields(backupFields)}
        `;
      default:
        return this.renderFields(tradingFields);
    }
  }

  render() {
    if (this.settings.loading && !this.settings.value) {
      return html`<div>Loading settings…</div>`;
    }

    if (this.settings.error) {
      return html`<tui-text variant="error"
        >Error loading settings: ${this.settings.error.message}</tui-text
      >`;
    }

    return html`
      <tui-radio-buttonset
        aria-label="Settings section"
        value=${this.tab}
        @change=${(event) => (this.tab = event.currentTarget.value)}
      >
        <tui-radio-button value="trading">Trading</tui-radio-button>
        <tui-radio-button value="fees">Fees</tui-radio-button>
        <tui-radio-button value="strategy">Strategy</tui-radio-button>
        <tui-radio-button value="forecasting">Forecasts</tui-radio-button>
        <tui-radio-button value="research">Research</tui-radio-button>
        <tui-radio-button value="api">API</tui-radio-button>
        <tui-radio-button value="backup">Backup</tui-radio-button>
      </tui-radio-buttonset>
      <div aria-hidden="true">&nbsp;</div>
      ${this.renderPanel()}
      ${
        this.busyKey
          ? html`<div aria-live="polite">Saving ${this.busyKey}…</div>`
          : ""
      }
      ${this.notice ? html`<div aria-live="polite">${this.notice}</div>` : ""}
      ${
        this.actionError
          ? html`<tui-text variant="error">${this.actionError}</tui-text>`
          : ""
      }
    `;
  }
}

customElements.define("sentinel-settings", SentinelSettings);
