import { useEffect, useCallback } from 'react';
import { notifications } from '@mantine/notifications';
import { useAppStore } from '../stores/appStore';

/**
 * Hook to display notifications from app store messages
 * Also returns a showNotification function for direct use
 */
export function useNotifications() {
  const { message, messageType } = useAppStore();

  useEffect(() => {
    if (message) {
      notifications.show({
        title: messageType === 'error' ? 'Error' : messageType === 'success' ? 'Success' : 'Info',
        message,
        color: messageType === 'error' ? 'red' : messageType === 'success' ? 'green' : 'blue',
        autoClose: 3000,
      });
    }
  }, [message, messageType]);

  // Memoize the showNotification function to maintain stable reference
  const showNotification = useCallback((message, type = 'success') => {
    notifications.show({
      title: type === 'error' ? 'Error' : type === 'success' ? 'Success' : 'Info',
      message,
      color: type === 'error' ? 'red' : type === 'success' ? 'green' : 'blue',
      autoClose: 3000,
    });
  }, []);

  return { showNotification };
}
