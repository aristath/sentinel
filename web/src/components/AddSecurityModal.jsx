import { useState } from 'react';
import { Modal, TextInput, TagsInput, Stack, Button, Group, Text } from '@mantine/core';
import { useCategories, getGeographyOptions, getIndustryOptions } from '../hooks/useCategories';

export function AddSecurityModal({ opened, onClose, onAdd }) {
  const [symbol, setSymbol] = useState('');
  const [geography, setGeography] = useState([]);
  const [industry, setIndustry] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const { data: categories } = useCategories();
  const geographyOptions = getGeographyOptions(categories?.geographies || []);
  const industryOptions = getIndustryOptions(categories?.industries || []);

  const handleSubmit = async () => {
    if (!symbol.trim()) {
      setError('Symbol is required');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await onAdd(symbol.trim().toUpperCase(), geography, industry);
      setSymbol('');
      setGeography([]);
      setIndustry([]);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to add security');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setSymbol('');
    setGeography([]);
    setIndustry([]);
    setError(null);
    onClose();
  };

  return (
    <Modal opened={opened} onClose={handleClose} title={<Text fw={600} className="add-security-modal__title">Add Security</Text>} className="add-security-modal">
      <Stack gap="md" className="add-security-modal__content">
        <TextInput
          label="Symbol"
          description="Tradernet symbol (e.g., AAPL.US, ASML.EU)"
          placeholder="Enter symbol"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          error={error && !symbol.trim() ? 'Symbol is required' : null}
          disabled={isLoading}
          className="add-security-modal__field add-security-modal__field--symbol"
        />

        <TagsInput
          label="Geography"
          description="Markets/regions (type to add new)"
          placeholder="Select or type geography"
          data={geographyOptions}
          value={geography}
          onChange={setGeography}
          clearable
          disabled={isLoading}
          className="add-security-modal__field add-security-modal__field--geography"
        />

        <TagsInput
          label="Industry"
          description="Industry sectors (type to add new)"
          placeholder="Select or type industry"
          data={industryOptions}
          value={industry}
          onChange={setIndustry}
          clearable
          disabled={isLoading}
          className="add-security-modal__field add-security-modal__field--industry"
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
