/**
 * Edit Security Modal Component
 *
 * Modal dialog for editing security properties in the investment universe.
 * Supports field overrides (custom values that override defaults) with reset functionality.
 *
 * Features:
 * - Editable fields: symbol, name, geography, exchange, industry, product type, min lot, allow buy/sell
 * - Override indicators showing which fields have custom values
 * - Reset to default functionality for overridden fields
 * - Field validation and whitelist enforcement
 * - Success/error notifications
 *
 * Used for customizing security metadata and trading permissions.
 */
import { Modal, TextInput, NumberInput, Switch, Button, Group, Stack, Select, ActionIcon, Tooltip, Badge, Collapse, Code } from '@mantine/core';
import { IconRefresh, IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useAppStore } from '../../stores/appStore';
import { useSecuritiesStore } from '../../stores/securitiesStore';
import { useState, useEffect } from 'react';
import { api } from '../../api/client';

/**
 * Edit Security modal component
 *
 * Provides a form to edit security properties with override support.
 *
 * @returns {JSX.Element|null} Edit Security modal dialog or null if no security selected
 */
export function EditSecurityModal() {
  const { showEditSecurityModal, editingSecurity, closeEditSecurityModal } = useAppStore();
  const { fetchSecurities } = useSecuritiesStore();
  const [formData, setFormData] = useState(null);
  const [overrides, setOverrides] = useState({});  // Fields that have custom overrides
  const [loading, setLoading] = useState(false);
  const [resettingField, setResettingField] = useState(null);  // Field currently being reset
  const [showRawData, setShowRawData] = useState(false);  // Control collapse for raw JSON data

  // Load security data and overrides when editing security changes
  useEffect(() => {
    if (editingSecurity) {
      setFormData({ ...editingSecurity });
      // Fetch overrides for this security to show which fields are customized
      api.getSecurityOverrides(editingSecurity.isin)
        .then(setOverrides)
        .catch(err => {
          console.error('Failed to fetch overrides:', err);
          setOverrides({});
        });
    }
  }, [editingSecurity]);

  /**
   * Resets a field to its default value by deleting the override
   *
   * @param {string} field - Field name to reset
   */
  const handleResetField = async (field) => {
    if (!formData?.isin) return;

    setResettingField(field);
    try {
      // Delete the override
      await api.deleteSecurityOverride(formData.isin, field);
      // Refresh overrides list
      const newOverrides = await api.getSecurityOverrides(formData.isin);
      setOverrides(newOverrides);
      // Refresh security data to get default value
      await fetchSecurities();
      notifications.show({
        title: 'Reset',
        message: `${field} reset to default`,
        color: 'blue',
      });
    } catch (e) {
      console.error(`Failed to reset ${field}:`, e);
      notifications.show({
        title: 'Error',
        message: `Failed to reset ${field}: ${e.message}`,
        color: 'red',
      });
    } finally {
      setResettingField(null);
    }
  };

  /**
   * Override indicator component
   *
   * Shows a "Customized" badge and reset button for fields that have overrides.
   *
   * @param {Object} props - Component props
   * @param {string} props.field - Field name to check for override
   * @returns {JSX.Element|null} Override indicator or null if not overridden
   */
  const OverrideIndicator = ({ field }) => {
    const isOverridden = field in overrides;
    if (!isOverridden) return null;

    return (
      <Group gap="xs">
        <Badge size="xs" color="blue" variant="light">Customized</Badge>
        <Tooltip label={`Reset ${field} to default`}>
          <ActionIcon
            size="xs"
            variant="subtle"
            color="gray"
            onClick={() => handleResetField(field)}
            loading={resettingField === field}
          >
            <IconRefresh size={12} />
          </ActionIcon>
        </Tooltip>
      </Group>
    );
  };

  /**
   * Handles saving security changes
   *
   * Only sends whitelisted editable fields to the backend.
   * Filters out undefined/null values but preserves empty strings and false booleans.
   */
  const handleSave = async () => {
    if (!formData || !formData.isin) return;

    setLoading(true);
    try {
      // Only send editable fields that are in the backend whitelist
      // Filter out undefined/null values, but keep empty strings and false booleans
      const updateData = {};
      const editableFields = [
        'symbol',
        'name',
        'geography',
        'fullExchangeName',
        'industry',
        'product_type',
        'min_lot',
        'allow_buy',
        'allow_sell',
      ];

      // Build update payload with only defined fields
      editableFields.forEach(field => {
        if (formData[field] !== undefined && formData[field] !== null) {
          updateData[field] = formData[field];
        }
      });

      // Update security via API
      await api.updateSecurity(formData.isin, updateData);
      // Refresh securities list
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
      className="edit-security-modal"
      opened={showEditSecurityModal}
      onClose={closeEditSecurityModal}
      title="Edit Security"
      size="md"
    >
      <Stack className="edit-security-modal__content" gap="md">
        <TextInput
          className="edit-security-modal__input edit-security-modal__input--symbol"
          label="Symbol (Tradernet)"
          value={formData.symbol || ''}
          onChange={(e) => setFormData({ ...formData, symbol: e.target.value })}
          description="Tradernet ticker symbol (e.g., ASML.NL, RHM.DE)"
        />
        <TextInput
          className="edit-security-modal__input edit-security-modal__input--name"
          label={<Group gap="xs">Name <OverrideIndicator field="name" /></Group>}
          value={formData.name || ''}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
        />
        <TextInput
          className="edit-security-modal__input edit-security-modal__input--isin"
          label="ISIN"
          value={formData.isin || ''}
          disabled
          description="Unique security identifier (cannot be changed)"
        />
        <TextInput
          className="edit-security-modal__input edit-security-modal__input--geography"
          label={<Group gap="xs">Geography <OverrideIndicator field="geography" /></Group>}
          value={formData.geography || ''}
          onChange={(e) => setFormData({ ...formData, geography: e.target.value })}
          placeholder="e.g., EU, US, ASIA (comma-separated for multiple)"
          description="Geographic region(s) where the security operates"
        />
        <TextInput
          className="edit-security-modal__input edit-security-modal__input--exchange"
          label="Exchange"
          value={formData.fullExchangeName || ''}
          onChange={(e) => setFormData({ ...formData, fullExchangeName: e.target.value })}
          placeholder="e.g., NASDAQ, Euronext Amsterdam, XETRA"
          description="Exchange where the security trades"
        />
        <TextInput
          className="edit-security-modal__input edit-security-modal__input--industry"
          label={<Group gap="xs">Industry <OverrideIndicator field="industry" /></Group>}
          value={formData.industry || ''}
          onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
          placeholder="e.g., Technology, Healthcare, Financial Services"
          description="Industry classification"
        />
        <Select
          className="edit-security-modal__select edit-security-modal__select--product-type"
          label={<Group gap="xs">Product Type <OverrideIndicator field="product_type" /></Group>}
          value={formData.product_type || 'UNKNOWN'}
          onChange={(value) => setFormData({ ...formData, product_type: value })}
          data={[
            { value: 'EQUITY', label: 'EQUITY - Individual stocks/shares' },
            { value: 'ETF', label: 'ETF - Exchange Traded Funds' },
            { value: 'MUTUALFUND', label: 'MUTUALFUND - Mutual funds' },
            { value: 'ETC', label: 'ETC - Exchange Traded Commodities' },
            { value: 'CASH', label: 'CASH - Cash positions' },
            { value: 'UNKNOWN', label: 'UNKNOWN - Unknown type' },
          ]}
          description="Product type classification"
        />
        <NumberInput
          className="edit-security-modal__number-input edit-security-modal__number-input--min-lot"
          label={<Group gap="xs">Min Lot Size <OverrideIndicator field="min_lot" /></Group>}
          value={formData.min_lot || 1}
          onChange={(val) => setFormData({ ...formData, min_lot: Number(val) || 1 })}
          min={1}
          step={1}
          description="Minimum shares per trade (e.g., 100 for Japanese securities)"
        />
        <Group gap="md">
          <Switch
            className="edit-security-modal__switch edit-security-modal__switch--allow-buy"
            label={<Group gap="xs">Allow Buy <OverrideIndicator field="allow_buy" /></Group>}
            checked={formData.allow_buy !== false}
            onChange={(e) => setFormData({ ...formData, allow_buy: e.currentTarget.checked })}
          />
        </Group>
        <Group gap="md">
          <Switch
            className="edit-security-modal__switch edit-security-modal__switch--allow-sell"
            label={<Group gap="xs">Allow Sell <OverrideIndicator field="allow_sell" /></Group>}
            checked={formData.allow_sell !== false}
            onChange={(e) => setFormData({ ...formData, allow_sell: e.currentTarget.checked })}
          />
        </Group>

        {/* Raw JSON Data Viewer - Collapsible debugging section */}
        <Stack gap="xs" mt="md" pt="md" style={{ borderTop: '1px solid var(--mantine-color-dark-4)' }}>
          <Group
            gap="xs"
            style={{ cursor: 'pointer' }}
            onClick={() => setShowRawData(!showRawData)}
          >
            {showRawData ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
            <Badge size="sm" variant="outline" color="gray">Debug</Badge>
            <span style={{ fontSize: '0.875rem', color: 'var(--mantine-color-dimmed)' }}>
              Raw JSON Data
            </span>
          </Group>
          <Collapse in={showRawData}>
            <Code
              block
              style={{
                maxHeight: '300px',
                overflow: 'auto',
                fontSize: '0.75rem',
                backgroundColor: 'var(--mantine-color-dark-7)',
              }}
            >
              {formData.data ? JSON.stringify(formData.data, null, 2) : 'No data available'}
            </Code>
          </Collapse>
        </Stack>

        <Group className="edit-security-modal__actions" justify="flex-end">
          <Button className="edit-security-modal__cancel-btn" variant="subtle" onClick={closeEditSecurityModal}>
            Cancel
          </Button>
          <Button className="edit-security-modal__save-btn" onClick={handleSave} loading={loading}>
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
