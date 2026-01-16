/**
 * Formatting Utility Functions
 *
 * Provides consistent formatting for currency, percentages, numbers, dates, and timestamps
 * throughout the application. All functions handle null/undefined values gracefully.
 */

/**
 * Formats a numeric value as currency
 *
 * Uses Intl.NumberFormat for locale-aware currency formatting.
 * Returns '-' for null, undefined, or NaN values.
 *
 * @param {number|null|undefined} value - Numeric value to format
 * @param {string} currency - Currency code (default: 'EUR')
 * @returns {string} Formatted currency string (e.g., "€1,234.56") or "-" for invalid values
 */
export function formatCurrency(value, currency = 'EUR') {
  if (value == null || isNaN(value)) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Formats a decimal value as a percentage
 *
 * Converts decimal (0.0 to 1.0) to percentage (0% to 100%).
 * Returns '-' for null, undefined, or NaN values.
 *
 * @param {number|null|undefined} value - Decimal value (0.0 to 1.0)
 * @param {number} decimals - Number of decimal places (default: 1)
 * @returns {string} Formatted percentage string (e.g., "85.5%") or "-" for invalid values
 */
export function formatPercent(value, decimals = 1) {
  if (value == null || isNaN(value)) return '-';
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Formats a numeric value with specified decimal places
 *
 * Returns '-' for null, undefined, or NaN values.
 *
 * @param {number|null|undefined} value - Numeric value to format
 * @param {number} decimals - Number of decimal places (default: 2)
 * @returns {string} Formatted number string (e.g., "123.45") or "-" for invalid values
 */
export function formatNumber(value, decimals = 2) {
  if (value == null || isNaN(value)) return '-';
  return value.toFixed(decimals);
}

/**
 * Formats a date value as a locale-aware date string
 *
 * Uses browser's locale settings for date formatting.
 * Returns '-' for null, undefined, or invalid date values.
 *
 * @param {string|Date|null|undefined} date - Date value (ISO string, Date object, or timestamp)
 * @returns {string} Formatted date string (locale-dependent) or "-" for invalid values
 */
export function formatDate(date) {
  if (!date) return '-';
  const d = new Date(date);
  return d.toLocaleDateString();
}

/**
 * Formats a date value as a date-time string (YYYY-MM-DD HH:MM)
 *
 * Uses ISO-like format for consistency across locales.
 * Returns '-' for null, undefined, or invalid date values.
 *
 * @param {string|Date|null|undefined} date - Date value (ISO string, Date object, or timestamp)
 * @returns {string} Formatted date-time string (e.g., "2024-01-15 14:30") or "-" for invalid values
 */
export function formatDateTime(date) {
  if (!date) return '-';
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');  // Month is 0-indexed
  const day = String(d.getDate()).padStart(2, '0');
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

/**
 * Formats a Unix timestamp (seconds since epoch) as a date-time string
 *
 * Converts Unix timestamp (seconds) to JavaScript Date (milliseconds).
 * Uses ISO-like format for consistency.
 * Returns '-' for null, undefined, or invalid timestamp values.
 *
 * @param {number|null|undefined} timestamp - Unix timestamp in seconds
 * @returns {string} Formatted date-time string (e.g., "2024-01-15 14:30") or "-" for invalid values
 */
export function formatTimestamp(timestamp) {
  if (!timestamp) return '-';
  // Unix timestamps are in seconds, JavaScript Date expects milliseconds
  const d = new Date(timestamp * 1000);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');  // Month is 0-indexed
  const day = String(d.getDate()).padStart(2, '0');
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}
