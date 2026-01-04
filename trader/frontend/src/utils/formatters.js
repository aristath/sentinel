/**
 * Utility functions for formatting data
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

export function formatPercent(value, decimals = 1) {
  if (value == null || isNaN(value)) return '-';
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatNumber(value, decimals = 2) {
  if (value == null || isNaN(value)) return '-';
  return value.toFixed(decimals);
}

export function formatDate(date) {
  if (!date) return '-';
  const d = new Date(date);
  return d.toLocaleDateString();
}

export function formatDateTime(date) {
  if (!date) return '-';
  const d = new Date(date);
  return d.toLocaleString();
}
