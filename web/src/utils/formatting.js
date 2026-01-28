/**
 * Formatting Utilities - Single source of truth for all formatting functions.
 *
 * Usage:
 *   import { formatCurrency, formatEur, formatPercent } from '../utils/formatting';
 *   formatCurrency(1000.50, 'USD')     // "$1,000.50"
 *   formatEur(1000.50)                 // "€1,000.50"
 *   formatPercent(12.5)                // "+12.5%"
 *   formatPercent(-5.3, false)         // "-5.3%"
 */

/**
 * Format a value as currency.
 *
 * @param {number|null|undefined} value - The numeric value to format
 * @param {string} currency - Currency code (EUR, USD, GBP, HKD, etc.)
 * @param {number} decimals - Number of decimal places (default: 2)
 * @returns {string} Formatted currency string
 */
export function formatCurrency(value, currency = 'EUR', decimals = 2) {
  if (value === null || value === undefined) return '-';

  // Use Intl.NumberFormat for proper localization
  return new Intl.NumberFormat('en-EU', {
    style: 'currency',
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * Format a value as EUR currency.
 * Convenience wrapper for formatCurrency with EUR.
 *
 * @param {number|null|undefined} value - The numeric value to format
 * @param {number} decimals - Number of decimal places (default: 2)
 * @returns {string} Formatted EUR string (e.g., "€1,234.56")
 */
export function formatEur(value, decimals = 2) {
  return formatCurrency(value, 'EUR', decimals);
}

/**
 * Format a value as currency with symbol prefix.
 * Alternative formatting using locale-based number formatting with symbol prefix.
 *
 * @param {number|null|undefined} value - The numeric value to format
 * @param {string} currency - Currency code (EUR, USD, GBP, HKD)
 * @param {number} decimals - Number of decimal places (default: 2)
 * @returns {string} Formatted currency string with symbol prefix
 */
export function formatCurrencySymbol(value, currency = 'EUR', decimals = 2) {
  if (value === null || value === undefined) return '-';

  const symbols = {
    EUR: '€',
    USD: '$',
    GBP: '£',
    HKD: 'HK$',
    CHF: 'CHF ',
    JPY: '¥',
    CNY: '¥',
  };
  const symbol = symbols[currency] || currency + ' ';

  return `${symbol}${value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

/**
 * Format a value as a percentage.
 *
 * @param {number|null|undefined} value - The percentage value (e.g., 12.5 for 12.5%)
 * @param {boolean} showSign - Whether to show + sign for positive values (default: true)
 * @param {number} decimals - Number of decimal places (default: 1)
 * @returns {string} Formatted percentage string (e.g., "+12.5%")
 */
export function formatPercent(value, showSign = true, decimals = 1) {
  if (value === null || value === undefined) return '-';

  const sign = showSign && value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format a large number with abbreviation (K, M, B).
 *
 * @param {number|null|undefined} value - The numeric value to format
 * @param {number} decimals - Number of decimal places (default: 1)
 * @returns {string} Abbreviated number string (e.g., "1.2M")
 */
export function formatCompact(value, decimals = 1) {
  if (value === null || value === undefined) return '-';

  const absValue = Math.abs(value);

  if (absValue >= 1e9) {
    return (value / 1e9).toFixed(decimals) + 'B';
  }
  if (absValue >= 1e6) {
    return (value / 1e6).toFixed(decimals) + 'M';
  }
  if (absValue >= 1e3) {
    return (value / 1e3).toFixed(decimals) + 'K';
  }

  return value.toFixed(decimals);
}

/**
 * Format a number with thousand separators.
 *
 * @param {number|null|undefined} value - The numeric value to format
 * @param {number} decimals - Number of decimal places (default: 0)
 * @returns {string} Formatted number string
 */
export function formatNumber(value, decimals = 0) {
  if (value === null || value === undefined) return '-';

  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
