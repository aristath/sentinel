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
import { IconSettings, IconCoin, IconBrain, IconKey, IconChartDots } from '@tabler/icons-react';
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

              <Divider label="Portfolio Optimization" />

              <Select
                label="Optimization Method"
                description="Algorithm for calculating ideal portfolio allocations"
                value={settings?.optimization_method || 'classic'}
                onChange={(value) => handleChange('optimization_method', value)}
                data={[
                  { value: 'classic', label: 'Classic (Wavelet-based)' },
                  { value: 'entropy', label: 'Entropy Optimization' },
                  { value: 'skfolio_mv', label: 'Mean-Variance (skfolio)' },
                  { value: 'skfolio_hrp', label: 'Hierarchical Risk Parity (skfolio)' },
                  { value: 'skfolio_rp', label: 'Risk Parity (skfolio)' },
                ]}
              />

              {settings?.optimization_method === 'entropy' && (
                <>
                  <Select
                    label="Entropy Method"
                    description="Type of entropy calculation to use"
                    value={settings?.entropy_method || 'shannon'}
                    onChange={(value) => handleChange('entropy_method', value)}
                    data={[
                      { value: 'shannon', label: 'Shannon Entropy' },
                      { value: 'tsallis', label: 'Tsallis Entropy' },
                    ]}
                  />

                  <NumberInput
                    label="Entropy Weight"
                    description="Balance between returns and diversification (0-1)"
                    value={settings?.entropy_weight || 0.3}
                    onChange={(value) => handleChange('entropy_weight', value)}
                    min={0}
                    max={1}
                    step={0.1}
                    decimalScale={2}
                  />

                  {settings?.entropy_method === 'tsallis' && (
                    <NumberInput
                      label="Tsallis Q Parameter"
                      description="Non-extensivity parameter for Tsallis entropy"
                      value={settings?.tsallis_q || 2.0}
                      onChange={(value) => handleChange('tsallis_q', value)}
                      min={0.5}
                      max={3}
                      step={0.1}
                      decimalScale={1}
                    />
                  )}
                </>
              )}

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

              <Switch
                label="Enable Transfer Entropy Analysis"
                description="Identify directional dependencies between securities"
                checked={settings?.use_transfer_entropy || false}
                onChange={(e) => handleChange('use_transfer_entropy', e.currentTarget.checked)}
              />

              {settings?.use_transfer_entropy && (
                <>
                  <NumberInput
                    label="Transfer Entropy Lag"
                    description="Time lag for causality detection"
                    value={settings?.te_lag || 5}
                    onChange={(value) => handleChange('te_lag', value)}
                    min={1}
                    max={20}
                    suffix=" days"
                  />

                  <NumberInput
                    label="Transfer Entropy Bins"
                    description="Discretization bins for entropy calculation"
                    value={settings?.te_bins || 10}
                    onChange={(value) => handleChange('te_bins', value)}
                    min={5}
                    max={20}
                  />

                  <NumberInput
                    label="Influence Threshold"
                    description="Minimum transfer entropy to consider as influence"
                    value={settings?.te_influence_threshold || 0.1}
                    onChange={(value) => handleChange('te_influence_threshold', value)}
                    min={0}
                    max={1}
                    step={0.05}
                    decimalScale={2}
                  />
                </>
              )}

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
