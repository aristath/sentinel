import { LitElement, html } from "lit";
import { getJson, postJson, putJson } from "./api.js";
import { LiveResource } from "./live-resource.js";
import {
  formatDateTime,
  formatDuration,
  formatRelativeTime,
  statusVariant,
} from "./modal-utils.js";

const intervalMultipliers = {
  minutes: 1,
  hours: 60,
  days: 1440,
};

function displayInterval(minutes) {
  if (minutes >= 1440 && minutes % 1440 === 0) {
    return { value: minutes / 1440, unit: "days" };
  }

  if (minutes >= 60 && minutes % 60 === 0) {
    return { value: minutes / 60, unit: "hours" };
  }

  return { value: minutes, unit: "minutes" };
}

class SentinelScheduler extends LitElement {
  static properties = {
    tab: { state: true },
    busyAction: { state: true },
    actionError: { state: true },
    notice: { state: true },
  };

  constructor() {
    super();
    this.tab = "status";
    this.busyAction = "";
    this.actionError = "";
    this.notice = "";
  }

  schedules = new LiveResource(
    this,
    (signal) => getJson("/api/jobs/schedules", { signal }),
    { interval: 5000 },
  );

  status = new LiveResource(
    this,
    (signal) => getJson("/api/jobs", { signal }),
    { interval: 3000 },
  );

  history = new LiveResource(
    this,
    (signal) => getJson("/api/jobs/history?limit=100", { signal }),
    { interval: 10_000 },
  );

  createRenderRoot() {
    return this;
  }

  async updateSchedule(jobType, values) {
    this.busyAction = `update:${jobType}`;
    this.actionError = "";
    this.notice = "";

    try {
      await putJson(
        `/api/jobs/schedules/${encodeURIComponent(jobType)}`,
        values,
      );
      this.notice = `${jobType} updated`;
      await this.schedules.refresh();
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  async runJob(jobType) {
    this.busyAction = `run:${jobType}`;
    this.actionError = "";
    this.notice = "";

    try {
      await postJson(`/api/jobs/${encodeURIComponent(jobType)}/run`);
      this.notice = `${jobType} started`;
      await Promise.all([
        this.status.refresh(),
        this.schedules.refresh(),
        this.history.refresh(),
      ]);
    } catch (error) {
      this.actionError = error.message;
    } finally {
      this.busyAction = "";
    }
  }

  updateInterval(job, field, value, unit) {
    const minutes = Math.round(Number(value) * intervalMultipliers[unit]);

    if (minutes > 0) {
      this.updateSchedule(job.job_type, { [field]: minutes });
    }
  }

  renderInterval(job, field, label) {
    const minutes = Number(job[field] ?? job.interval_minutes);
    const display = displayInterval(minutes);

    return html`
      <label
        >${label}&nbsp;<wa-input
          size="small"
          type="number"
          min="1"
          max="10080"
          .value=${display.value}
          ?disabled=${this.busyAction !== ""}
          @change=${(event) =>
            this.updateInterval(
              job,
              field,
              event.currentTarget.value,
              display.unit,
            )}
        ></wa-input
      ></label>
      <wa-select
        size="small"
        aria-label="${label} unit for ${job.job_type}"
        .value=${display.unit}
        ?disabled=${this.busyAction !== ""}
        @change=${(event) =>
          this.updateInterval(
            job,
            field,
            display.value,
            event.currentTarget.value,
          )}
      >
        <wa-option value="minutes">Minutes</wa-option>
        <wa-option value="hours">Hours</wa-option>
        <wa-option value="days">Days</wa-option>
      </wa-select>
    `;
  }

  renderStatus() {
    const status = this.status.value ?? {};

    return html`
      <wa-card
        ><span slot="header">Currently Running</span>
        ${status.current ?? "No job running"}
      </wa-card>
      <div aria-hidden="true">&nbsp;</div>
      <wa-card
        ><span slot="header">Upcoming Jobs</span>
        ${status.upcoming?.length
          ? status.upcoming.map(
              (job) => html`
                <div>${job.job_type} · ${formatRelativeTime(job.next_run)}</div>
              `,
            )
          : "No upcoming jobs"}
      </wa-card>
      <div aria-hidden="true">&nbsp;</div>
      <wa-card
        ><span slot="header">Recent Jobs</span>
        ${status.recent?.length
          ? status.recent.map(
              (job) => html`
                <div>
                  ${job.job_type} ·
                  <span data-tone=${statusVariant(job.status) || ""}
                    >${job.status}</span
                  >
                  · ${formatRelativeTime(job.executed_at)}
                </div>
              `,
            )
          : "No recent jobs"}
      </wa-card>
    `;
  }

  renderJob(job) {
    const busy = this.busyAction !== "";

    return html`
      <div>
        <div
          class="sentinel-layout"
          data-align="baseline"
          data-justify="between"
          data-wrap
        >
          <span>
            ${job.job_type}
            ${job.last_status
              ? html`<span data-tone=${statusVariant(job.last_status) || ""}
                  >${job.last_status}</span
                >`
              : ""}
          </span>
          <span>
            <label
              >Timing&nbsp;<wa-select
                size="small"
                .value=${String(job.market_timing)}
                ?disabled=${busy}
                @change=${(event) =>
                  this.updateSchedule(job.job_type, {
                    market_timing: Number(event.currentTarget.value),
                  })}
              >
                <wa-option value="0">Any time</wa-option>
                <wa-option value="1">After close</wa-option>
                <wa-option value="2">During open</wa-option>
                <wa-option value="3">All closed</wa-option>
              </wa-select></label
            >
            <wa-button
              size="small"
              ?disabled=${busy}
              @click=${() => this.runJob(job.job_type)}
              >${this.busyAction === `run:${job.job_type}`
                ? "Running…"
                : "Run"}</wa-button
            >
          </span>
        </div>
        <div>${job.description ?? ""}</div>
        <div class="sentinel-layout" data-align="baseline" data-wrap>
          ${this.renderInterval(job, "interval_minutes", "Interval")}
          ${this.renderInterval(
            job,
            "interval_market_open_minutes",
            "Market open",
          )}
          ${job.next_run
            ? html`<span aria-hidden="true">&nbsp;·&nbsp;</span
                ><span>Next ${formatRelativeTime(job.next_run)}</span>`
            : ""}
        </div>
      </div>
    `;
  }

  renderJobs() {
    const schedules = this.schedules.value?.schedules ?? [];
    const categories = [
      ...new Set(schedules.map((job) => job.category).filter(Boolean)),
    ];

    return categories.map(
      (category, index) => html`
        ${index > 0 ? html`<div aria-hidden="true">&nbsp;</div>` : ""}
        <wa-card
          ><span slot="header">${category}</span>
          ${schedules
            .filter((job) => job.category === category)
            .map(
              (job, jobIndex) => html`
                ${jobIndex > 0 ? html`<wa-divider></wa-divider>` : ""}
                ${this.renderJob(job)}
              `,
            )}
        </wa-card>
      `,
    );
  }

  renderHistory() {
    const history = this.history.value?.history ?? [];

    if (history.length === 0) {
      return html`<div>No execution history</div>`;
    }

    return html`
      <div style="overflow: auto; min-width: 0">
        <table style="border-collapse: collapse; width: 100%">
          <thead>
            <tr>
              <th style="text-align: left">Job ID</th>
              <th style="text-align: left">Status</th>
              <th style="text-align: left">Duration</th>
              <th style="text-align: left">Executed</th>
              <th style="text-align: left">Error</th>
            </tr>
          </thead>
          <tbody>
            ${history.map(
              (entry) => html`
                <tr>
                  <td style="text-align: left; vertical-align: top">
                    ${entry.job_id}
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
                    ${formatDateTime(entry.executed_at, { seconds: true })}
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

  render() {
    const error =
      this.schedules.error ?? this.status.error ?? this.history.error;
    const loading =
      (!this.schedules.value && this.schedules.loading) ||
      (!this.status.value && this.status.loading) ||
      (!this.history.value && this.history.loading);

    if (loading) {
      return html`<div>Loading scheduler…</div>`;
    }

    if (error) {
      return html`<span data-tone="error"
        >Error loading scheduler: ${error.message}</span
      >`;
    }

    return html`
      <wa-radio-group
        size="small"
        aria-label="Scheduler view"
        .value=${this.tab}
        @change=${(event) => (this.tab = event.currentTarget.value)}
      >
        <wa-radio appearance="button" value="status">Status</wa-radio>
        <wa-radio appearance="button" value="jobs">Jobs</wa-radio>
        <wa-radio appearance="button" value="history">History</wa-radio>
      </wa-radio-group>
      <div aria-hidden="true">&nbsp;</div>
      ${this.tab === "jobs"
        ? this.renderJobs()
        : this.tab === "history"
          ? this.renderHistory()
          : this.renderStatus()}
      ${this.notice ? html`<div aria-live="polite">${this.notice}</div>` : ""}
      ${this.actionError
        ? html`<span data-tone="error">${this.actionError}</span>`
        : ""}
    `;
  }
}

customElements.define("sentinel-scheduler", SentinelScheduler);
