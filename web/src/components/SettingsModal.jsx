import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Modal,
  Stack,
  Text,
  TextInput,
  PasswordInput,
  NumberInput,
  Select,
  Switch,
  Loader,
  Center,
  Tabs,
  Divider,
} from '@mantine/core';
import { IconSettings, IconCoin, IconBrain, IconKey, IconChartDots, IconCloudUpload } from '@tabler/icons-react';
import { getSettings, updateSetting } from '../api/client';

export function SettingsModal({ opened, onClose }) {
  const queryClient = useQueryClient();

  const { data: settings, isLoading, error } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    enabled: opened,
  });

  const updateMutation = useMutation({
    mutationFn: ({ key, value }) => updateSetting(key, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });

  const handleChange = (key, value) => {
    updateMutation.mutate({ key, value });
  };

  return (
    <Modal opened={opened} onClose={onClose} title={<Text fw={600}>Settings</Text>} size="lg">
      {isLoading ? (
        <Center h={200}>
          <Loader />
        </Center>
      ) : error ? (
        <Text c="red">Error loading settings: {error.message}</Text>
      ) : (
        <Tabs defaultValue="trading">
          <Tabs.List>
            <Tabs.Tab value="trading" leftSection={<IconSettings size={16} />}>
              Trading
            </Tabs.Tab>
            <Tabs.Tab value="fees" leftSection={<IconCoin size={16} />}>
              Fees
            </Tabs.Tab>
            <Tabs.Tab value="strategy" leftSection={<IconBrain size={16} />}>
              Strategy
            </Tabs.Tab>
            <Tabs.Tab value="analytics" leftSection={<IconChartDots size={16} />}>
              Advanced Analytics
            </Tabs.Tab>
            <Tabs.Tab value="api" leftSection={<IconKey size={16} />}>
              API
            </Tabs.Tab>
            <Tabs.Tab value="backup" leftSection={<IconCloudUpload size={16} />}>
              Backup
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="trading" pt="md">
            <Stack gap="md">
              <Select
                label="Trading Mode"
                description="Research mode simulates trades without executing"
                value={settings?.trading_mode || 'research'}
                onChange={(value) => handleChange('trading_mode', value)}
                data={[
                  { value: 'research', label: 'Research (Paper Trading)' },
                  { value: 'live', label: 'Live Trading' },
                ]}
              />

              <NumberInput
                label="Max Position %"
                description="Maximum allocation to a single security"
                value={settings?.max_position_pct || 20}
                onChange={(value) => handleChange('max_position_pct', value)}
                min={5}
                max={100}
                suffix="%"
              />

              <NumberInput
                label="Min Position %"
                description="Minimum allocation to maintain a position"
                value={settings?.min_position_pct || 2}
                onChange={(value) => handleChange('min_position_pct', value)}
                min={0.5}
                max={20}
                suffix="%"
              />

              <NumberInput
                label="Target Cash %"
                description="Target cash allocation in portfolio"
                value={settings?.target_cash_pct || 5}
                onChange={(value) => handleChange('target_cash_pct', value)}
                min={0}
                max={50}
                suffix="%"
              />

              <NumberInput
                label="Min Cash Buffer %"
                description="Minimum cash to keep as safety buffer"
                value={(settings?.min_cash_buffer || 0.005) * 100}
                onChange={(value) => handleChange('min_cash_buffer', value / 100)}
                min={0}
                max={10}
                decimalScale={2}
                suffix="%"
              />

              <NumberInput
                label="Min Trade Value"
                description="Minimum trade value in EUR"
                value={settings?.min_trade_value || 100}
                onChange={(value) => handleChange('min_trade_value', value)}
                min={10}
                max={10000}
                prefix="EUR "
              />

              <NumberInput
                label="Trade Cool-Off Period"
                description="Days to wait before opposite action after a trade"
                value={settings?.trade_cooloff_days || 30}
                onChange={(value) => handleChange('trade_cooloff_days', value)}
                min={0}
                max={365}
                suffix=" days"
              />
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="fees" pt="md">
            <Stack gap="md">
              <NumberInput
                label="Fixed Transaction Fee"
                description="Fixed fee per trade"
                value={settings?.transaction_fee_fixed || 2}
                onChange={(value) => handleChange('transaction_fee_fixed', value)}
                min={0}
                max={50}
                decimalScale={2}
                prefix="EUR "
              />

              <NumberInput
                label="Variable Transaction Fee %"
                description="Fee as percentage of trade value"
                value={settings?.transaction_fee_percent || 0.2}
                onChange={(value) => handleChange('transaction_fee_percent', value)}
                min={0}
                max={5}
                decimalScale={2}
                suffix="%"
              />
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="strategy" pt="md">
            <Stack gap="md">
              <NumberInput
                label="Score Lookback Years"
                description="Years of historical data for scoring"
                value={settings?.score_lookback_years || 10}
                onChange={(value) => handleChange('score_lookback_years', value)}
                min={1}
                max={20}
                suffix=" years"
              />

              <NumberInput
                label="Rebalance Threshold %"
                description="Minimum deviation to trigger rebalance"
                value={settings?.rebalance_threshold_pct || 5}
                onChange={(value) => handleChange('rebalance_threshold_pct', value)}
                min={1}
                max={20}
                suffix="%"
              />

              <NumberInput
                label="Diversification Impact %"
                description="Max score adjustment for diversification (0 = disabled)"
                value={settings?.diversification_impact_pct ?? 10}
                onChange={(value) => handleChange('diversification_impact_pct', value)}
                min={0}
                max={50}
                suffix="%"
              />
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="analytics" pt="md">
            <Stack gap="md">
              <Text size="sm" c="dimmed">
                Advanced quantitative finance techniques (all optional)
              </Text>

              <Divider label="Regime Detection" />

              <Switch
                label="Enable Regime Adjustment"
                description="Adjust portfolio weights based on Bull/Bear/Sideways market regimes"
                checked={settings?.use_regime_adjustment || false}
                onChange={(e) => handleChange('use_regime_adjustment', e.currentTarget.checked)}
              />

              {settings?.use_regime_adjustment && (
                <>
                  <NumberInput
                    label="Number of Market States"
                    description="Number of hidden states for regime detection (typically 3)"
                    value={settings?.regime_n_states || 3}
                    onChange={(value) => handleChange('regime_n_states', value)}
                    min={2}
                    max={5}
                  />

                  <NumberInput
                    label="Regime Lookback Days"
                    description="Historical data window for regime training"
                    value={settings?.regime_lookback_days || 504}
                    onChange={(value) => handleChange('regime_lookback_days', value)}
                    min={252}
                    max={2520}
                    suffix=" days"
                  />

                  <NumberInput
                    label="Regime Weight Adjustment %"
                    description="Maximum weight adjustment based on regime"
                    value={(settings?.regime_weight_adjustment || 0.2) * 100}
                    onChange={(value) => handleChange('regime_weight_adjustment', value / 100)}
                    min={0}
                    max={50}
                    suffix="%"
                  />
                </>
              )}

              <Divider label="Correlation & Dependencies" />

              <Switch
                label="Use Cleaned Correlation Matrix"
                description="Apply Random Matrix Theory to filter noise from correlations"
                checked={settings?.use_cleaned_correlation || false}
                onChange={(e) => handleChange('use_cleaned_correlation', e.currentTarget.checked)}
              />

              <Text size="xs" c="dimmed" mt="md">
                Weekly jobs (Sundays 21:00-23:00) automatically update these analytics
              </Text>
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="api" pt="md">
            <Stack gap="md">
              <TextInput
                label="Tradernet API Key"
                description="Your Tradernet public API key"
                value={settings?.tradernet_api_key || ''}
                onChange={(e) => handleChange('tradernet_api_key', e.target.value)}
                placeholder="Enter API key"
              />

              <PasswordInput
                label="Tradernet API Secret"
                description="Your Tradernet private API secret"
                value={settings?.tradernet_api_secret || ''}
                onChange={(e) => handleChange('tradernet_api_secret', e.target.value)}
                placeholder="Enter API secret"
              />

              <TextInput
                label="ML Service Base URL"
                description="Base URL for sentinel-ml (used by monolith orchestration and tooling)"
                value={settings?.ml_service_base_url || 'http://localhost:8001'}
                onChange={(e) => handleChange('ml_service_base_url', e.target.value)}
                placeholder="http://localhost:8001"
              />
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="backup" pt="md">
            <Stack gap="md">
              <Text size="sm" c="dimmed">
                Back up the data folder (database + ML models) to Cloudflare R2
              </Text>

              <TextInput
                label="R2 Account ID"
                description="Your Cloudflare account ID"
                value={settings?.r2_account_id || ''}
                onChange={(e) => handleChange('r2_account_id', e.target.value)}
                placeholder="Enter account ID"
              />

              <TextInput
                label="R2 Access Key"
                description="R2 API token access key"
                value={settings?.r2_access_key || ''}
                onChange={(e) => handleChange('r2_access_key', e.target.value)}
                placeholder="Enter access key"
              />

              <PasswordInput
                label="R2 Secret Key"
                description="R2 API token secret key"
                value={settings?.r2_secret_key || ''}
                onChange={(e) => handleChange('r2_secret_key', e.target.value)}
                placeholder="Enter secret key"
              />

              <TextInput
                label="R2 Bucket Name"
                description="Name of the R2 bucket to store backups"
                value={settings?.r2_bucket_name || ''}
                onChange={(e) => handleChange('r2_bucket_name', e.target.value)}
                placeholder="Enter bucket name"
              />

              <NumberInput
                label="Retention Days"
                description="Automatically delete backups older than this"
                value={settings?.r2_backup_retention_days ?? 30}
                onChange={(value) => handleChange('r2_backup_retention_days', value)}
                min={1}
                max={365}
                suffix=" days"
              />
            </Stack>
          </Tabs.Panel>

          {updateMutation.isError && (
            <Text c="red" size="sm" mt="md">
              Error saving: {updateMutation.error.message}
            </Text>
          )}
        </Tabs>
      )}
    </Modal>
  );
}
