import { Modal, TextInput, Button, Group, Alert, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useAppStore } from '../../stores/appStore';
import { useSecuritiesStore } from '../../stores/securitiesStore';
import { useState } from 'react';
import { api } from '../../api/client';

export function AddSecurityModal() {
  const { showAddSecurityModal, closeAddSecurityModal } = useAppStore();
  const { fetchSecurities } = useSecuritiesStore();
  const [identifier, setIdentifier] = useState('');
  const [loading, setLoading] = useState(false);

  const handleAdd = async () => {
    if (!identifier.trim()) return;

    setLoading(true);
    try {
      await api.addSecurityByIdentifier({ identifier: identifier.trim() });
      await fetchSecurities();
      setIdentifier('');
      closeAddSecurityModal();
      notifications.show({
        title: 'Success',
        message: 'Security added successfully',
        color: 'green',
      });
    } catch (e) {
      console.error('Failed to add security:', e);
      notifications.show({
        title: 'Error',
        message: `Failed to add security: ${e.message}`,
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      opened={showAddSecurityModal}
      onClose={closeAddSecurityModal}
      title="Add Security to Universe"
      size="md"
    >
      <div>
        <TextInput
          label="Identifier"
          placeholder="e.g., AAPL.US or US0378331005"
          value={identifier}
          onChange={(e) => setIdentifier(e.target.value)}
          mb="md"
          required
        />
        <Alert color="blue" variant="light" mb="md">
          <Text size="xs">
            All data will be automatically fetched: name, country, exchange, industry, currency, ISIN, historical data (10 years), and initial score calculation.
          </Text>
        </Alert>
        <Group justify="flex-end">
          <Button variant="subtle" onClick={closeAddSecurityModal}>
            Cancel
          </Button>
          <Button onClick={handleAdd} loading={loading} disabled={!identifier.trim()}>
            Add Security
          </Button>
        </Group>
      </div>
    </Modal>
  );
}

