/**
 * Arduino Trader - Utility Functions
 * Formatting and helper functions used across components
 */

/**
 * Format a number as currency (EUR)
 * @param {number|null} value - The value to format
 * @returns {string} Formatted currency string
 */
function formatCurrency(value) {
  if (value == null) return '-';
  return new Intl.NumberFormat('en-IE', {
    style: 'currency',
    currency: 'EUR'
  }).format(value);
}

/**
 * Format a date string as date only
 * @param {string|null} dateStr - ISO date string
 * @returns {string} Formatted date
 */
function formatDate(dateStr) {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString('de-DE');
}

/**
 * Format a date string as date and time
 * @param {string|null} dateStr - ISO date string
 * @returns {string} Formatted date and time
 */
function formatDateTime(dateStr) {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * Format a number with specified decimal places
 * @param {number|null} value - The value to format
 * @param {number} decimals - Number of decimal places (default 2)
 * @returns {string} Formatted number string
 */
function formatNumber(value, decimals = 2) {
  if (value == null) return '-';
  return value.toLocaleString('en-IE', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

/**
 * Format a percentage value
 * @param {number} value - Decimal value (e.g., 0.5 for 50%)
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted percentage
 */
function formatPercent(value, decimals = 1) {
  if (value == null) return '-';
  return (value * 100).toFixed(decimals) + '%';
}

/**
 * Format a score value
 * @param {number|null} value - Score value (0-1)
 * @returns {string} Formatted score
 */
function formatScore(value) {
  if (value == null) return '-';
  return value.toFixed(2);
}

/**
 * Get Tailwind class for score value
 * @param {number|null} score - Score value (0-1)
 * @returns {string} Tailwind class names
 */
function getScoreClass(score) {
  if (score == null) return 'bg-gray-700 text-gray-400';
  if (score > 0.7) return 'bg-green-900/50 text-green-400';
  if (score > 0.4) return 'bg-yellow-900/50 text-yellow-400';
  return 'bg-gray-700 text-gray-400';
}

/**
 * Format a priority score value
 * @param {number|null} value - Priority score (0-3 range)
 * @returns {string} Formatted priority
 */
function formatPriority(value) {
  if (value == null) return '-';
  return value.toFixed(2);
}

/**
 * Get Tailwind class for priority score value
 * @param {number|null} score - Priority score (0-1.5 range, can be higher with multipliers)
 * @returns {string} Tailwind class names
 */
function getPriorityClass(score) {
  if (score == null) return 'bg-gray-700 text-gray-400';
  if (score >= 0.6) return 'bg-green-900/50 text-green-400';
  if (score >= 0.4) return 'bg-blue-900/50 text-blue-400';
  return 'bg-gray-700 text-gray-400';
}

/**
 * Get CSS class for allocation deviation
 * @param {number} deviation - Deviation value
 * @returns {string} CSS class suffix
 */
function getDeviationClass(deviation) {
  if (deviation < -0.05) return 'text-red-400';
  if (deviation > 0.05) return 'text-green-400';
  return 'text-gray-400';
}

/**
 * Get Tailwind class for country tag
 * @param {string} country - Country name (e.g., "United States", "Germany")
 * @returns {string} Tailwind class names
 */
function getGeoTagClass(country) {
  // Use a simple color scheme - can be enhanced later with country-specific colors
  if (!country) return 'bg-gray-700 text-gray-400';
  // Generate a consistent color based on country name hash
  const hash = country.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const colors = [
    'bg-blue-900/50 text-blue-400',
    'bg-red-900/50 text-red-400',
    'bg-green-900/50 text-green-400',
    'bg-yellow-900/50 text-yellow-400',
    'bg-purple-900/50 text-purple-400',
    'bg-cyan-900/50 text-cyan-400'
  ];
  return colors[hash % colors.length];
}

/**
 * Get Tailwind class for trade side tag
 * @param {string} side - Trade side (BUY, SELL)
 * @returns {string} Tailwind class names
 */
function getSideTagClass(side) {
  return side === 'BUY' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400';
}

// Make functions available globally for Alpine.js
window.formatCurrency = formatCurrency;
window.formatNumber = formatNumber;
window.formatDate = formatDate;
window.formatDateTime = formatDateTime;
window.formatPercent = formatPercent;
window.formatScore = formatScore;
window.formatPriority = formatPriority;
window.getScoreClass = getScoreClass;
window.getPriorityClass = getPriorityClass;
window.getDeviationClass = getDeviationClass;
window.getGeoTagClass = getGeoTagClass;
window.getSideTagClass = getSideTagClass;
