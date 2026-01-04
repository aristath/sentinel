import { Modal, Text } from '@mantine/core';
import { useAppStore } from '../../stores/appStore';

export function UniverseManagementModal() {
  const { showUniverseManagementModal, closeUniverseManagementModal } = useAppStore();

  return (
    <Modal
      opened={showUniverseManagementModal}
      onClose={closeUniverseManagementModal}
      title="Universe Management"
      size="lg"
    >
      <Text c="dimmed">Universe Management modal - to be implemented</Text>
    </Modal>
  );
}

