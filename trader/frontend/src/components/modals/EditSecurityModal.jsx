import { Modal, TextInput, Select, NumberInput, Switch, Button, Group, Stack } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { useSecuritiesStore } from '../../stores/securitiesStore';
import { useState, useEffect } from 'react';
import { api } from '../../api/client';

export function EditSecurityModal() {
  const { showEditSecurityModal, editingSecurity, closeEditSecurityModal } = useAppStore();
  const { buckets } = usePortfolioStore();
  const { fetchSecurities } = useSecuritiesStore();
  const [formData, setFormData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (editingSecurity) {
      setFormData({ ...editingSecurity });
    }
  }, [editingSecurity]);

  const handleSave = async () => {
    if (!formData || !formData.isin) return;

    setLoading(true);
    try {
      await api.updateSecurity(formData.isin, formData);
      await fetchSecurities();
      closeEditSecurityModal();
      notifications.show({
        title: 'Success',
        message: 'Security updated successfully',
        color: 'green',
      });
    } catch (e) {
      console.error('Failed to update security:', e);
      notifications.show({
        title: 'Error',
        message: `Failed to update security: ${e.message}`,
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  if (!formData) return null;

  return (
    <Modal
      opened={showEditSecurityModal}
      onClose={closeEditSecurityModal}
      title="Edit Security"
      size="md"
    >
      <Stack gap="md">
        <TextInput
          label="Symbol (Tradernet)"
          value={formData.symbol || ''}
          onChange={(e) => setFormData({ ...formData, symbol: e.target.value })}
          description="Tradernet ticker symbol (e.g., ASML.NL, RHM.DE)"
        />
        <TextInput
          label="Yahoo Symbol (override)"
          value={formData.yahoo_symbol || ''}
          onChange={(e) => setFormData({ ...formData, yahoo_symbol: e.target.value })}
          placeholder="Leave empty to use convention"
          description="e.g., 1810.HK for Xiaomi, 300750.SZ for CATL"
        />
        <TextInput
          label="Name"
          value={formData.name || ''}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
        />
        <TextInput
          label="ISIN"
          value={formData.isin || ''}
          disabled
          description="Unique security identifier (cannot be changed)"
        />
        <TextInput
          label="Country"
          value={formData.country || ''}
          onChange={(e) => setFormData({ ...formData, country: e.target.value })}
          placeholder="e.g., United States, Netherlands, Germany"
          description="Country where the security is domiciled"
        />
        <TextInput
          label="Exchange"
          value={formData.fullExchangeName || ''}
          onChange={(e) => setFormData({ ...formData, fullExchangeName: e.target.value })}
          placeholder="e.g., NASDAQ, Euronext Amsterdam, XETRA"
          description="Exchange where the security trades"
        />
        <TextInput
          label="Industry"
          value={formData.industry || ''}
          onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
          placeholder="e.g., Technology, Healthcare, Financial Services"
          description="Industry classification"
        />
        <Select
          label="Universe / Bucket"
          data={buckets.map(b => ({ value: b.id, label: b.name }))}
          value={formData.bucket_id || null}
          onChange={(val) => setFormData({ ...formData, bucket_id: val })}
          description="Assign this security to a specific universe/bucket"
        />
        <NumberInput
          label="Min Lot Size"
          value={formData.min_lot || 1}
          onChange={(val) => setFormData({ ...formData, min_lot: Number(val) || 1 })}
          min={1}
          step={1}
          description="Minimum shares per trade (e.g., 100 for Japanese securities)"
        />
        <Switch
          label="Allow Buy"
          checked={formData.allow_buy !== false}
          onChange={(e) => setFormData({ ...formData, allow_buy: e.currentTarget.checked })}
        />
        <Switch
          label="Allow Sell"
          checked={formData.allow_sell !== false}
          onChange={(e) => setFormData({ ...formData, allow_sell: e.currentTarget.checked })}
        />
        <Group justify="flex-end">
          <Button variant="subtle" onClick={closeEditSecurityModal}>
            Cancel
          </Button>
          <Button onClick={handleSave} loading={loading}>
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

