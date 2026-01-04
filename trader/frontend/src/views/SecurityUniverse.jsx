import { Group, Button, Stack } from '@mantine/core';
import { SecurityTable } from '../components/portfolio/SecurityTable';
import { useAppStore } from '../stores/appStore';

export function SecurityUniverse() {
  const { openPlannerManagementModal } = useAppStore();

  return (
    <Stack gap="md">
      {/* Actions */}
      <Group justify="flex-end" wrap="wrap">
        <Button
          variant="light"
          color="green"
          size="sm"
          onClick={() => openPlannerManagementModal()}
        >
          ⚙️ Configure Planner
        </Button>
      </Group>

      <SecurityTable />
    </Stack>
  );
}
