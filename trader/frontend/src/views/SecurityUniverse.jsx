import { Group, Button, Stack } from '@mantine/core';
import { SecurityTable } from '../components/portfolio/SecurityTable';
import { useAppStore } from '../stores/appStore';
import { usePortfolioStore } from '../stores/portfolioStore';
import { useSecuritiesStore } from '../stores/securitiesStore';

export function SecurityUniverse() {
  const { buckets } = usePortfolioStore();
  const { securities } = useSecuritiesStore();
  const {
    openBucketHealthModal,
    openUniverseManagementModal,
    openPlannerManagementModal,
  } = useAppStore();

  const getSecurityCountForBucket = (bucketId) => {
    return securities.filter(s => String(s.bucket_id) === String(bucketId)).length;
  };

  return (
    <Stack gap="md">
      {/* Universe Filter Buttons */}
      <Group justify="space-between" wrap="wrap">
        <Group gap="xs" wrap="wrap">
          {buckets.map((bucket) => (
            <Button
              key={bucket.id}
              onClick={() => openBucketHealthModal(bucket)}
              variant={bucket.type === 'core' ? 'filled' : 'light'}
              color={bucket.type === 'core' ? 'blue' : 'violet'}
              size="sm"
            >
              {bucket.name}
              <span style={{ marginLeft: '8px', opacity: 0.75 }}>
                ({getSecurityCountForBucket(bucket.id)})
              </span>
            </Button>
          ))}
        </Group>
        <Group gap="xs">
          <Button
            variant="light"
            size="sm"
            onClick={() => openUniverseManagementModal()}
          >
            ⚙️ Manage Universes
          </Button>
          <Button
            variant="light"
            color="green"
            size="sm"
            onClick={() => openPlannerManagementModal()}
          >
            ⚙️ Configure Planners
          </Button>
        </Group>
      </Group>

      <SecurityTable />
    </Stack>
  );
}
