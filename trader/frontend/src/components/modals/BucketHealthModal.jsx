import { useState, useEffect } from 'react';
import { Modal, Text, Button, Select, NumberInput, TextInput, Group, Stack, Paper, Badge, Loader } from '@mantine/core';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { api } from '../../api/client';
import { useNotifications } from '../../hooks/useNotifications';

export function BucketHealthModal() {
  const { showBucketHealthModal, selectedBucket, closeBucketHealthModal } = useAppStore();
  const { buckets, fetchBuckets, bucketBalances } = usePortfolioStore();
  const { showNotification } = useNotifications();

  const [transfer, setTransfer] = useState({
    fromBucket: '',
    toBucket: '',
    amount: '',
    currency: 'EUR',
    description: '',
  });
  const [transferring, setTransferring] = useState(false);
  const [balance, setBalance] = useState(null);
  const [loadingBalance, setLoadingBalance] = useState(false);

  useEffect(() => {
    if (showBucketHealthModal && selectedBucket) {
      loadBalance();
    }
  }, [showBucketHealthModal, selectedBucket]);

  const loadBalance = async () => {
    if (!selectedBucket) return;

    setLoadingBalance(true);
    try {
      const data = await api.fetchBucketBalances(selectedBucket.id);
      setBalance(data);
    } catch (error) {
      showNotification(`Failed to load balance: ${error.message}`, 'error');
    } finally {
      setLoadingBalance(false);
    }
  };

  const executeTransfer = async () => {
    if (!transfer.fromBucket || !transfer.toBucket || !transfer.amount) {
      showNotification('Please fill in all transfer fields', 'error');
      return;
    }

    setTransferring(true);
    try {
      await api.transferCash({
        from_bucket_id: transfer.fromBucket,
        to_bucket_id: transfer.toBucket,
        amount: parseFloat(transfer.amount),
        currency: transfer.currency,
        description: transfer.description || undefined,
      });
      showNotification('Cash transfer executed successfully', 'success');
      setTransfer({
        fromBucket: '',
        toBucket: '',
        amount: '',
        currency: 'EUR',
        description: '',
      });
      await loadBalance();
      await fetchBuckets();
    } catch (error) {
      showNotification(`Failed to transfer cash: ${error.message}`, 'error');
    } finally {
      setTransferring(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'green';
      case 'accumulating': return 'yellow';
      case 'hibernating': return 'orange';
      case 'paused': return 'gray';
      case 'retired': return 'red';
      default: return 'gray';
    }
  };

  const cashAmount = balance?.[transfer.currency] || balance?.EUR || 0;

  return (
    <Modal
      opened={showBucketHealthModal}
      onClose={closeBucketHealthModal}
      title={selectedBucket ? `Bucket Health: ${selectedBucket.name}` : 'Bucket Health'}
      size="lg"
    >
      {selectedBucket ? (
        <Stack gap="md">
          {/* Health Metrics */}
          <Group grow>
            <Paper p="md" withBorder>
              <Text size="xs" c="dimmed" mb="xs">Status</Text>
              <Group gap="xs">
                <Badge color={getStatusColor(selectedBucket.status)}>
                  {selectedBucket.status || 'active'}
                </Badge>
              </Group>
            </Paper>

            <Paper p="md" withBorder>
              <Text size="xs" c="dimmed" mb="xs">Cash Balance</Text>
              {loadingBalance ? (
                <Loader size="sm" />
              ) : (
                <Text fw={500}>€{cashAmount.toFixed(2)}</Text>
              )}
            </Paper>

            {selectedBucket.type === 'satellite' && selectedBucket.target_pct && (
              <Paper p="md" withBorder>
                <Text size="xs" c="dimmed" mb="xs">Target Allocation</Text>
                <Text fw={500}>{(selectedBucket.target_pct * 100).toFixed(1)}%</Text>
              </Paper>
            )}

            {selectedBucket.high_water_mark && (
              <Paper p="md" withBorder>
                <Text size="xs" c="dimmed" mb="xs">High Water Mark</Text>
                <Text fw={500}>€{selectedBucket.high_water_mark.toFixed(2)}</Text>
              </Paper>
            )}
          </Group>

          {/* Manual Cash Transfer */}
          <Paper p="md" withBorder>
            <Text size="sm" fw={500} mb="md">Manual Cash Transfer</Text>
            <Stack gap="sm">
              <Select
                label="From Universe"
                placeholder="Select source universe"
                data={buckets.map(b => ({ value: String(b.id), label: b.name }))}
                value={transfer.fromBucket}
                onChange={(val) => setTransfer({ ...transfer, fromBucket: val || '' })}
              />

              <Select
                label="To Universe"
                placeholder="Select destination universe"
                data={buckets.map(b => ({ value: String(b.id), label: b.name }))}
                value={transfer.toBucket}
                onChange={(val) => setTransfer({ ...transfer, toBucket: val || '' })}
              />

              <Group grow>
                <NumberInput
                  label="Amount"
                  placeholder="0.00"
                  value={transfer.amount}
                  onChange={(val) => setTransfer({ ...transfer, amount: val || '' })}
                  min={0}
                  step={0.01}
                  precision={2}
                />

                <Select
                  label="Currency"
                  data={['EUR', 'USD', 'GBP', 'HKD']}
                  value={transfer.currency}
                  onChange={(val) => setTransfer({ ...transfer, currency: val || 'EUR' })}
                />
              </Group>

              <TextInput
                label="Description (optional)"
                placeholder="e.g., 'Rebalancing', 'Jumpstart new satellite'"
                value={transfer.description}
                onChange={(e) => setTransfer({ ...transfer, description: e.currentTarget.value })}
              />

              <Button
                onClick={executeTransfer}
                disabled={!transfer.fromBucket || !transfer.toBucket || !transfer.amount || transferring}
                loading={transferring}
                fullWidth
              >
                {transferring ? 'Transferring...' : 'Execute Transfer'}
              </Button>
            </Stack>
          </Paper>
        </Stack>
      ) : (
        <Text c="dimmed">No bucket selected</Text>
      )}

      <Group justify="flex-end" mt="xl" pt="md" style={{ borderTop: '1px solid var(--mantine-color-default-border)' }}>
        <Button variant="subtle" onClick={closeBucketHealthModal}>
          Close
        </Button>
      </Group>
    </Modal>
  );
}
