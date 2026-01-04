import { Modal, Button, Group, Text } from '@mantine/core';
import { useAppStore } from '../../stores/appStore';

export function SettingsModal() {
  const { showSettingsModal, closeSettingsModal } = useAppStore();

  return (
    <Modal
      opened={showSettingsModal}
      onClose={closeSettingsModal}
      title="Settings"
      size="lg"
    >
      <Text c="dimmed">Settings modal - to be implemented</Text>
    </Modal>
  );
}

