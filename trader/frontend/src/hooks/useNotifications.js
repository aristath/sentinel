import { useEffect } from 'react';
import { notifications } from '@mantine/notifications';
import { useAppStore } from '../stores/appStore';

/**
 * Hook to display notifications from app store messages
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
}

