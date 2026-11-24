import { LitElement, html } from "lit";
import { deleteJson, getJson, postJson, putJson } from "./api.js";
import { formatDateTime, requestDialog, statusVariant } from "./modal-utils.js";
import "./sentinel-code-editor.js";

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
    return requestDialog({
      label: "Discard changes",
      message: `Discard unsaved changes to "${this.task?.name || this.selectedId}"?`,
      submitLabel: "Discard",
      danger: true,
    });
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
    if (!force && !(await this.confirmClose())) return;

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
    const task = this.task;
    if (
      !task ||
      !(await requestDialog({
        label: "Delete task",
        message: `Delete task "${task.name}"?`,
        submitLabel: "Delete",
        danger: true,
      }))
    )
      return;

    this.busyAction = "delete-task";

    try {
      await deleteJson(`/api/tasks/${encodeURIComponent(task.id)}`);
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

  async createFile() {
    const name = await requestDialog({
      label: "New file",
      placeholder: "prompt.md",
      submitLabel: "Create",
    });
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
    if (
      !(await requestDialog({
        label: "Delete file",
        message: `Permanently delete "${file.name}"?`,
        submitLabel: "Delete",
        danger: true,
      }))
    )
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
      <wa-card
        ><span slot="header">Tasks</span>
        ${groups.map(
          ([label, tasks], index) => html`
            ${index > 0 ? html`<div aria-hidden="true">&nbsp;</div>` : ""}
            <div>${label}</div>
            ${tasks.map(
              (task) => html`
                <div>
                  <span aria-hidden="true"
                    >${task.id === this.selectedId ? "▶" : " "}&nbsp;</span
                  ><wa-button
                    size="small"
                    @click=${() => this.selectTask(task.id)}
                    >${task.name}</wa-button
                  >
                  <span
                    data-tone=${task.invalid
                      ? "error"
                      : task.enabled
                        ? "success"
                        : ""}
                    >${task.invalid
                      ? "invalid"
                      : task.enabled
                        ? "on"
                        : "off"}</span
                  >
                  <div>${task.id}</div>
                </div>
              `,
            )}
          `,
        )}
      </wa-card>
    `;
  }

  renderToolbar() {
    return html`
      <div
        class="sentinel-layout"
        data-align="baseline"
        data-justify="between"
        data-wrap
      >
        <span>
          ${this.task.name}
          ${this.dirty ? html`<span data-tone="warning">unsaved</span>` : ""} ·
          ${this.task.source} · ${this.task.id}
        </span>
        <span>
          <wa-button
            size="small"
            ?disabled=${this.dirty || this.running || this.busyAction !== ""}
            @click=${this.validateTask}
            >Check</wa-button
          >
          ${this.running
            ? html`<wa-button
                size="small"
                variant="danger"
                @click=${this.stopRun}
                >Stop</wa-button
              >`
            : html`<wa-button
                size="small"
                ?disabled=${this.dirty ||
                this.task.invalid ||
                this.busyAction !== ""}
                @click=${this.startRun}
                >Run</wa-button
              >`}
          <wa-button
            size="small"
            variant="danger"
            ?disabled=${this.running ||
            this.task.source === "core" ||
            this.busyAction !== ""}
            @click=${this.deleteTask}
            >Delete</wa-button
          >
        </span>
      </div>
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
      <div class="sentinel-layout" data-align="start" data-wrap>
        <wa-card style="flex: 1 1 20ch; min-width: 0"
          ><span slot="header">Files</span>
          <div>
            <wa-button size="small" @click=${this.createFile}
              >New File</wa-button
            >
          </div>
          ${this.files.map(
            (file) => html`
              <div>
                <span aria-hidden="true"
                  >${file.name === this.activeFile ? "▶" : " "}&nbsp;</span
                ><wa-button
                  size="small"
                  @click=${() => this.selectFile(file.name)}
                  >${file.name}</wa-button
                >
                ${this.drafts[file.name] !== this.baselines[file.name] &&
                file.name in this.baselines
                  ? html`<span data-tone="warning">unsaved</span>`
                  : ""}
                ${file.protected ? "protected" : ""}
                ${!file.protected
                  ? html`<wa-button
                      size="small"
                      variant="danger"
                      ?disabled=${this.running}
                      @click=${() => this.deleteFile(file)}
                      >Delete</wa-button
                    >`
                  : ""}
              </div>
            `,
          )}
        </wa-card>
        <section style="flex: 4 1 60ch; min-width: 0">
          <div>
            ${this.activeFile ?? "No file selected"}
            ${active?.protected ? "· protected" : ""}
            ${dirty ? html`· <span data-tone="warning">unsaved</span>` : ""}
            <wa-button
              size="small"
              ?disabled=${!dirty || this.running || this.busyAction !== ""}
              @click=${this.saveFile}
              >Save</wa-button
            >
          </div>
          <sentinel-code-editor
            aria-label="${this.activeFile ?? "Task file"} content"
            document-id="${this.selectedId ?? ""}/${this.activeFile ?? ""}"
            filename=${this.activeFile ?? "file.txt"}
            language=${active?.language ?? "plaintext"}
            .value=${draft}
            ?disabled=${!this.activeFile || this.running}
            @input=${(event) => this.updateDraft(event.currentTarget.value)}
          ></sentinel-code-editor>
        </section>
      </div>
    `;
  }

  renderSchedule() {
    const parts = this.intervalParts();

    return html`
      <div>Schedule</div>
      <wa-radio-group
        size="small"
        aria-label="Task schedule mode"
        .value=${this.scheduleMode}
        ?disabled=${this.running}
        @change=${(event) => this.setScheduleMode(event.currentTarget.value)}
      >
        <wa-radio appearance="button" value="off">Off</wa-radio>
        <wa-radio appearance="button" value="cron">Cron</wa-radio>
        <wa-radio appearance="button" value="interval">Interval</wa-radio>
      </wa-radio-group>
      ${this.scheduleMode === "cron"
        ? html`
            <div>
              <label
                >Cron&nbsp;<wa-input
                  size="small"
                  .value=${this.metadata.schedule ?? defaultCron}
                  style="inline-size: 24ch; max-inline-size: 100%"
                  ?disabled=${this.running}
                  @input=${(event) =>
                    this.patchMetadata({
                      schedule: event.currentTarget.value || defaultCron,
                    })}
                ></wa-input
              ></label>
            </div>
            ${cronFields.map((field) => {
              const selected = this.cronValues(field.index);

              return html`
                <div>${field.label}</div>
                <div class="sentinel-layout" data-align="baseline" data-wrap>
                  ${field.options.map(
                    ([value, label]) => html`
                      <wa-switch
                        size="small"
                        .checked=${selected.has(value)}
                        ?disabled=${this.running}
                        @change=${(event) =>
                          this.toggleCronValue(
                            field.index,
                            value,
                            event.currentTarget.checked,
                          )}
                        >${value} ${label}</wa-switch
                      ><span aria-hidden="true">&nbsp;</span>
                    `,
                  )}
                </div>
              `;
            })}
          `
        : ""}
      ${this.scheduleMode === "interval"
        ? html`
            <div class="sentinel-layout" data-align="baseline" data-wrap>
              <label
                >Days&nbsp;<wa-input
                  size="small"
                  type="number"
                  min="0"
                  .value=${parts.days}
                  @change=${(event) =>
                    this.patchInterval("days", event.currentTarget.value)}
                ></wa-input
              ></label>

              <label
                >Hours&nbsp;<wa-input
                  size="small"
                  type="number"
                  min="0"
                  max="23"
                  .value=${parts.hours}
                  @change=${(event) =>
                    this.patchInterval("hours", event.currentTarget.value)}
                ></wa-input
              ></label>

              <label
                >Minutes&nbsp;<wa-input
                  size="small"
                  type="number"
                  min="0"
                  max="59"
                  .value=${parts.minutes}
                  @change=${(event) =>
                    this.patchInterval("minutes", event.currentTarget.value)}
                ></wa-input
              ></label>

              <label
                >Run when&nbsp;<wa-select
                  size="small"
                  .value=${this.metadata.schedulePolicy?.runWhen ?? "idle"}
                  @change=${(event) =>
                    this.patchSchedulePolicy({
                      runWhen: event.currentTarget.value,
                    })}
                >
                  <wa-option value="idle">Idle</wa-option>
                  <wa-option value="immediate">Immediate</wa-option>
                </wa-select></label
              >

              <label
                >Priority&nbsp;<wa-input
                  size="small"
                  type="number"
                  min="-1000"
                  max="1000"
                  .value=${this.metadata.schedulePolicy?.priority ?? 0}
                  @change=${(event) =>
                    this.patchSchedulePolicy({
                      priority: Number(event.currentTarget.value),
                    })}
                ></wa-input
              ></label>
            </div>
          `
        : ""}
    `;
  }

  renderMetadata() {
    if (!this.metadata) return html`<div>Loading metadata…</div>`;

    return html`
      <div
        class="sentinel-layout"
        data-align="baseline"
        data-justify="between"
        data-wrap
      >
        <span>Metadata</span>
        <wa-button
          size="small"
          ?disabled=${!this.metadataDirty ||
          this.running ||
          this.busyAction !== ""}
          @click=${this.saveMetadata}
          >Save</wa-button
        >
      </div>
      <div>
        <label
          ><span>Name</span>
          <wa-input
            size="small"
            style="inline-size: 100%"
            .value=${this.metadata.name}
            @input=${(event) =>
              this.patchMetadata({ name: event.currentTarget.value })}
          ></wa-input
        ></label>
        <wa-switch
          size="small"
          .checked=${this.metadata.enabled}
          ?disabled=${this.running}
          @change=${(event) =>
            this.patchMetadata({ enabled: event.currentTarget.checked })}
          >Enabled</wa-switch
        >
      </div>
      <div>
        <label>Description</label>
        <wa-textarea
          size="small"
          aria-label="Task description"
          style="inline-size: 100%"
          rows="4"
          .value=${this.metadata.description}
          ?disabled=${this.running}
          @input=${(event) =>
            this.patchMetadata({ description: event.currentTarget.value })}
        ></wa-textarea>
      </div>
      <div>
        <label
          ><span>Tags</span>
          <wa-input
            size="small"
            style="inline-size: 100%"
            .value=${this.metadata.tags.join(", ")}
            ?disabled=${this.running}
            @input=${(event) =>
              this.patchMetadata({
                tags: event.currentTarget.value
                  .split(",")
                  .map((tag) => tag.trim())
                  .filter(Boolean),
              })}
          ></wa-input
        ></label>
      </div>
      <div>
        <label
          >Timeout (seconds)&nbsp;<wa-input
            size="small"
            type="number"
            min="0"
            step="60"
            .value=${this.metadata.timeout}
            ?disabled=${this.running}
            @change=${(event) =>
              this.patchMetadata({
                timeout: Number(event.currentTarget.value),
              })}
          ></wa-input
        ></label>
      </div>
      <div>
        <label
          ><span>Working directory</span>
          <wa-input
            size="small"
            style="inline-size: 100%"
            .value=${this.metadata.cwd}
            placeholder="@/tasks/artifacts/{{task-id}}"
            ?disabled=${this.running}
            @input=${(event) =>
              this.patchMetadata({ cwd: event.currentTarget.value })}
          ></wa-input
        ></label>
      </div>
      <div aria-hidden="true">&nbsp;</div>
      ${this.renderSchedule()}
    `;
  }

  renderRun() {
    return html`
      <wa-card
        ><span slot="header">Run</span>
        <div>
          Status
          <span data-tone=${statusVariant(this.run?.status) || ""}
            >${this.run?.status ?? "idle"}</span
          >
        </div>
        <div>History</div>
        ${this.runs.length
          ? this.runs.map(
              (run) => html`
                <div>
                  <span aria-hidden="true"
                    >${run.id === this.runId ? "▶" : " "}&nbsp;</span
                  ><wa-button size="small" @click=${() => this.loadRun(run.id)}
                    >${run.status} -
                    ${run.createdAt
                      ? formatDateTime(run.createdAt)
                      : run.id}</wa-button
                  >
                </div>
              `,
            )
          : "No runs"}
        <div>Inputs (JSON)</div>
        <wa-textarea
          size="small"
          aria-label="Task run inputs"
          style="inline-size: 100%"
          rows="4"
          .value=${this.runInputs}
          ?disabled=${this.running}
          @input=${(event) => (this.runInputs = event.currentTarget.value)}
        ></wa-textarea>
        <div>Log</div>
        ${(this.run?.log ?? []).map(
          (line) => html`<div><code>${line}</code></div>`,
        )}
        ${this.run?.error
          ? html`<span data-tone="error">${this.run.error}</span>`
          : ""}
        <pre style="white-space: pre-wrap; overflow-wrap: anywhere">
${this.run?.liveOutput ?? " "}</pre
        >
      </wa-card>
    `;
  }

  renderWorkbench() {
    if (this.loading && !this.task) return html`<div>Loading task…</div>`;
    if (!this.task) return html`<div>No task selected</div>`;

    return html`
      ${this.renderToolbar()}
      ${this.notice ? html`<div aria-live="polite">${this.notice}</div>` : ""}
      ${this.actionError
        ? html`<span data-tone="error">${this.actionError}</span>`
        : ""}
      <div aria-hidden="true">&nbsp;</div>
      <div class="sentinel-layout" data-align="start" data-wrap>
        <section style="flex: 3 1 60ch; min-width: 0">
          <wa-radio-group
            size="small"
            aria-label="Task editor view"
            .value=${this.tab}
            @change=${(event) => (this.tab = event.currentTarget.value)}
          >
            <wa-radio appearance="button" value="files">Files</wa-radio>
            <wa-radio appearance="button" value="metadata">Metadata</wa-radio>
          </wa-radio-group>
          ${this.tab === "metadata"
            ? this.renderMetadata()
            : this.renderFiles()}
        </section>
        <aside style="flex: 1 1 32ch; min-width: 0">${this.renderRun()}</aside>
      </div>
    `;
  }

  render() {
    return html`
      <div
        class="sentinel-layout"
        data-align="baseline"
        data-justify="between"
        data-wrap
      >
        <span>${this.tasks.length} core and user task definitions</span>
        <span>
          <wa-button
            size="small"
            ?disabled=${this.busyAction !== ""}
            @click=${this.createTask}
            >New</wa-button
          >
          <wa-button size="small" @click=${() => this.loadTasks()}
            >Refresh</wa-button
          >
        </span>
      </div>
      <div aria-hidden="true">&nbsp;</div>
      ${this.loading && this.tasks.length === 0
        ? html`<div>Loading tasks…</div>`
        : html`
            <div class="sentinel-layout" data-align="start" data-wrap>
              <aside style="flex: 1 1 24ch; min-width: 0">
                ${this.renderTaskList()}
              </aside>
              <section style="flex: 4 1 70ch; min-width: 0">
                ${this.renderWorkbench()}
              </section>
            </div>
          `}
    `;
  }
}

customElements.define("sentinel-tasks", SentinelTasks);
