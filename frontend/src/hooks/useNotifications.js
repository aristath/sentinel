/**
 * Notifications Hook
 *
 * React hook that provides notification functionality for the application.
 * Automatically displays notifications from the app store's message state,
 * and provides a direct function for showing custom notifications.
 *
 * Features:
 * - Watches app store for messages and displays them as notifications
 * - Provides showNotification function for direct use in components
 * - Uses Mantine notifications for consistent styling
 */
import { useEffect, useCallback } from 'react';
import { notifications } from '@mantine/notifications';
import { useAppStore } from '../stores/appStore';

/**
 * Hook to display notifications from app store messages
 *
 * This hook:
 * 1. Watches the app store's message and messageType state
 * 2. Automatically displays notifications when messages are set
 * 3. Provides a showNotification function for direct use in components
 *
 * @returns {Object} Object with showNotification function
 * @returns {Function} showNotification - Function to show a notification directly
 *   @param {string} message - Notification message text
 *   @param {string} type - Notification type: 'success', 'error', or 'info' (default: 'success')
 */
export function useNotifications() {
  const { message, messageType } = useAppStore();

  // Watch app store messages and display as notifications
  useEffect(() => {
    if (message) {
      notifications.show({
        title: messageType === 'error' ? 'Error' : messageType === 'success' ? 'Success' : 'Info',
        message,
        color: messageType === 'error' ? 'red' : messageType === 'success' ? 'green' : 'blue',
        autoClose: 3000,  // Auto-close after 3 seconds
      });
    }
  }, [message, messageType]);

  // Memoize the showNotification function to maintain stable reference
  // This prevents unnecessary re-renders in components using this hook
  const showNotification = useCallback((message, type = 'success') => {
    notifications.show({
      title: type === 'error' ? 'Error' : type === 'success' ? 'Success' : 'Info',
      message,
      color: type === 'error' ? 'red' : type === 'success' ? 'green' : 'blue',
      autoClose: 3000,  // Auto-close after 3 seconds
    });
  }, []);

  return { showNotification };
}
