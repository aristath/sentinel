import { LitElement, html } from "lit";
import { getJson, postEventStream, postJson } from "./api.js";
import { LiveResource } from "./live-resource.js";
import {
  formatDuration,
  formatRelativeTime,
  statusVariant,
} from "./modal-utils.js";
import "./sentinel-tasks.js";

class SentinelResearch extends LitElement {
  static properties = {
    tab: { state: true },
    kind: { state: true },
    staleOnly: { state: true },
    ratingSymbol: { state: true },
    busy: { state: true },
    notice: { state: true },
    actionError: { state: true },
    artifactUnit: { state: true },
    activeArtifact: { state: true },
    artifactContent: { state: true },
    artifactLoading: { state: true },
    artifactError: { state: true },
    chatMessages: { state: true },
    chatDraft: { state: true },
    chatBusy: { state: true },
    chatError: { state: true },
  };

  constructor() {
    super();
    this.tab = "status";
    this.kind = "";
    this.staleOnly = false;
    this.ratingSymbol = "";
    this.busy = false;
    this.notice = "";
    this.actionError = "";
    this.artifactUnit = undefined;
    this.activeArtifact = "";
    this.artifactContent = "";
    this.artifactLoading = false;
    this.artifactError = "";
    this.chatMessages = this.loadChatMessages();
    this.chatDraft = "";
    this.chatBusy = false;
    this.chatError = "";
  }

  status = new LiveResource(
    this,
    (signal) => getJson("/api/ai/status", { signal }),
    { interval: 3000 },
  );

  units = new LiveResource(
    this,
    (signal) => getJson(this.unitsPath, { signal }),
    { interval: 10_000 },
  );

  allUnits = new LiveResource(
    this,
    (signal) => getJson("/api/ai/units", { signal }),
    { interval: 10_000 },
  );

  history = new LiveResource(
    this,
    (signal) => getJson("/api/ai/history?limit=100", { signal }),
    { interval: 10_000 },
  );

  createRenderRoot() {
    return this;
  }

  get unitsPath() {
    const parameters = new URLSearchParams();
    if (this.kind) parameters.set("kind", this.kind);
    if (this.staleOnly) parameters.set("stale_only", "true");
    const query = parameters.toString();
    return `/api/ai/units${query ? `?${query}` : ""}`;
  }

  loadChatMessages() {
    try {
      const storageKey = "sentinel-research-chat";
      const stored = window.localStorage.getItem(storageKey);
      const legacy = window.sessionStorage.getItem(storageKey);
      const value = JSON.parse(stored ?? legacy ?? "[]");
      if (stored === null && legacy !== null) {
        window.localStorage.setItem(storageKey, legacy);
        window.sessionStorage.removeItem(storageKey);
      }
      return Array.isArray(value)
        ? value
            .filter(
              (entry) =>
                ["user", "assistant"].includes(entry?.role) &&
                typeof entry?.content === "string",
            )
            .map((entry) => ({ ...entry, pending: false }))
        : [];
    } catch {
      return [];
    }
  }

  persistChatMessages() {
    try {
      window.localStorage.setItem(
        "sentinel-research-chat",
        JSON.stringify(this.chatMessages),
      );
    } catch {
      // The chat remains usable when browser storage is unavailable.
    }
  }

  clearChat() {
    this.chatMessages = [];
    this.chatError = "";
    this.persistChatMessages();
    window.sessionStorage.removeItem("sentinel-research-chat");
  }

  chatHistory() {
    return this.chatMessages
      .filter(
        (entry) =>
          ["user", "assistant"].includes(entry.role) &&
          typeof entry.content === "string" &&
          !entry.pending,
      )
      .map((entry) => ({
        role: entry.role,
        content: entry.contextContent || entry.content,
      }));
  }

  updateStreamingAssistant(id, update) {
    const transcript = this.querySelector("[data-research-chat-transcript]");
    const follow =
      !transcript ||
      transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight <
        48;
    this.chatMessages = this.chatMessages.map((entry) =>
      entry.id === id ? update(entry) : entry,
    );
    this.persistChatMessages();
    if (follow) this.scrollChatToEnd();
  }

  handleChatEvent(id, event) {
    if (event.type === "error") throw new Error(event.error || "Chat failed");
    this.updateStreamingAssistant(id, (entry) => {
      if (event.type === "content_delta") {
        const segments = [...(entry.segments ?? [])];
        const index = segments.findIndex(
          (segment) => segment.turnId === event.turn_id,
        );
        if (index === -1) {
          segments.push({ turnId: event.turn_id, content: event.delta });
        } else {
          segments[index] = {
            ...segments[index],
            content: segments[index].content + event.delta,
          };
        }
        return {
          ...entry,
          segments,
          content: segments.map((segment) => segment.content).join(""),
        };
      }
      if (event.type === "reasoning_delta") {
        const reasoning = [...(entry.reasoning ?? [])];
        const index = reasoning.findIndex(
          (item) => item.turnId === event.turn_id,
        );
        if (index === -1) {
          reasoning.push({ turnId: event.turn_id, content: event.delta });
        } else {
          reasoning[index] = {
            ...reasoning[index],
            content: reasoning[index].content + event.delta,
          };
        }
        return { ...entry, reasoning };
      }
      if (event.type === "turn_reset") {
        const segments = (entry.segments ?? []).filter(
          (segment) => segment.turnId !== event.turn_id,
        );
        return {
          ...entry,
          segments,
          content: segments.map((segment) => segment.content).join(""),
          reasoning: (entry.reasoning ?? []).filter(
            (item) => item.turnId !== event.turn_id,
          ),
        };
      }
      if (event.type === "tool_start") {
        return {
          ...entry,
          tools: [
            ...(entry.tools ?? []),
            {
              id: event.id,
              name: event.name,
              arguments: event.arguments,
              result: "",
              status: "running",
            },
          ],
        };
      }
      if (event.type === "tool_result") {
        return {
          ...entry,
          tools: (entry.tools ?? []).map((tool) =>
            tool.id === event.id
              ? { ...tool, result: event.result, status: "complete" }
              : tool,
          ),
        };
      }
      if (event.type === "context") {
        return { ...entry, context: event };
      }
      if (event.type === "done") {
        return {
          ...entry,
          content: entry.content || event.output || "",
          contextContent: event.output || entry.content || "",
          pending: false,
        };
      }
      return entry;
    });
  }

  async sendChatMessage() {
    const message = this.chatDraft.trim();
    if (!message || this.chatBusy) return;
    const history = this.chatHistory();
    const assistantId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}`;
    this.chatMessages = [
      ...this.chatMessages,
      { role: "user", content: message },
      {
        id: assistantId,
        role: "assistant",
        content: "",
        contextContent: "",
        segments: [],
        reasoning: [],
        tools: [],
        pending: true,
      },
    ];
    this.chatDraft = "";
    this.chatBusy = true;
    this.chatError = "";
    this.persistChatMessages();
    await this.scrollChatToEnd();

    try {
      await postEventStream("/api/ai/chat", { message, history }, (event) =>
        this.handleChatEvent(assistantId, event),
      );
    } catch (error) {
      this.chatError = error.message;
      this.updateStreamingAssistant(assistantId, (entry) => ({
        ...entry,
        pending: false,
      }));
    } finally {
      this.chatBusy = false;
      await this.scrollChatToEnd();
      this.querySelector("[data-research-chat-input]")?.focus();
    }
  }

  async scrollChatToEnd() {
    await this.updateComplete;
    const transcript = this.querySelector("[data-research-chat-transcript]");
    if (transcript) transcript.scrollTop = transcript.scrollHeight;
  }

  handleChatKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      this.sendChatMessage();
    }
  }

  formatToolArguments(value) {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value;
    }
  }

  changeUnitsFilter(name, value) {
    this[name] = value;
    this.units.refresh();
  }

  async changeTab(event) {
    const control = event.currentTarget;
    const nextTab = control.value;

    if (this.tab === "tasks" && nextTab !== "tasks") {
      const tasks = this.querySelector("sentinel-tasks");
      if (tasks?.dirty && !(await tasks.confirmClose())) {
        control.value = "tasks";
        return;
      }
    }

    this.tab = nextTab;
  }

  async refreshAll() {
    await Promise.all([
      this.status.refresh(),
      this.units.refresh(),
      this.allUnits.refresh(),
      this.history.refresh(),
    ]);
  }

  async requestResearch(kind, unitKind, unitKey) {
    this.busy = true;
    this.notice = "";
    this.actionError = "";

    try {
      await postJson("/api/ai/requests", {
        kind,
        unit_kind: unitKind,
        unit_key: unitKey,
      });
      this.notice = `${kind === "rate" ? "Rating" : "Analysis"} queued for ${unitKey}`;
      await this.refreshAll();
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.busy = false;
    }
  }

  async openArtifacts(unit) {
    this.artifactUnit = unit;
    this.activeArtifact = unit.artifacts?.[0] ?? "";
    this.artifactContent = "";
    this.artifactError = "";

    if (this.activeArtifact) {
      await this.loadArtifact();
    }
  }

  closeArtifacts() {
    this.artifactUnit = undefined;
    this.activeArtifact = "";
    this.artifactContent = "";
  }

  async changeArtifact(name) {
    this.activeArtifact = name;
    await this.loadArtifact();
  }

  async loadArtifact() {
    const unit = this.artifactUnit;
    const name = this.activeArtifact;

    if (!unit || !name) return;
    this.artifactLoading = true;
    this.artifactError = "";

    try {
      const data = await getJson(
        `/api/ai/artifacts/${encodeURIComponent(unit.kind)}/${encodeURIComponent(unit.key)}/${encodeURIComponent(name)}`,
      );
      let content = data.content ?? "";

      if (name.endsWith(".json")) {
        try {
          content = JSON.stringify(JSON.parse(content), null, 2);
        } catch {
          // Preserve malformed historical JSON as plain text.
        }
      }

      this.artifactContent = content;
    } catch (error) {
      this.artifactError = error.message;
    } finally {
      this.artifactLoading = false;
    }
  }

  renderStatus() {
    const status = this.status.value;
    const security = status.staleness?.security ?? { stale: 0, total: 0 };
    const units = this.allUnits.value?.units ?? [];
    const securities = units.filter((unit) => unit.kind === "security");

    return html`
      <div>
        Securities ${security.stale}/${security.total} stale · Queued
        ${status.queued?.length ?? 0} · Memory ${status.memory?.findings ?? "-"}
        findings
      </div>
      <div aria-hidden="true">&nbsp;</div>
      <wa-card
        ><span slot="header">Current Work</span>
        ${status.running
          ? html`
              <div>${status.running.label}</div>
              <div>${status.running.kind}:${status.running.key}</div>
              ${status.running.elapsed_seconds !== undefined
                ? html`<div>
                    ${formatDuration(status.running.elapsed_seconds * 1000)}
                  </div>`
                : ""}
            `
          : "Idle"}
      </wa-card>
      <div aria-hidden="true">&nbsp;</div>
      <div class="sentinel-layout" data-align="start" data-wrap>
        <wa-card style="flex: 1 1 40ch; min-width: 0"
          ><span slot="header">Next in Line</span>
          ${status.queued?.length
            ? status.queued.map(
                (item) => html`
                  <div>
                    ${item.unit_label ?? `${item.unit_kind}:${item.unit_key}`} ·
                    ${item.task_name ?? item.task_id ?? item.kind}
                  </div>
                `,
              )
            : "Queue empty"}
        </wa-card>
        <wa-card style="flex: 1 1 40ch; min-width: 0"
          ><span slot="header">Latest Tick</span>
          ${status.last_run
            ? html`
                <div>
                  <span data-tone=${statusVariant(status.last_run.status) || ""}
                    >${status.last_run.status}</span
                  >
                  · ${formatRelativeTime(status.last_run.finished_at)}
                </div>
                ${status.last_run.unit_label
                  ? html`<div>
                      ${status.last_run.unit_label}
                      ${status.last_run.unit_key
                        ? `(${status.last_run.unit_key})`
                        : ""}
                    </div>`
                  : ""}
                ${status.last_run.duration_seconds !== undefined
                  ? html`<div>
                      ${formatDuration(status.last_run.duration_seconds * 1000)}
                    </div>`
                  : ""}
                ${status.last_run.error
                  ? html`<span data-tone="error"
                      >${status.last_run.error}</span
                    >`
                  : ""}
              `
            : "No runs yet"}
        </wa-card>
      </div>
      ${status.staleness?.most_stale
        ? html`<div>
            Oldest: ${status.staleness.most_stale.label}
            (${status.staleness.most_stale.kind})
          </div>`
        : ""}
      ${status.memory?.error
        ? html`<span data-tone="error">Memory: ${status.memory.error}</span>`
        : ""}
      <div aria-hidden="true">&nbsp;</div>
      <wa-card
        ><span slot="header">Manual Rating</span>
        <div class="sentinel-layout" data-align="baseline" data-wrap>
          <label
            >Security&nbsp;<wa-select
              size="small"
              .value=${this.ratingSymbol}
              @change=${(event) =>
                (this.ratingSymbol = event.currentTarget.value)}
            >
              <wa-option value="">Select a security</wa-option>
              ${securities.map(
                (unit) =>
                  html`<wa-option value=${unit.key}>
                    ${unit.label} (${unit.key})
                  </wa-option>`,
              )}
            </wa-select></label
          >
          <span aria-hidden="true">&nbsp;</span>
          <wa-button
            size="small"
            ?disabled=${!this.ratingSymbol || this.busy}
            @click=${() =>
              this.requestResearch("rate", "security", this.ratingSymbol)}
            >Rate now</wa-button
          >
        </div>
      </wa-card>
    `;
  }

  renderUnits() {
    const units = this.units.value?.units ?? [];

    return html`
      <div class="sentinel-layout" data-align="baseline" data-wrap>
        <label
          >Kind&nbsp;<wa-select
            size="small"
            .value=${this.kind}
            @change=${(event) =>
              this.changeUnitsFilter("kind", event.currentTarget.value)}
          >
            <wa-option value="">All units</wa-option>
            <wa-option value="security">Securities</wa-option>
            <wa-option value="portfolio">Portfolio</wa-option>
          </wa-select></label
        >

        <wa-switch
          size="small"
          .checked=${this.staleOnly}
          @change=${(event) =>
            this.changeUnitsFilter("staleOnly", event.currentTarget.checked)}
          >Stale only</wa-switch
        >

        <wa-button size="small" @click=${this.refreshAll}>Refresh</wa-button>
      </div>
      <div aria-hidden="true">&nbsp;</div>
      ${this.units.loading && !this.units.value
        ? "Loading units…"
        : units.length === 0
          ? "No research units match this view."
          : html`
              <div style="overflow: auto; min-width: 0">
                <table style="border-collapse: collapse; width: 100%">
                  <thead>
                    <tr>
                      <th style="text-align: left">Unit</th>
                      <th style="text-align: left">Kind</th>
                      <th style="text-align: left">Last analyzed</th>
                      <th style="text-align: left">State</th>
                      <th style="text-align: left">Error</th>
                      <th style="text-align: left">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${units.map((unit) => {
                      const state =
                        unit.status === "running"
                          ? "running"
                          : unit.stale
                            ? "stale"
                            : "fresh";

                      return html`
                        <tr>
                          <td style="text-align: left; vertical-align: top">
                            ${unit.label}<br />${unit.key}
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            ${unit.kind}
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            ${unit.last_analyzed_at
                              ? formatRelativeTime(unit.last_analyzed_at)
                              : "Never"}
                          </td>
                          <td style="text-align: left; vertical-align: top">
                            <span data-tone=${statusVariant(state) || ""}
                              >${state}</span
                            >
                          </td>
                          <td
                            style="text-align: left; vertical-align: top; max-width: 40ch; overflow-wrap: anywhere"
                          >
                            ${unit.last_error ?? "-"}
                          </td>
                          <td
                            style="text-align: left; vertical-align: top; white-space: nowrap"
                          >
                            ${unit.kind !== "portfolio"
                              ? html`<wa-button
                                  size="small"
                                  ?disabled=${this.busy ||
                                  unit.status === "running"}
                                  @click=${() =>
                                    this.requestResearch(
                                      "analyze",
                                      unit.kind,
                                      unit.key,
                                    )}
                                  >Analyze</wa-button
                                >`
                              : ""}
                            <wa-button
                              size="small"
                              ?disabled=${!unit.artifacts?.length}
                              @click=${() => this.openArtifacts(unit)}
                              >View</wa-button
                            >
                          </td>
                        </tr>
                      `;
                    })}
                  </tbody>
                </table>
              </div>
            `}
    `;
  }

  renderHistory() {
    const history = this.history.value?.history ?? [];

    if (this.history.loading && !this.history.value) {
      return html`<div>Loading pipeline history…</div>`;
    }

    if (history.length === 0) {
      return html`<div>No pipeline runs yet.</div>`;
    }

    return html`
      <div style="overflow: auto; min-width: 0">
        <table style="border-collapse: collapse; width: 100%">
          <thead>
            <tr>
              <th style="text-align: left">Unit</th>
              <th style="text-align: left">Status</th>
              <th style="text-align: left">Duration</th>
              <th style="text-align: left">Finished</th>
              <th style="text-align: left">Error</th>
            </tr>
          </thead>
          <tbody>
            ${history.map(
              (entry) => html`
                <tr>
                  <td style="text-align: left; vertical-align: top">
                    ${entry.unit_label ??
                    entry.unit_key ??
                    entry.job_id?.replace("ai:tick:", "") ??
                    "-"}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    <span data-tone=${statusVariant(entry.status) || ""}
                      >${entry.status}</span
                    >
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatDuration(entry.duration_ms)}
                  </td>
                  <td style="text-align: left; vertical-align: top">
                    ${formatRelativeTime(
                      typeof entry.executed_at === "number"
                        ? entry.executed_at * 1000
                        : entry.executed_at,
                    )}
                  </td>
                  <td
                    style="text-align: left; vertical-align: top; overflow-wrap: anywhere"
                  >
                    ${entry.error ?? "-"}
                  </td>
                </tr>
              `,
            )}
          </tbody>
        </table>
      </div>
    `;
  }

  renderChat() {
    return html`
      <section
        data-research-chat-transcript
        aria-label="Research chat transcript"
        aria-live="polite"
        style="height: min(52vh, 36rem); overflow-y: auto; padding-right: 1ch"
      >
        ${this.chatMessages.length
          ? this.chatMessages.map(
              (message) => html`
                <article style="margin-bottom: 1.25rem">
                  <div>
                    <span
                      >${message.role === "assistant"
                        ? "Sentinel"
                        : "You"}</span
                    >
                  </div>
                  <div
                    style="white-space: pre-wrap; overflow-wrap: anywhere; max-width: 78ch"
                  >
                    ${message.content}
                  </div>
                  ${message.role === "assistant"
                    ? html`
                        ${(message.reasoning ?? []).map(
                          (item, index) => html`
                            <wa-details
                              style="margin-top: 0.45rem; max-width: 78ch"
                            >
                              <span slot="summary">
                                Reasoning${message.reasoning.length > 1
                                  ? ` ${index + 1}`
                                  : ""}
                              </span>
                              <div
                                style="white-space: pre-wrap; overflow-wrap: anywhere; padding: 0.4rem 0 0 2ch"
                              >
                                ${item.content}
                              </div>
                            </wa-details>
                          `,
                        )}
                        ${(message.tools ?? []).map(
                          (tool) => html`
                            <wa-details
                              style="margin-top: 0.45rem; max-width: 78ch"
                            >
                              <span slot="summary">
                                Tool · ${tool.name} ·
                                ${tool.status === "complete"
                                  ? "complete"
                                  : "running"}
                              </span>
                              <div style="padding: 0.4rem 0 0 2ch">
                                <div>Arguments</div>
                                <pre
                                  style="white-space: pre-wrap; overflow-wrap: anywhere; margin: 0.25rem 0 0.75rem"
                                >
${this.formatToolArguments(tool.arguments)}</pre
                                >
                                <div>Result</div>
                                <pre
                                  style="white-space: pre-wrap; overflow-wrap: anywhere; margin: 0.25rem 0 0"
                                >
${tool.result || "Waiting…"}</pre
                                >
                              </div>
                            </wa-details>
                          `,
                        )}
                        ${message.context?.dropped_messages > 0
                          ? html`
                              <wa-details
                                style="margin-top: 0.45rem; max-width: 78ch"
                              >
                                <span slot="summary">
                                  Context · ${message.context.dropped_messages}
                                  older messages omitted
                                </span>
                                <div style="padding: 0.4rem 0 0 2ch">
                                  The newest
                                  ${message.context.retained_messages} messages
                                  were retained inside the
                                  ${Math.round(
                                    message.context.limit_tokens / 1024,
                                  )}k-token
                                  context window.
                                </div>
                              </wa-details>
                            `
                          : ""}
                      `
                    : ""}
                </article>
              `,
            )
          : html`<div style="max-width: 68ch">
              Ask about the research pipeline, inspect any generated artifact,
              search the web, browse with Firefox, or operate Sentinel directly.
            </div>`}
        ${this.chatBusy ? html`<div>Streaming…</div>` : ""}
      </section>
      <wa-divider></wa-divider>
      <label for="research-chat-input">Message</label>
      <wa-textarea
        size="small"
        id="research-chat-input"
        data-research-chat-input
        aria-label="Message research chat"
        style="inline-size: 100%"
        rows="4"
        placeholder="Ask Sentinel…"
        .value=${this.chatDraft}
        ?disabled=${this.chatBusy}
        @input=${(event) => (this.chatDraft = event.currentTarget.value)}
        @keydown=${this.handleChatKeydown}
      ></wa-textarea>
      <div
        class="sentinel-layout"
        data-align="baseline"
        data-justify="between"
        data-wrap
      >
        <span>Enter sends · Shift+Enter adds a line</span>
        <span>
          <wa-button
            size="small"
            ?disabled=${this.chatMessages.length === 0 || this.chatBusy}
            @click=${this.clearChat}
            >Clear</wa-button
          >
          <wa-button
            size="small"
            ?disabled=${!this.chatDraft.trim() || this.chatBusy}
            @click=${this.sendChatMessage}
            >Send</wa-button
          >
        </span>
      </div>
      ${this.chatError
        ? html`<span data-tone="error">${this.chatError}</span>`
        : ""}
    `;
  }

  renderArtifactModal() {
    const unit = this.artifactUnit;

    if (!unit) return "";
    return html`
      <wa-dialog
        label="${unit.label} / artifacts"
        open
        @wa-after-hide=${(event) => {
          if (event.target === event.currentTarget) this.closeArtifacts();
        }}
      >
        ${unit.artifacts?.length
          ? html`
              <label
                >Artifact&nbsp;<wa-select
                  size="small"
                  .value=${this.activeArtifact}
                  @change=${(event) =>
                    this.changeArtifact(event.currentTarget.value)}
                >
                  ${unit.artifacts.map(
                    (name) =>
                      html`<wa-option value=${name}>${name}</wa-option>`,
                  )}
                </wa-select></label
              >
              <div aria-hidden="true">&nbsp;</div>
              ${this.artifactLoading
                ? "Loading artifact…"
                : this.artifactError
                  ? html`<span data-tone="error">${this.artifactError}</span>`
                  : html`<pre
                      style="white-space: pre-wrap; overflow-wrap: anywhere"
                    >
${this.artifactContent}</pre
                    >`}
            `
          : "No artifacts have been written for this unit."}
      </wa-dialog>
    `;
  }

  render() {
    const error =
      this.status.error ??
      this.units.error ??
      this.allUnits.error ??
      this.history.error;
    const loading =
      (!this.status.value && this.status.loading) ||
      (!this.allUnits.value && this.allUnits.loading);

    const enabled = this.status.value?.enabled;
    const pipelineState = loading
      ? html`<span>loading</span>`
      : error && !this.status.value
        ? html`<span data-tone="error">unavailable</span>`
        : html`<span data-tone=${enabled ? "success" : ""}
            >${enabled ? "enabled" : "paused"}</span
          >`;

    let content;
    if (this.tab === "tasks") {
      content = html`<sentinel-tasks></sentinel-tasks>`;
    } else if (this.tab === "chat") {
      content = this.renderChat();
    } else if (loading) {
      content = html`<div>Loading research pipeline…</div>`;
    } else if (error && !this.status.value) {
      content = html`<span data-tone="error">${error.message}</span>`;
    } else if (this.tab === "units") {
      content = this.renderUnits();
    } else if (this.tab === "history") {
      content = this.renderHistory();
    } else {
      content = this.renderStatus();
    }

    return html`
      <div>Pipeline ${pipelineState}</div>
      <wa-radio-group
        size="small"
        aria-label="Research pipeline view"
        .value=${this.tab}
        @change=${this.changeTab}
      >
        <wa-radio appearance="button" value="status">Status</wa-radio>
        <wa-radio appearance="button" value="units">Units</wa-radio>
        <wa-radio appearance="button" value="history">History</wa-radio>
        <wa-radio appearance="button" value="chat">Chat</wa-radio>
        <wa-radio appearance="button" value="tasks">Tasks</wa-radio>
      </wa-radio-group>
      <div aria-hidden="true">&nbsp;</div>
      ${content}
      ${this.tab !== "tasks" && this.notice
        ? html`<div aria-live="polite">${this.notice}</div>`
        : ""}
      ${this.tab !== "tasks" && this.actionError
        ? html`<span data-tone="error">${this.actionError}</span>`
        : ""}
      ${this.renderArtifactModal()}
    `;
  }
}

customElements.define("sentinel-research", SentinelResearch);
