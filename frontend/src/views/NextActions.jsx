import { Group, Button, Stack } from '@mantine/core';
import { NextActionsCard } from '../components/portfolio/NextActionsCard';
import { useAppStore } from '../stores/appStore';

export function NextActions() {
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

      <NextActionsCard />
    </Stack>
  );
}
