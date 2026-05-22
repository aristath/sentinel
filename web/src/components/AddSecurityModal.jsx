import { useState } from 'react';
import { Modal, TextInput, Stack, Button, Group, Text } from '@mantine/core';

export function AddSecurityModal({ opened, onClose, onAdd }) {
  const [symbol, setSymbol] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async () => {
    if (!symbol.trim()) {
      setError('Symbol is required');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await onAdd(symbol.trim().toUpperCase());
      setSymbol('');
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to add security');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setSymbol('');
    setError(null);
    onClose();
  };

  return (
    <Modal opened={opened} onClose={handleClose} title={<Text fw={600} className="add-security-modal__title">Add Security</Text>} className="add-security-modal">
      <Stack gap="md" className="add-security-modal__content">
        <TextInput
          label="Symbol"
          description="Tradernet symbol (e.g., AAPL.US, ASML.EU). Geography and industry are auto-filled by the next metadata sync."
          placeholder="Enter symbol"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          error={error && !symbol.trim() ? 'Symbol is required' : null}
          disabled={isLoading}
          className="add-security-modal__field add-security-modal__field--symbol"
        />

        {error && (
          <Text c="red" size="sm" className="add-security-modal__error">
            {error}
          </Text>
        )}

        <Group justify="flex-end" mt="md" className="add-security-modal__actions">
          <Button variant="subtle" onClick={handleClose} disabled={isLoading} className="add-security-modal__cancel-btn">
            Cancel
          </Button>
          <Button onClick={handleSubmit} loading={isLoading} className="add-security-modal__submit-btn">
            Add Security
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
