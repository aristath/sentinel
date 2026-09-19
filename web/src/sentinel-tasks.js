import { LitElement, html } from "lit";
import { deleteJson, getJson, postJson, putJson } from "./api.js";
import { formatDateTime, statusVariant } from "./modal-utils.js";
import "./sentinel-code-editor.js";

const editorColorSchemeKey = "sentinel.codeEditorColorScheme";
const editorColorSchemes = new Set([
  "monochrome",
  "latte",
  "frappe",
  "macchiato",
  "mocha",
]);
const defaultCron = "0 9 * * *";
const defaultIntervalSeconds = 12 * 60 * 60;
const cronFields = [
  {
    label: "Minute",
    options: [
      ["*", "every minute"],
      ...[0, 5, 10, 15, 20, 30, 45].map((value) => [
        String(value),
        `:${String(value).padStart(2, "0")}`,
      ]),
    ],
  },
  {
    label: "Hour",
    options: [
      ["*", "every hour"],
      ...Array.from({ length: 24 }, (_, value) => [
        String(value),
        value === 0
          ? "midnight"
          : value === 12
            ? "noon"
            : `${value > 12 ? value - 12 : value} ${value < 12 ? "AM" : "PM"}`,
      ]),
    ],
  },
  {
    label: "Day",
    options: [
      ["*", "every day"],
      ...Array.from({ length: 31 }, (_, index) => [
        String(index + 1),
        String(index + 1),
      ]),
    ],
  },
  {
    label: "Month",
    options: [
      ["*", "every month"],
      ...[
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
      ].map((label, index) => [String(index + 1), label]),
    ],
  },
  {
    label: "Weekday",
    options: [
      ["*", "every day"],
      ...[
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
      ].map((label, index) => [String(index), label]),
    ],
  },
].map((field, index) => ({ ...field, index }));

function parseMetadata(content) {
  let raw = {};

  try {
    raw = JSON.parse(content);
  } catch {
    // The Files view remains available to repair malformed task.json files.
  }

  return {
    name: typeof raw.name === "string" ? raw.name : "",
    enabled: raw.enabled === true,
    description: typeof raw.description === "string" ? raw.description : "",
    tags: Array.isArray(raw.tags)
      ? raw.tags.filter((tag) => typeof tag === "string")
      : [],
    cwd: typeof raw.cwd === "string" ? raw.cwd : "",
    timeout: typeof raw.timeout === "number" ? raw.timeout : "",
    schedule:
      typeof raw.schedule === "string" && raw.schedule.trim()
        ? raw.schedule
        : null,
    schedulePolicy:
      raw.schedulePolicy && typeof raw.schedulePolicy === "object"
        ? raw.schedulePolicy
        : null,
  };
}

class SentinelTasks extends LitElement {
  static properties = {
    tasks: { state: true },
    selectedId: { state: true },
    task: { state: true },
    files: { state: true },
    activeFile: { state: true },
    drafts: { state: true },
    baselines: { state: true },
    metadata: { state: true },
    metadataBaseline: { state: true },
    tab: { state: true },
    runInputs: { state: true },
    runs: { state: true },
    runId: { state: true },
    run: { state: true },
    loading: { state: true },
    busyAction: { state: true },
    notice: { state: true },
    actionError: { state: true },
    editorColorScheme: { state: true },
  };

  constructor() {
    super();
    this.tasks = [];
    this.selectedId = undefined;
    this.task = undefined;
    this.files = [];
    this.activeFile = undefined;
    this.drafts = {};
    this.baselines = {};
    this.metadata = undefined;
    this.metadataBaseline = "";
    this.tab = "files";
    this.runInputs = "{}";
    this.runs = [];
    this.runId = undefined;
    this.run = undefined;
    this.loading = true;
    this.busyAction = "";
    this.notice = "";
    this.actionError = "";
    const storedEditorColorScheme = globalThis.localStorage?.getItem(
      editorColorSchemeKey,
    );
    this.editorColorScheme = editorColorSchemes.has(storedEditorColorScheme)
      ? storedEditorColorScheme
      : "monochrome";
  }

  createRenderRoot() {
    return this;
  }

  connectedCallback() {
    super.connectedCallback();
    this.loadTasks();
    this.tasksTimer = setInterval(() => this.loadTasks(true), 20_000);
    this.runsTimer = setInterval(() => this.pollRuns(), 2000);
  }

  disconnectedCallback() {
    clearInterval(this.tasksTimer);
    clearInterval(this.runsTimer);
    super.disconnectedCallback();
  }

  get filesDirty() {
    return this.files.some(
      (file) =>
        file.name in this.baselines &&
        this.drafts[file.name] !== this.baselines[file.name],
    );
  }

  get metadataDirty() {
    return (
      this.metadata !== undefined &&
      JSON.stringify(this.metadata) !== this.metadataBaseline
    );
  }

  get dirty() {
    return this.filesDirty || this.metadataDirty;
  }

  get running() {
    return ["queued", "running"].includes(this.run?.status);
  }

  confirmClose() {
    if (!this.dirty) return true;
    return window.confirm(
      `Discard unsaved changes to "${this.task?.name || this.selectedId}"?`,
    );
  }

  async loadTasks(background = false) {
    if (!background) this.loading = true;

    try {
      const tasks = await getJson("/api/tasks");
      this.tasks = tasks;

      if (
        !this.selectedId ||
        !tasks.some((task) => task.id === this.selectedId)
      ) {
        if (tasks[0]) await this.selectTask(tasks[0].id, { force: true });
      }
    } catch (error) {
      this.actionError = error.message;
    } finally {
      if (!background) this.loading = false;
    }
  }

  async selectTask(id, { force = false } = {}) {
    if (id === this.selectedId && this.task) return;
    if (!force && !this.confirmClose()) return;

    this.selectedId = id;
    this.task = undefined;
    this.files = [];
    this.activeFile = undefined;
    this.drafts = {};
    this.baselines = {};
    this.metadata = undefined;
    this.metadataBaseline = "";
    this.runs = [];
    this.runId = undefined;
    this.run = undefined;
    this.runInputs = "{}";
    this.notice = "";
    this.actionError = "";
    this.loading = true;

    try {
      const [task, files, runs, metadataFile] = await Promise.all([
        getJson(`/api/tasks/${encodeURIComponent(id)}`),
        getJson(`/api/tasks/${encodeURIComponent(id)}/files`),
        getJson(`/api/tasks/${encodeURIComponent(id)}/runs?limit=50`),
        getJson(
          `/api/tasks/${encodeURIComponent(id)}/files/${encodeURIComponent("task.json")}`,
        ),
      ]);

      if (this.selectedId !== id) return;
      this.task = task;
      this.files = files;
      this.runs = runs;
      this.metadata = parseMetadata(metadataFile.content);
      this.metadataBaseline = JSON.stringify(this.metadata);
      const activeFile =
        files.find((file) => file.name === "task.js")?.name ?? files[0]?.name;
      if (activeFile) await this.selectFile(activeFile);
      const activeRun = runs.find((item) =>
        ["queued", "running"].includes(item.status),
      );
      this.runId = activeRun?.id ?? runs[0]?.id;
      if (this.runId) await this.loadRun(this.runId);
    } catch (error) {
      this.actionError = error.message;
    } finally {
      if (this.selectedId === id) this.loading = false;
    }
  }

  async selectFile(name) {
    this.activeFile = name;

    if (name in this.drafts) return;

    try {
      const file = await getJson(
        `/api/tasks/${encodeURIComponent(this.selectedId)}/files/${encodeURIComponent(name)}`,
      );
      this.drafts = { ...this.drafts, [name]: file.content };
      this.baselines = { ...this.baselines, [name]: file.content };
    } catch (error) {
      this.actionError = error.message;
    }
  }

  async pollRuns() {
    if (!this.selectedId) return;
    const selectedId = this.selectedId;

    try {
      const runs = await getJson(
        `/api/tasks/${encodeURIComponent(selectedId)}/runs?limit=50`,
      );
      if (this.selectedId !== selectedId) return;
      this.runs = runs;
      const active = runs.find((item) =>
        ["queued", "running"].includes(item.status),
      );

      if (active) this.runId = active.id;
      else if (this.runId && !runs.some((item) => item.id === this.runId)) {
        this.runId = runs[0]?.id;
      }

      if (this.runId) await this.loadRun(this.runId);
    } catch (error) {
      this.actionError = error.message;
    }
  }

  async loadRun(id) {
    this.runId = id;

    try {
      this.run = await getJson(`/api/task-runs/${encodeURIComponent(id)}`);
    } catch (error) {
      this.actionError = error.message;
    }
  }

  async createTask() {
    this.busyAction = "new";
    this.actionError = "";

    try {
      const task = await postJson("/api/tasks", { name: "New Task" });
      await this.loadTasks(true);
      await this.selectTask(task.id, { force: true });
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  async deleteTask() {
    if (!this.task || !window.confirm(`Delete task "${this.task.name}"?`)) {
      return;
    }

    this.busyAction = "delete-task";

    try {
      await deleteJson(`/api/tasks/${encodeURIComponent(this.task.id)}`);
      this.selectedId = undefined;
      this.task = undefined;
      this.notice = "Deleted";
      await this.loadTasks();
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  async validateTask() {
    this.busyAction = "validate";
    this.notice = "";
    this.actionError = "";

    try {
      const result = await getJson(
        `/api/tasks/${encodeURIComponent(this.selectedId)}/validate`,
      );
      this.notice = result.ok
        ? "Validation passed"
        : (result.errors ?? []).join("\n");
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  async startRun() {
    let inputs;

    try {
      inputs = JSON.parse(this.runInputs);
      if (!inputs || Array.isArray(inputs) || typeof inputs !== "object") {
        throw new Error("Inputs must be a JSON object");
      }
    } catch (error) {
      this.actionError = `Invalid inputs: ${error.message}`;
      return;
    }

    this.busyAction = "run";
    this.notice = "";
    this.actionError = "";

    try {
      const run = await postJson(
        `/api/tasks/${encodeURIComponent(this.selectedId)}/run`,
        { inputs },
      );
      this.runId = run.id;
      this.run = run;
      await this.pollRuns();
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  async stopRun() {
    if (!this.runId) return;
    this.busyAction = "stop";

    try {
      await deleteJson(`/api/task-runs/${encodeURIComponent(this.runId)}`);
      await this.pollRuns();
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  updateDraft(content) {
    this.drafts = { ...this.drafts, [this.activeFile]: content };
  }

  async saveFile() {
    if (!this.activeFile) return;
    this.busyAction = "save-file";

    try {
      const content = this.drafts[this.activeFile] ?? "";
      await putJson(
        `/api/tasks/${encodeURIComponent(this.selectedId)}/files/${encodeURIComponent(this.activeFile)}`,
        { content },
      );
      this.baselines = { ...this.baselines, [this.activeFile]: content };
      this.notice = "Saved";
      if (this.activeFile === "task.json") await this.loadTasks(true);
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  setEditorColorScheme(value) {
    this.editorColorScheme = editorColorSchemes.has(value)
      ? value
      : "monochrome";
    globalThis.localStorage?.setItem(
      editorColorSchemeKey,
      this.editorColorScheme,
    );
  }

  async createFile() {
    const name = window
      .prompt("New file name (e.g. step.sh, prompt.md)")
      ?.trim();
    if (!name) return;

    try {
      await postJson(
        `/api/tasks/${encodeURIComponent(this.selectedId)}/files`,
        {
          name,
          content: "",
        },
      );
      this.files = await getJson(
        `/api/tasks/${encodeURIComponent(this.selectedId)}/files`,
      );
      this.drafts = { ...this.drafts, [name]: "" };
      this.baselines = { ...this.baselines, [name]: "" };
      this.activeFile = name;
      this.notice = "Created";
    } catch (error) {
      this.actionError = error.message;
    }
  }

  async deleteFile(file) {
    if (!window.confirm(`Delete "${file.name}"? This cannot be undone.`))
      return;

    try {
      await deleteJson(
        `/api/tasks/${encodeURIComponent(this.selectedId)}/files/${encodeURIComponent(file.name)}`,
      );
      const drafts = { ...this.drafts };
      const baselines = { ...this.baselines };
      delete drafts[file.name];
      delete baselines[file.name];
      this.drafts = drafts;
      this.baselines = baselines;
      this.files = this.files.filter(
        (candidate) => candidate.name !== file.name,
      );
      if (this.activeFile === file.name) {
        this.activeFile = undefined;
        if (this.files[0]) await this.selectFile(this.files[0].name);
      }
      this.notice = "Deleted";
    } catch (error) {
      this.actionError = error.message;
    }
  }

  patchMetadata(values) {
    this.metadata = { ...this.metadata, ...values };
  }

  get scheduleMode() {
    if (this.metadata?.schedule) return "cron";
    if ((this.metadata?.schedulePolicy?.staleAfterSeconds ?? 0) > 0) {
      return "interval";
    }
    return "off";
  }

  setScheduleMode(mode) {
    if (mode === "cron") {
      this.patchMetadata({
        schedule: this.metadata.schedule || defaultCron,
        schedulePolicy: null,
      });
    } else if (mode === "interval") {
      this.patchMetadata({
        schedule: null,
        schedulePolicy: {
          ...(this.metadata.schedulePolicy ?? {}),
          staleAfterSeconds:
            this.metadata.schedulePolicy?.staleAfterSeconds ??
            defaultIntervalSeconds,
          runWhen: this.metadata.schedulePolicy?.runWhen ?? "idle",
        },
      });
    } else {
      this.patchMetadata({ schedule: null, schedulePolicy: null });
    }
  }

  intervalParts() {
    const seconds =
      this.metadata?.schedulePolicy?.staleAfterSeconds ??
      defaultIntervalSeconds;
    return {
      days: Math.floor(seconds / 86_400),
      hours: Math.floor((seconds % 86_400) / 3600),
      minutes: Math.floor((seconds % 3600) / 60),
    };
  }

  patchInterval(part, value) {
    const parts = {
      ...this.intervalParts(),
      [part]: Math.max(0, Number(value)),
    };
    const staleAfterSeconds = Math.max(
      1,
      Math.floor(parts.days * 86_400 + parts.hours * 3600 + parts.minutes * 60),
    );
    this.patchMetadata({
      schedulePolicy: {
        ...this.metadata.schedulePolicy,
        staleAfterSeconds,
        runWhen: this.metadata.schedulePolicy?.runWhen ?? "idle",
      },
    });
  }

  patchSchedulePolicy(values) {
    this.patchMetadata({
      schedulePolicy: { ...this.metadata.schedulePolicy, ...values },
    });
  }

  cronParts() {
    const schedule = this.metadata?.schedule?.trim() || defaultCron;
    const parts = schedule.split(/\s+/);
    return parts.length === 5 ? parts : defaultCron.split(" ");
  }

  cronValues(index) {
    const part = this.cronParts()[index];
    return new Set(part === "*" ? ["*"] : part.split(",").filter(Boolean));
  }

  toggleCronValue(index, value, checked) {
    const values = this.cronValues(index);

    if (value === "*") {
      values.clear();
      values.add("*");
    } else if (checked) {
      values.delete("*");
      values.add(value);
    } else {
      values.delete(value);
      if (values.size === 0) values.add("*");
    }

    const parts = this.cronParts();
    parts[index] = values.has("*")
      ? "*"
      : [...values]
          .sort((left, right) => Number(left) - Number(right))
          .join(",");
    this.patchMetadata({ schedule: parts.join(" "), schedulePolicy: null });
  }

  async saveMetadata() {
    this.busyAction = "save-metadata";

    try {
      const payload = {
        name: this.metadata.name.trim() || "Untitled task",
        enabled: this.metadata.enabled,
        description: this.metadata.description.trim() || null,
        tags: this.metadata.tags.length ? this.metadata.tags : null,
        cwd: this.metadata.cwd.trim() || null,
        timeout:
          Number(this.metadata.timeout) > 0
            ? Number(this.metadata.timeout)
            : null,
        schedule: this.metadata.schedule?.trim() || null,
        schedulePolicy: this.metadata.schedulePolicy || null,
      };
      const task = await putJson(
        `/api/tasks/${encodeURIComponent(this.selectedId)}/meta`,
        payload,
      );
      this.task = task;
      this.metadataBaseline = JSON.stringify(this.metadata);
      this.notice = "Saved";
      await this.loadTasks(true);
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  renderTaskList() {
    const groups = [
      ["Invalid", this.tasks.filter((task) => task.invalid)],
      ["Enabled", this.tasks.filter((task) => task.enabled && !task.invalid)],
      ["Disabled", this.tasks.filter((task) => !task.enabled && !task.invalid)],
    ].filter(([, tasks]) => tasks.length > 0);

    return html`
      <tui-box heading="Tasks" border="single">
        ${groups.map(
          ([label, tasks], index) => html`
            ${index > 0 ? html`<div aria-hidden="true">&nbsp;</div>` : ""}
            <div>${label}</div>
            ${tasks.map(
              (task) => html`
                <div>
                  <span aria-hidden="true"
                    >${task.id === this.selectedId ? "▶" : " "}&nbsp;</span
                  ><tui-button @click=${() => this.selectTask(task.id)}
                    >${task.name}</tui-button
                  >
                  <tui-text
                    variant=${
                      task.invalid ? "error" : task.enabled ? "success" : ""
                    }
                    >${task.invalid ? "invalid" : task.enabled ? "on" : "off"}</tui-text
                  >
                  <div>${task.id}</div>
                </div>
              `,
            )}
          `,
        )}
      </tui-box>
    `;
  }

  renderToolbar() {
    return html`
      <tui-flex align="baseline" justify="between" wrap>
        <span>
          ${this.task.name}
          ${this.dirty ? html`<tui-text variant="warning">unsaved</tui-text>` : ""}
          │ ${this.task.source} │ ${this.task.id}
        </span>
        <span>
          <tui-button
            ?disabled=${this.dirty || this.running || this.busyAction !== ""}
            @click=${this.validateTask}
            >Check</tui-button
          >
          ${
            this.running
              ? html`<tui-button variant="error" @click=${this.stopRun}
                  >Stop</tui-button
                >`
              : html`<tui-button
                  ?disabled=${
                    this.dirty || this.task.invalid || this.busyAction !== ""
                  }
                  @click=${this.startRun}
                  >Run</tui-button
                >`
          }
          <tui-button
            variant="error"
            ?disabled=${
              this.running ||
              this.task.source === "core" ||
              this.busyAction !== ""
            }
            @click=${this.deleteTask}
            >Delete</tui-button
          >
        </span>
      </tui-flex>
    `;
  }

  renderFiles() {
    const active = this.files.find((file) => file.name === this.activeFile);
    const draft = this.activeFile ? (this.drafts[this.activeFile] ?? "") : "";
    const dirty =
      this.activeFile &&
      this.activeFile in this.baselines &&
      draft !== this.baselines[this.activeFile];

    return html`
      <tui-flex align="start" wrap>
        <tui-box
          heading="Files"
          border="single"
          style="flex: 1 1 20ch; min-width: 0"
        >
          <div><tui-button @click=${this.createFile}>New File</tui-button></div>
          ${this.files.map(
            (file) => html`
              <div>
                <span aria-hidden="true"
                  >${file.name === this.activeFile ? "▶" : " "}&nbsp;</span
                ><tui-button @click=${() => this.selectFile(file.name)}
                  >${file.name}</tui-button
                >
                ${
                  this.drafts[file.name] !== this.baselines[file.name] &&
                  file.name in this.baselines
                    ? html`<tui-text variant="warning">unsaved</tui-text>`
                    : ""
                }
                ${file.protected ? "protected" : ""}
                ${
                  !file.protected
                    ? html`<tui-button
                        variant="error"
                        ?disabled=${this.running}
                        @click=${() => this.deleteFile(file)}
                        >Delete</tui-button
                      >`
                    : ""
                }
              </div>
            `,
          )}
        </tui-box>
        <section style="flex: 4 1 60ch; min-width: 0">
          <div>
            ${this.activeFile ?? "No file selected"}
            ${active?.protected ? "│ protected" : ""}
            ${dirty ? html`│ <tui-text variant="warning">unsaved</tui-text>` : ""}
            <label
              >Scheme&nbsp;<tui-select
                aria-label="Code editor color scheme"
                value=${this.editorColorScheme}
                @change=${(event) =>
                  this.setEditorColorScheme(event.currentTarget.value)}
              >
                <option value="monochrome">Monochrome</option>
                <option value="latte">Latte</option>
                <option value="frappe">Frappé</option>
                <option value="macchiato">Macchiato</option>
                <option value="mocha">Mocha</option>
              </tui-select></label
            >
            <tui-button
              ?disabled=${!dirty || this.running || this.busyAction !== ""}
              @click=${this.saveFile}
              >Save</tui-button
            >
          </div>
          <sentinel-code-editor
            aria-label="${this.activeFile ?? "Task file"} content"
            document-id="${this.selectedId ?? ""}/${this.activeFile ?? ""}"
            filename=${this.activeFile ?? "file.txt"}
            language=${active?.language ?? "plaintext"}
            color-scheme=${this.editorColorScheme}
            .value=${draft}
            ?disabled=${!this.activeFile || this.running}
            @input=${(event) => this.updateDraft(event.currentTarget.value)}
          ></sentinel-code-editor>
        </section>
      </tui-flex>
    `;
  }

  renderSchedule() {
    const parts = this.intervalParts();

    return html`
      <div>Schedule</div>
      <tui-radio-buttonset
        aria-label="Task schedule mode"
        value=${this.scheduleMode}
        ?disabled=${this.running}
        @change=${(event) => this.setScheduleMode(event.currentTarget.value)}
      >
        <tui-radio-button value="off">Off</tui-radio-button>
        <tui-radio-button value="cron">Cron</tui-radio-button>
        <tui-radio-button value="interval">Interval</tui-radio-button>
      </tui-radio-buttonset>
      ${
        this.scheduleMode === "cron"
          ? html`
              <div>
                <label
                  >Cron&nbsp;<tui-input
                    value=${this.metadata.schedule ?? defaultCron}
                    size="24"
                    ?disabled=${this.running}
                    @input=${(event) =>
                      this.patchMetadata({
                        schedule: event.currentTarget.value || defaultCron,
                      })}
                  ></tui-input
                ></label>
              </div>
              ${cronFields.map((field) => {
                const selected = this.cronValues(field.index);

                return html`
                  <div>${field.label}</div>
                  <tui-flex align="baseline" wrap>
                    ${field.options.map(
                      ([value, label]) => html`
                        <tui-toggle
                          ?checked=${selected.has(value)}
                          ?disabled=${this.running}
                          @change=${(event) =>
                            this.toggleCronValue(
                              field.index,
                              value,
                              event.currentTarget.checked,
                            )}
                          >${value} ${label}</tui-toggle
                        ><span aria-hidden="true">&nbsp;</span>
                      `,
                    )}
                  </tui-flex>
                `;
              })}
            `
          : ""
      }
      ${
        this.scheduleMode === "interval"
          ? html`
              <tui-flex align="baseline" wrap>
                <label
                  >Days&nbsp;<tui-input
                    type="number"
                    min="0"
                    value=${parts.days}
                    @change=${(event) =>
                      this.patchInterval("days", event.currentTarget.value)}
                  ></tui-input
                ></label>
                <span aria-hidden="true">&nbsp;│&nbsp;</span>
                <label
                  >Hours&nbsp;<tui-input
                    type="number"
                    min="0"
                    max="23"
                    value=${parts.hours}
                    @change=${(event) =>
                      this.patchInterval("hours", event.currentTarget.value)}
                  ></tui-input
                ></label>
                <span aria-hidden="true">&nbsp;│&nbsp;</span>
                <label
                  >Minutes&nbsp;<tui-input
                    type="number"
                    min="0"
                    max="59"
                    value=${parts.minutes}
                    @change=${(event) =>
                      this.patchInterval("minutes", event.currentTarget.value)}
                  ></tui-input
                ></label>
                <span aria-hidden="true">&nbsp;│&nbsp;</span>
                <label
                  >Run when&nbsp;<tui-select
                    value=${this.metadata.schedulePolicy?.runWhen ?? "idle"}
                    @change=${(event) =>
                      this.patchSchedulePolicy({
                        runWhen: event.currentTarget.value,
                      })}
                  >
                    <option value="idle">Idle</option>
                    <option value="immediate">Immediate</option>
                  </tui-select></label
                >
                <span aria-hidden="true">&nbsp;│&nbsp;</span>
                <label
                  >Priority&nbsp;<tui-input
                    type="number"
                    min="-1000"
                    max="1000"
                    value=${this.metadata.schedulePolicy?.priority ?? 0}
                    @change=${(event) =>
                      this.patchSchedulePolicy({
                        priority: Number(event.currentTarget.value),
                      })}
                  ></tui-input
                ></label>
              </tui-flex>
            `
          : ""
      }
    `;
  }

  renderMetadata() {
    if (!this.metadata) return html`<div>Loading metadata…</div>`;

    return html`
      <tui-flex align="baseline" justify="between" wrap>
        <span>Metadata</span>
        <tui-button
          ?disabled=${
            !this.metadataDirty || this.running || this.busyAction !== ""
          }
          @click=${this.saveMetadata}
          >Save</tui-button
        >
      </tui-flex>
      <div>
        <label
          ><span>Name</span>
          <tui-input
            block
            value=${this.metadata.name}
            @input=${(event) =>
              this.patchMetadata({ name: event.currentTarget.value })}
          ></tui-input
        ></label>
        <tui-toggle
          ?checked=${this.metadata.enabled}
          ?disabled=${this.running}
          @change=${(event) =>
            this.patchMetadata({ enabled: event.currentTarget.checked })}
          >Enabled</tui-toggle
        >
      </div>
      <div>
        <label>Description</label>
        <tui-textarea
          aria-label="Task description"
          block
          rows="4"
          value=${this.metadata.description}
          ?disabled=${this.running}
          @input=${(event) =>
            this.patchMetadata({ description: event.currentTarget.value })}
        ></tui-textarea>
      </div>
      <div>
        <label
          ><span>Tags</span>
          <tui-input
            block
            value=${this.metadata.tags.join(", ")}
            ?disabled=${this.running}
            @input=${(event) =>
              this.patchMetadata({
                tags: event.currentTarget.value
                  .split(",")
                  .map((tag) => tag.trim())
                  .filter(Boolean),
              })}
          ></tui-input
        ></label>
      </div>
      <div>
        <label
          >Timeout (seconds)&nbsp;<tui-input
            type="number"
            min="0"
            step="60"
            value=${this.metadata.timeout}
            ?disabled=${this.running}
            @change=${(event) =>
              this.patchMetadata({
                timeout: Number(event.currentTarget.value),
              })}
          ></tui-input
        ></label>
      </div>
      <div>
        <label
          ><span>Working directory</span>
          <tui-input
            block
            value=${this.metadata.cwd}
            placeholder="@/tasks/artifacts/{{task-id}}"
            ?disabled=${this.running}
            @input=${(event) =>
              this.patchMetadata({ cwd: event.currentTarget.value })}
          ></tui-input
        ></label>
      </div>
      <div aria-hidden="true">&nbsp;</div>
      ${this.renderSchedule()}
    `;
  }

  renderRun() {
    return html`
      <tui-box heading="Run" border="single">
        <div>
          Status
          <tui-text variant=${statusVariant(this.run?.status) || ""}
            >${this.run?.status ?? "idle"}</tui-text
          >
        </div>
        <div>History</div>
        ${
          this.runs.length
            ? this.runs.map(
                (run) => html`
                  <div>
                    <span aria-hidden="true"
                      >${run.id === this.runId ? "▶" : " "}&nbsp;</span
                    ><tui-button @click=${() => this.loadRun(run.id)}
                      >${run.status} -
                      ${
                        run.createdAt ? formatDateTime(run.createdAt) : run.id
                      }</tui-button
                    >
                  </div>
                `,
              )
            : "No runs"
        }
        <div>Inputs (JSON)</div>
        <tui-textarea
          aria-label="Task run inputs"
          block
          rows="4"
          value=${this.runInputs}
          ?disabled=${this.running}
          @input=${(event) => (this.runInputs = event.currentTarget.value)}
        ></tui-textarea>
        <div>Log</div>
        ${(this.run?.log ?? []).map(
          (line) => html`<div><code>${line}</code></div>`,
        )}
        ${
          this.run?.error
            ? html`<tui-text variant="error">${this.run.error}</tui-text>`
            : ""
        }
        <pre style="white-space: pre-wrap; overflow-wrap: anywhere">
${this.run?.liveOutput ?? " "}</pre>
      </tui-box>
    `;
  }

  renderWorkbench() {
    if (this.loading && !this.task) return html`<div>Loading task…</div>`;
    if (!this.task) return html`<div>No task selected</div>`;

    return html`
      ${this.renderToolbar()}
      ${this.notice ? html`<div aria-live="polite">${this.notice}</div>` : ""}
      ${
        this.actionError
          ? html`<tui-text variant="error">${this.actionError}</tui-text>`
          : ""
      }
      <div aria-hidden="true">&nbsp;</div>
      <tui-flex align="start" wrap>
        <section style="flex: 3 1 60ch; min-width: 0">
          <tui-radio-buttonset
            aria-label="Task editor view"
            value=${this.tab}
            @change=${(event) => (this.tab = event.currentTarget.value)}
          >
            <tui-radio-button value="files">Files</tui-radio-button>
            <tui-radio-button value="metadata">Metadata</tui-radio-button>
          </tui-radio-buttonset>
          ${
            this.tab === "metadata" ? this.renderMetadata() : this.renderFiles()
          }
        </section>
        <aside style="flex: 1 1 32ch; min-width: 0">${this.renderRun()}</aside>
      </tui-flex>
    `;
  }

  render() {
    return html`
      <tui-flex align="baseline" justify="between" wrap>
        <span>${this.tasks.length} core and user task definitions</span>
        <span>
          <tui-button
            ?disabled=${this.busyAction !== ""}
            @click=${this.createTask}
            >New</tui-button
          >
          <tui-button @click=${() => this.loadTasks()}>Refresh</tui-button>
        </span>
      </tui-flex>
      <div aria-hidden="true">&nbsp;</div>
      ${
        this.loading && this.tasks.length === 0
          ? html`<div>Loading tasks…</div>`
          : html`
              <tui-flex align="start" wrap>
                <aside style="flex: 1 1 24ch; min-width: 0">
                  ${this.renderTaskList()}
                </aside>
                <section style="flex: 4 1 70ch; min-width: 0">
                  ${this.renderWorkbench()}
                </section>
              </tui-flex>
            `
      }
    `;
  }
}

customElements.define("sentinel-tasks", SentinelTasks);
