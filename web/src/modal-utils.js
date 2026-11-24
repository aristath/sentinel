export function formatNumber(value, fractionDigits = 0) {
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("en-GB", {
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
      })
    : "-";
}

export function formatDateTime(value, { seconds = false } = {}) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const date = seconds ? new Date(Number(value) * 1000) : new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "-";
  }

  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelativeTime(value) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "-";
  }

  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const absolute = Math.abs(seconds);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

  if (absolute < 60) {
    return formatter.format(seconds, "second");
  }

  if (absolute < 3600) {
    return formatter.format(Math.round(seconds / 60), "minute");
  }

  if (absolute < 86_400) {
    return formatter.format(Math.round(seconds / 3600), "hour");
  }

  return formatter.format(Math.round(seconds / 86_400), "day");
}

export function formatDuration(milliseconds) {
  const value = Number(milliseconds);

  if (!Number.isFinite(value)) {
    return "-";
  }

  if (value < 1000) {
    return `${Math.round(value)} ms`;
  }

  const seconds = value / 1000;

  if (seconds < 60) {
    return `${seconds.toFixed(seconds < 10 ? 1 : 0)} sec`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return `${minutes} min ${remainder} sec`;
}

export function statusVariant(status) {
  if (["completed", "done", "fresh", "enabled"].includes(status)) {
    return "success";
  }

  if (["failed", "error", "invalid"].includes(status)) {
    return "error";
  }

  if (["queued", "running", "stale"].includes(status)) {
    return "warning";
  }

  return undefined;
}

export function dateInputValue(date) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}
import { html, render } from "lit";

export function requestDialog({
  label,
  message,
  submitLabel,
  placeholder,
  danger = false,
}) {
  return new Promise((resolve) => {
    const container = document.body.appendChild(document.createElement("div"));
    let result;
    render(
      html`
        <wa-dialog
          class="sentinel-compact-dialog"
          label=${label}
          open
          @wa-after-hide=${(event) => {
            if (event.target !== event.currentTarget) return;
            container.remove();
            resolve(result);
          }}
        >
          <form
            class="wa-stack"
            @submit=${(event) => {
              event.preventDefault();
              const input = container.querySelector("wa-input");
              const value = input?.value?.trim();
              if (input && !value) return;
              result = input ? value : true;
              container.querySelector("wa-dialog").open = false;
            }}
          >
            ${message ? html`<div>${message}</div>` : ""}
            ${placeholder
              ? html`
                  <wa-input
                    size="small"
                    label="File name"
                    placeholder=${placeholder}
                    required
                    autofocus
                  ></wa-input>
                `
              : ""}
            <div class="sentinel-layout">
              <wa-button
                size="small"
                type="button"
                ?autofocus=${!placeholder}
                @click=${() => {
                  container.querySelector("wa-dialog").open = false;
                }}
                >Cancel</wa-button
              >
              <wa-button
                size="small"
                type="submit"
                variant=${danger ? "danger" : "brand"}
                >${submitLabel}</wa-button
              >
            </div>
          </form>
        </wa-dialog>
      `,
      container,
    );
  });
}
