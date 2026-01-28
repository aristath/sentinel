import { useState } from 'react';
import { Modal, Text, Stack, Button, Group, Alert } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';

export function DeleteSecurityModal({ opened, onClose, onDelete, security }) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!security) return null;

  const hasPosition = security.quantity > 0;
  const positionValue = security.value_eur || 0;

  const handleDelete = async () => {
    setIsLoading(true);
    setError(null);

    try {
      await onDelete(security.symbol, hasPosition);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to delete security');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={<Text fw={600} className="delete-security-modal__title">Delete Security</Text>} className="delete-security-modal">
      <Stack gap="md" className="delete-security-modal__content">
        <Text className="delete-security-modal__message">
          Are you sure you want to remove <strong className="delete-security-modal__symbol">{security.symbol}</strong> from your universe?
        </Text>

        {hasPosition && (
          <Alert icon={<IconAlertTriangle size={16} />} color="red" variant="light" className="delete-security-modal__position-warning">
            <Text size="sm" fw={500} className="delete-security-modal__position-info">
              You have a position of {security.quantity} shares (~EUR {positionValue.toFixed(0)})
            </Text>
            <Text size="sm" mt="xs" className="delete-security-modal__position-note">
              This position will be sold immediately before removing the security.
            </Text>
          </Alert>
        )}

        {error && (
          <Text c="red" size="sm" className="delete-security-modal__error">
            {error}
          </Text>
        )}

        <Group justify="flex-end" mt="md" className="delete-security-modal__actions">
          <Button variant="subtle" onClick={onClose} disabled={isLoading} className="delete-security-modal__cancel-btn">
            Cancel
          </Button>
          <Button color="red" onClick={handleDelete} loading={isLoading} className={`delete-security-modal__confirm-btn ${hasPosition ? 'delete-security-modal__confirm-btn--with-position' : ''}`}>
            {hasPosition ? 'Sell & Delete' : 'Delete'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
