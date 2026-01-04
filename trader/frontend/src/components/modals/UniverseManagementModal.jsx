import { useState, useEffect } from 'react';
import { Modal, Text, Button, TextInput, Group, Stack, Paper, Loader, Badge, Alert } from '@mantine/core';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { api } from '../../api/client';
import { useNotifications } from '../../hooks/useNotifications';

export function UniverseManagementModal() {
  const { showUniverseManagementModal, closeUniverseManagementModal } = useAppStore();
  const { buckets, fetchBuckets } = usePortfolioStore();
  const { showNotification } = useNotifications();

  const [newUniverseName, setNewUniverseName] = useState('');
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [retiring, setRetiring] = useState({});

  useEffect(() => {
    if (showUniverseManagementModal) {
      fetchBuckets();
    }
  }, [showUniverseManagementModal, fetchBuckets]);

  const createUniverse = async () => {
    if (!newUniverseName.trim()) return;

    setCreating(true);
    try {
      await api.createBucket({ name: newUniverseName.trim() });
      showNotification('Universe created successfully', 'success');
      setNewUniverseName('');
      await fetchBuckets();
    } catch (error) {
      showNotification(`Failed to create universe: ${error.message}`, 'error');
    } finally {
      setCreating(false);
    }
  };

  const retireUniverse = async (bucketId) => {
    if (!confirm('Are you sure you want to retire this universe? This action cannot be undone.')) {
      return;
    }

    setRetiring({ ...retiring, [bucketId]: true });
    try {
      await api.retireBucket(bucketId);
      showNotification('Universe retired successfully', 'success');
      await fetchBuckets();
    } catch (error) {
      showNotification(`Failed to retire universe: ${error.message}`, 'error');
    } finally {
      setRetiring({ ...retiring, [bucketId]: false });
    }
  };

  return (
    <Modal
      opened={showUniverseManagementModal}
      onClose={closeUniverseManagementModal}
      title="Manage Universes / Buckets"
      size="lg"
    >
      <Stack gap="md">
        {/* Info Banner */}
        <Alert color="blue" title="Info">
          Universes (also called "buckets") allow you to organize securities into separate trading groups.
          Each universe operates independently with its own cash balance and trading strategy.
        </Alert>

        {/* Create New Universe */}
        <Paper p="md" withBorder>
          <Text size="sm" fw={500} mb="md">Create New Universe</Text>
          <Group>
            <TextInput
              placeholder="Enter universe name (e.g., 'Tech Growth', 'Dividend Focus')"
              value={newUniverseName}
              onChange={(e) => setNewUniverseName(e.currentTarget.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  createUniverse();
                }
              }}
              style={{ flex: 1 }}
            />
            <Button
              onClick={createUniverse}
              disabled={!newUniverseName.trim() || creating}
              loading={creating}
            >
              {creating ? 'Creating...' : 'Create'}
            </Button>
          </Group>
        </Paper>

        {/* Existing Universes */}
        <Paper p="md" withBorder>
          <Text size="sm" fw={500} mb="md">Existing Universes</Text>

          {loading ? (
            <Group justify="center" p="xl">
              <Loader />
              <Text c="dimmed">Loading universes...</Text>
            </Group>
          ) : buckets.length === 0 ? (
            <Text c="dimmed" ta="center" p="xl">
              No universes found. The "core" universe will be created automatically.
            </Text>
          ) : (
            <Stack gap="sm">
              {buckets.map((bucket) => (
                <Paper key={bucket.id} p="sm" withBorder>
                  <Group justify="space-between">
                    <div>
                      <Group gap="xs" mb="xs">
                        <Text fw={500}>{bucket.name}</Text>
                        {bucket.type === 'core' && (
                          <Badge color="blue">Core</Badge>
                        )}
                        {bucket.type === 'satellite' && (
                          <Badge color="violet">Satellite</Badge>
                        )}
                      </Group>
                      <Group gap="md">
                        <Text size="xs" c="dimmed">ID: {bucket.id}</Text>
                        <Text size="xs" c="dimmed">Status: {bucket.status || 'active'}</Text>
                      </Group>
                    </div>
                    {bucket.type !== 'core' && (
                      <Button
                        size="xs"
                        color="red"
                        variant="light"
                        onClick={() => retireUniverse(bucket.id)}
                        loading={retiring[bucket.id]}
                      >
                        Retire
                      </Button>
                    )}
                  </Group>
                </Paper>
              ))}
            </Stack>
          )}
        </Paper>
      </Stack>

      <Group justify="flex-end" mt="xl" pt="md" style={{ borderTop: '1px solid var(--mantine-color-default-border)' }}>
        <Button variant="subtle" onClick={closeUniverseManagementModal}>
          Close
        </Button>
      </Group>
    </Modal>
  );
}
