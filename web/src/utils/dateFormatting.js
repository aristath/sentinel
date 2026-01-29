/**
 * Date Formatting Utilities - Shared date/time formatting functions.
 */

/**
 * Format an ISO date string as a locale string.
 * @param {string|null} isoString - ISO date string
 * @returns {string} Formatted date/time string or 'Never'
 */
export function formatTime(isoString) {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  return date.toLocaleString();
}

/**
 * Format an ISO date string as relative time (e.g., "5m ago", "in 2h").
 * @param {string|null} isoString - ISO date string
 * @returns {string} Relative time string or 'Never'
 */
export function formatRelativeTime(isoString) {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  const now = new Date();
  const diff = date - now;

  if (diff < 0) {
    // In the past
    const mins = Math.abs(Math.round(diff / 60000));
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.round(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return formatTime(isoString);
  }

  // In the future
  const mins = Math.round(diff / 60000);
  if (mins < 60) return `in ${mins}m`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `in ${hours}h`;
  return formatTime(isoString);
}

/**
 * Format an ISO date string as compact time-until (e.g., "5m", "2h", "3d").
 * Returns null if the date is in the past or missing.
 * @param {string|null} isoString - ISO date string
 * @returns {string|null} Compact time string or null
 */
export function formatTimeUntil(isoString) {
  if (!isoString) return null;

  const date = new Date(isoString);
  const now = new Date();
  const diff = date - now;

  if (diff > 0) {
    const mins = Math.round(diff / 60000);
    if (mins < 60) return `${mins}m`;
    const hours = Math.round(mins / 60);
    if (hours < 24) return `${hours}h`;
    return `${Math.round(hours / 24)}d`;
  }

  return null;
}

/**
 * Format a duration in milliseconds to a human-readable string.
 * @param {number|null} ms - Duration in milliseconds
 * @returns {string} Formatted duration string
 */
export function formatDuration(ms) {
  if (!ms) return '-';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}
