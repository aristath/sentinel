/**
 * Confirmation Dialog Utility
 *
 * Provides a simple confirmation dialog wrapper around the browser's native confirm().
 * This is a temporary solution - can be replaced with a Mantine modal in the future
 * for better UX and styling consistency.
 *
 * Note: The native confirm() dialog blocks the UI thread and doesn't match
 * the application's design system. Consider migrating to Mantine's Modal component
 * for a better user experience.
 */

/**
 * Shows a confirmation dialog and returns the user's choice
 *
 * Uses the browser's native confirm() dialog which blocks the UI thread
 * until the user responds. Returns true if user clicks "OK", false if "Cancel".
 *
 * @param {string} message - Confirmation message to display
 * @returns {boolean} True if user confirmed, false if cancelled
 */
export function confirmDialog(message) {
  return window.confirm(message);
}
