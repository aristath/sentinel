import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Modal,
  Stack,
  Text,
  TextInput,
  PasswordInput,
  NumberInput,
  Select,
  Loader,
  Center,
  Tabs,
  Group,
  Button,
} from '@mantine/core';
import { IconSettings, IconCoin, IconBrain, IconKey, IconCloudUpload } from '@tabler/icons-react';
import { getSettings, updateSetting, updateSettingsBatch } from '../api/client';

export function SettingsModal({ opened, onClose }) {
  const queryClient = useQueryClient();
  const [strategyDraft, setStrategyDraft] = useState(null);

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

  const strategyMutation = useMutation({
    mutationFn: (values) => updateSettingsBatch(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });

  useEffect(() => {
    if (!settings) return;
    setStrategyDraft({
      strategy_core_target_pct: Number(settings.strategy_core_target_pct ?? 80),
      strategy_opportunity_target_pct: Number(settings.strategy_opportunity_target_pct ?? 20),
      strategy_opportunity_target_max_pct: Number(settings.strategy_opportunity_target_max_pct ?? 30),
      strategy_min_opp_score: Number(settings.strategy_min_opp_score ?? 0.55),
      strategy_core_floor_pct: Number(settings.strategy_core_floor_pct ?? 0.05),
      strategy_entry_t1_dd: Number(settings.strategy_entry_t1_dd ?? -0.10),
      strategy_entry_t2_dd: Number(settings.strategy_entry_t2_dd ?? -0.16),
      strategy_entry_t3_dd: Number(settings.strategy_entry_t3_dd ?? -0.22),
      strategy_entry_memory_days: Number(settings.strategy_entry_memory_days ?? 45),
      strategy_memory_max_boost: Number(settings.strategy_memory_max_boost ?? 0.12),
      strategy_opportunity_addon_threshold: Number(settings.strategy_opportunity_addon_threshold ?? 0.75),
      strategy_max_opportunity_buys_per_cycle: Number(settings.strategy_max_opportunity_buys_per_cycle ?? 1),
      strategy_max_new_opportunity_buys_per_cycle: Number(settings.strategy_max_new_opportunity_buys_per_cycle ?? 1),
    });
  }, [settings]);

  const handleStrategyChange = (key, value) => {
    if (value == null || Number.isNaN(value)) return;
    setStrategyDraft((prev) => ({ ...(prev || {}), [key]: Number(value) }));
  };

  const applyStrategyTuning = () => {
    if (!strategyDraft) return;
    strategyMutation.mutate(strategyDraft);
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
                label="Core Target %"
                description="Baseline allocation sleeve for core holdings"
                value={strategyDraft?.strategy_core_target_pct ?? settings?.strategy_core_target_pct ?? 80}
                onChange={(value) => handleStrategyChange('strategy_core_target_pct', value)}
                min={0}
                max={100}
                suffix="%"
              />

              <NumberInput
                label="Opportunity Target %"
                description="Tactical sleeve for high-opportunity names"
                value={strategyDraft?.strategy_opportunity_target_pct ?? settings?.strategy_opportunity_target_pct ?? 20}
                onChange={(value) => handleStrategyChange('strategy_opportunity_target_pct', value)}
                min={0}
                max={100}
                suffix="%"
              />

              <NumberInput
                label="Opportunity Target Max %"
                description="Dynamic cap for opportunity sleeve during broad/strong dip regimes"
                value={strategyDraft?.strategy_opportunity_target_max_pct ?? settings?.strategy_opportunity_target_max_pct ?? 30}
                onChange={(value) => handleStrategyChange('strategy_opportunity_target_max_pct', value)}
                min={0}
                max={100}
                suffix="%"
              />

              <NumberInput
                label="Minimum Opportunity Score"
                description="Minimum opp score required to enter opportunity sleeve"
                value={strategyDraft?.strategy_min_opp_score ?? settings?.strategy_min_opp_score ?? 0.55}
                onChange={(value) => handleStrategyChange('strategy_min_opp_score', value)}
                min={0}
                max={1}
                decimalScale={3}
              />

              <NumberInput
                label="Core Floor %"
                description="Minimum total portfolio share kept for core positions before trimming"
                value={(strategyDraft?.strategy_core_floor_pct ?? settings?.strategy_core_floor_pct ?? 0.05) * 100}
                onChange={(value) => handleStrategyChange('strategy_core_floor_pct', (value ?? 0) / 100)}
                min={0}
                max={100}
                decimalScale={2}
                suffix="%"
              />

              <NumberInput
                label="Entry T1 Drawdown"
                description="First opportunity tranche threshold (dd252)"
                value={strategyDraft?.strategy_entry_t1_dd ?? settings?.strategy_entry_t1_dd ?? -0.10}
                onChange={(value) => handleStrategyChange('strategy_entry_t1_dd', value)}
                min={-0.9}
                max={0}
                decimalScale={3}
              />

              <NumberInput
                label="Entry T2 Drawdown"
                description="Second opportunity tranche threshold (dd252)"
                value={strategyDraft?.strategy_entry_t2_dd ?? settings?.strategy_entry_t2_dd ?? -0.16}
                onChange={(value) => handleStrategyChange('strategy_entry_t2_dd', value)}
                min={-0.9}
                max={0}
                decimalScale={3}
              />

              <NumberInput
                label="Entry T3 Drawdown"
                description="Third opportunity tranche threshold (dd252)"
                value={strategyDraft?.strategy_entry_t3_dd ?? settings?.strategy_entry_t3_dd ?? -0.22}
                onChange={(value) => handleStrategyChange('strategy_entry_t3_dd', value)}
                min={-0.9}
                max={0}
                decimalScale={3}
              />

              <NumberInput
                label="Entry Memory Days"
                description="Keep recent-dip memory active for post-turn entries"
                value={strategyDraft?.strategy_entry_memory_days ?? settings?.strategy_entry_memory_days ?? 45}
                onChange={(value) => handleStrategyChange('strategy_entry_memory_days', value)}
                min={1}
                max={252}
                suffix=" days"
              />

              <NumberInput
                label="Memory Max Boost"
                description="Maximum boost added to opp score from recent dip memory"
                value={strategyDraft?.strategy_memory_max_boost ?? settings?.strategy_memory_max_boost ?? 0.12}
                onChange={(value) => handleStrategyChange('strategy_memory_max_boost', value)}
                min={0}
                max={0.5}
                decimalScale={3}
              />

              <NumberInput
                label="Opportunity Add-On Threshold"
                description="Allow add-on buys for already-held opportunity names above this score"
                value={strategyDraft?.strategy_opportunity_addon_threshold ?? settings?.strategy_opportunity_addon_threshold ?? 0.75}
                onChange={(value) => handleStrategyChange('strategy_opportunity_addon_threshold', value)}
                min={0}
                max={1}
                decimalScale={3}
              />

              <NumberInput
                label="Max Opportunity Buys / Cycle"
                description="Hard cap on total opportunity buys per rebalance cycle"
                value={strategyDraft?.strategy_max_opportunity_buys_per_cycle ?? settings?.strategy_max_opportunity_buys_per_cycle ?? 1}
                onChange={(value) => handleStrategyChange('strategy_max_opportunity_buys_per_cycle', value)}
                min={0}
                max={50}
              />

              <NumberInput
                label="Max New Opportunity Buys / Cycle"
                description="Hard cap on opening new opportunity positions per cycle"
                value={strategyDraft?.strategy_max_new_opportunity_buys_per_cycle ?? settings?.strategy_max_new_opportunity_buys_per_cycle ?? 1}
                onChange={(value) => handleStrategyChange('strategy_max_new_opportunity_buys_per_cycle', value)}
                min={0}
                max={50}
              />

              <Group justify="flex-end">
                <Button onClick={applyStrategyTuning} loading={strategyMutation.isPending}>
                  Apply Strategy Tuning
                </Button>
              </Group>

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

              <NumberInput
                label="Standard Lot Max %"
                description="Max ticket size treated as standard lot class"
                value={(settings?.strategy_lot_standard_max_pct ?? 0.08) * 100}
                onChange={(value) => handleChange('strategy_lot_standard_max_pct', (value ?? 0) / 100)}
                min={0}
                max={100}
                decimalScale={2}
                suffix="%"
              />

              <NumberInput
                label="Coarse Lot Max %"
                description="Max ticket size treated as coarse lot class"
                value={(settings?.strategy_lot_coarse_max_pct ?? 0.30) * 100}
                onChange={(value) => handleChange('strategy_lot_coarse_max_pct', (value ?? 0) / 100)}
                min={0}
                max={100}
                decimalScale={2}
                suffix="%"
              />

              <NumberInput
                label="Coarse Max New Lots"
                description="Max new coarse lots per rebalance cycle (unless opp score is very strong)"
                value={settings?.strategy_coarse_max_new_lots_per_cycle ?? 1}
                onChange={(value) => handleChange('strategy_coarse_max_new_lots_per_cycle', value)}
                min={1}
                max={10}
              />

              <NumberInput
                label="Opportunity Cool-Off Days"
                description="Minimum days between opposite actions for opportunity sleeve"
                value={settings?.strategy_opportunity_cooloff_days ?? 7}
                onChange={(value) => handleChange('strategy_opportunity_cooloff_days', value)}
                min={0}
                max={365}
              />

              <NumberInput
                label="Core Cool-Off Days"
                description="Minimum days between opposite actions for core sleeve"
                value={settings?.strategy_core_cooloff_days ?? 21}
                onChange={(value) => handleChange('strategy_core_cooloff_days', value)}
                min={0}
                max={365}
              />

              <NumberInput
                label="Rotation Time-Stop Days"
                description="Exit opportunity positions if thesis stalls beyond this horizon"
                value={settings?.strategy_rotation_time_stop_days ?? 90}
                onChange={(value) => handleChange('strategy_rotation_time_stop_days', value)}
                min={1}
                max={365}
              />
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

          <Tabs.Panel value="backup" pt="md">
            <Stack gap="md">
              <Text size="sm" c="dimmed">
                Back up the data folder (database and runtime state) to Cloudflare R2
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
          {strategyMutation.isError && (
            <Text c="red" size="sm" mt="md">
              Error saving strategy tuning: {strategyMutation.error.message}
            </Text>
          )}
        </Tabs>
      )}
    </Modal>
  );
}
