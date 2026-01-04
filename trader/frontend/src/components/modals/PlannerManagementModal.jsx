import { Modal, Text } from '@mantine/core';
import { useAppStore } from '../../stores/appStore';

export function PlannerManagementModal() {
  const { showPlannerManagementModal, closePlannerManagementModal } = useAppStore();

  return (
    <Modal
      opened={showPlannerManagementModal}
      onClose={closePlannerManagementModal}
      title="Planner Management"
      size="xl"
    >
      <Text c="dimmed">Planner Management modal - to be implemented</Text>
    </Modal>
  );
}

