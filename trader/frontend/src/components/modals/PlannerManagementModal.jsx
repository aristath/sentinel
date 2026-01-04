import { useState, useEffect } from 'react';
import { Modal, Tabs, Text, Button, TextInput, Textarea, Switch, NumberInput, Slider, Group, Stack, Paper, Alert, Loader, Divider, Tooltip, ActionIcon } from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';
import { useAppStore } from '../../stores/appStore';
import { api } from '../../api/client';
import { useNotifications } from '../../hooks/useNotifications';

const DEFAULT_CONFIG = {
  name: 'default',
  description: '',
  enable_batch_generation: true,
  max_depth: 5,
  max_opportunities_per_category: 5,
  enable_diverse_selection: true,
  diversity_weight: 0.3,
  transaction_cost_fixed: 5.0,
  transaction_cost_percent: 0.001,
  allow_sell: true,
  allow_buy: true,
  min_hold_days: 90,
  sell_cooldown_days: 180,
  max_loss_threshold: -0.20,
  max_sell_percentage: 0.20,
  // Opportunity Calculators
  enable_profit_taking_calc: true,
  enable_averaging_down_calc: true,
  enable_opportunity_buys_calc: true,
  enable_rebalance_sells_calc: true,
  enable_rebalance_buys_calc: true,
  enable_weight_based_calc: true,
  // Portfolio optimizer
  optimizer_blend: 0.5,
  // Pattern Generators
  enable_direct_buy_pattern: true,
  enable_profit_taking_pattern: true,
  enable_rebalance_pattern: true,
  enable_averaging_down_pattern: true,
  enable_single_best_pattern: true,
  enable_multi_sell_pattern: true,
  enable_mixed_strategy_pattern: true,
  enable_opportunity_first_pattern: true,
  enable_deep_rebalance_pattern: true,
  enable_cash_generation_pattern: true,
  enable_cost_optimized_pattern: true,
  enable_adaptive_pattern: true,
  enable_market_regime_pattern: true,
  // Sequence Generators
  enable_combinatorial_generator: true,
  enable_enhanced_combinatorial_generator: true,
  enable_constraint_relaxation_generator: true,
  // Filters
  enable_correlation_aware_filter: true,
  enable_diversity_filter: true,
  enable_eligibility_filter: true,
  enable_recently_traded_filter: true,
};

export function PlannerManagementModal() {
  const { showPlannerManagementModal, closePlannerManagementModal } = useAppStore();
  const { showNotification } = useNotifications();
  const [activeTab, setActiveTab] = useState('general');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [configId, setConfigId] = useState(1);

  useEffect(() => {
    if (showPlannerManagementModal) {
      loadConfig();
    }
  }, [showPlannerManagementModal]);

  const loadConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      // List configs to get the config ID (should be 1)
      const listResponse = await api.fetchPlannerConfigs();
      const configs = listResponse.configs || [];
      if (configs.length > 0) {
        const configId = configs[0].id;
        setConfigId(configId);
        // Fetch the actual config
        const response = await api.fetchPlannerConfig(configId);
        setConfig(response.config || DEFAULT_CONFIG);
      } else {
        // No config exists, use defaults
        setConfig(DEFAULT_CONFIG);
      }
    } catch (error) {
      setError(`Failed to load configuration: ${error.message}`);
      showNotification(`Failed to load configuration: ${error.message}`, 'error');
      // Use defaults on error
      setConfig(DEFAULT_CONFIG);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      await api.updatePlannerConfig(configId, config, 'ui', 'Updated via UI');
      showNotification('Planner configuration saved successfully', 'success');
    } catch (error) {
      const errorMsg = error.message || 'Failed to save configuration';
      setError(errorMsg);
      showNotification(errorMsg, 'error');
    } finally {
      setSaving(false);
    }
  };

  const updateConfig = (field, value) => {
    setConfig({ ...config, [field]: value });
  };

  const getConfigValue = (field, defaultValue) => {
    return config[field] ?? defaultValue;
  };

  return (
    <Modal
      opened={showPlannerManagementModal}
      onClose={closePlannerManagementModal}
      title="Planner Configuration"
      size="xl"
      styles={{ body: { padding: 0 } }}
    >
      {loading ? (
        <Group justify="center" p="xl">
          <Loader />
          <Text c="dimmed">Loading configuration...</Text>
        </Group>
      ) : (
        <>
          {error && (
            <Alert color="red" title="Error" m="md">
              {error}
            </Alert>
          )}

          <Tabs value={activeTab} onChange={setActiveTab}>
            <Tabs.List grow>
              <Tabs.Tab value="general">General</Tabs.Tab>
              <Tabs.Tab value="planner">Planner</Tabs.Tab>
              <Tabs.Tab value="transaction">Costs</Tabs.Tab>
              <Tabs.Tab value="calculators">Calculators</Tabs.Tab>
              <Tabs.Tab value="patterns">Patterns</Tabs.Tab>
              <Tabs.Tab value="generators">Generators</Tabs.Tab>
              <Tabs.Tab value="filters">Filters</Tabs.Tab>
            </Tabs.List>

            {/* General Tab */}
            <Tabs.Panel value="general" p="md">
              <Stack gap="md">
                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Basic Information</Text>
                  <Stack gap="sm">
                    <TextInput
                      label="Name"
                      value={getConfigValue('name', '')}
                      onChange={(e) => updateConfig('name', e.currentTarget.value)}
                      placeholder="e.g., Default Strategy"
                      required
                    />
                    <Textarea
                      label="Description"
                      value={getConfigValue('description', '')}
                      onChange={(e) => updateConfig('description', e.currentTarget.value)}
                      placeholder="Optional description"
                      minRows={2}
                    />
                    <Switch
                      label="Enable Batch Generation"
                      checked={getConfigValue('enable_batch_generation', true)}
                      onChange={(e) => updateConfig('enable_batch_generation', e.currentTarget.checked)}
                      description="Generate sequences in batches for better performance"
                    />
                  </Stack>
                </Paper>

                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Trade Permissions</Text>
                  <Stack gap="sm">
                    <Switch
                      label="Allow Buy Orders"
                      checked={getConfigValue('allow_buy', true)}
                      onChange={(e) => updateConfig('allow_buy', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Allow Sell Orders"
                      checked={getConfigValue('allow_sell', true)}
                      onChange={(e) => updateConfig('allow_sell', e.currentTarget.checked)}
                    />
                  </Stack>
                </Paper>
              </Stack>
            </Tabs.Panel>

            {/* Planner Settings Tab */}
            <Tabs.Panel value="planner" p="md">
              <Stack gap="md">
                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Planner Settings</Text>
                  <Stack gap="md">
                    <Group justify="space-between">
                      <div>
                        <Text size="sm">Max Depth</Text>
                        <Text size="xs" c="dimmed">Maximum sequence depth (1-10)</Text>
                      </div>
                      <NumberInput
                        value={getConfigValue('max_depth', 5)}
                        onChange={(val) => updateConfig('max_depth', val)}
                        min={1}
                        max={10}
                        step={1}
                        w={80}
                        size="sm"
                      />
                    </Group>

                    <Group justify="space-between">
                      <div style={{ flex: 1 }}>
                        <Group gap="xs" mb={4}>
                          <Text size="sm">Max Opportunities Per Category</Text>
                          <Tooltip
                            label="Categories: profit_taking (sell winners), averaging_down (buy more of losers), opportunity_buys (general buys), rebalance_sells (sell overweight), rebalance_buys (buy underweight), weight_based (optimizer targets). This setting limits how many opportunities are kept per category (e.g., max 5 profit-taking, max 5 averaging-down, etc.)"
                            multiline
                            w={300}
                            withArrow
                          >
                            <ActionIcon size="xs" variant="subtle" color="gray">
                              <IconInfoCircle size={16} />
                            </ActionIcon>
                          </Tooltip>
                        </Group>
                        <Text size="xs" c="dimmed">Maximum opportunities per category</Text>
                      </div>
                      <NumberInput
                        value={getConfigValue('max_opportunities_per_category', 5)}
                        onChange={(val) => updateConfig('max_opportunities_per_category', val)}
                        min={1}
                        step={1}
                        w={80}
                        size="sm"
                      />
                    </Group>

                    <Switch
                      label="Enable Diverse Selection"
                      checked={getConfigValue('enable_diverse_selection', true)}
                      onChange={(e) => updateConfig('enable_diverse_selection', e.currentTarget.checked)}
                      description="Select diverse sequences to avoid redundancy"
                    />

                    <div>
                      <Group justify="space-between" mb="xs">
                        <Text size="sm">Diversity Weight</Text>
                        <Text size="sm" fw={500}>
                          {getConfigValue('diversity_weight', 0.3).toFixed(2)}
                        </Text>
                      </Group>
                      <Slider
                        value={getConfigValue('diversity_weight', 0.3)}
                        onChange={(val) => updateConfig('diversity_weight', val)}
                        min={0}
                        max={1}
                        step={0.01}
                        mb="xs"
                      />
                      <Text size="xs" c="dimmed">Weight for diversity in sequence selection (0.0 - 1.0)</Text>
                    </div>
                  </Stack>
                </Paper>

                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Portfolio Optimizer</Text>
                  <Stack gap="md">
                    <div>
                      <Group justify="space-between" mb="xs">
                        <Text size="sm">Strategy Blend</Text>
                        <Text size="sm" fw={500}>
                          {(getConfigValue('optimizer_blend', 0.5) * 100).toFixed(0)}%
                        </Text>
                      </Group>
                      <Group gap="xs" mb="xs">
                        <Text size="xs" c="dimmed">MV</Text>
                        <Slider
                          value={getConfigValue('optimizer_blend', 0.5)}
                          onChange={(val) => updateConfig('optimizer_blend', val)}
                          min={0}
                          max={1}
                          step={0.05}
                          style={{ flex: 1 }}
                        />
                        <Text size="xs" c="dimmed">HRP</Text>
                      </Group>
                      <Text size="xs" c="dimmed">0% = Goal-directed (Mean-Variance), 100% = Robust (HRP)</Text>
                    </div>
                  </Stack>
                </Paper>

                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Risk Management</Text>
                  <Stack gap="md">
                    <Group justify="space-between">
                      <div>
                        <Text size="sm">Min Hold Days</Text>
                        <Text size="xs" c="dimmed">Minimum days a position must be held before selling</Text>
                      </div>
                      <NumberInput
                        value={getConfigValue('min_hold_days', 90)}
                        onChange={(val) => updateConfig('min_hold_days', val)}
                        min={0}
                        max={365}
                        step={1}
                        w={80}
                        size="sm"
                      />
                    </Group>

                    <Group justify="space-between">
                      <div>
                        <Text size="sm">Sell Cooldown Days</Text>
                        <Text size="xs" c="dimmed">Days to wait after selling before buying again</Text>
                      </div>
                      <NumberInput
                        value={getConfigValue('sell_cooldown_days', 180)}
                        onChange={(val) => updateConfig('sell_cooldown_days', val)}
                        min={0}
                        max={365}
                        step={1}
                        w={80}
                        size="sm"
                      />
                    </Group>

                    <div>
                      <Group justify="space-between" mb="xs">
                        <Text size="sm">Max Loss Threshold</Text>
                        <Text size="sm" fw={500}>
                          {(getConfigValue('max_loss_threshold', -0.20) * 100).toFixed(0)}%
                        </Text>
                      </Group>
                      <Slider
                        value={getConfigValue('max_loss_threshold', -0.20)}
                        onChange={(val) => updateConfig('max_loss_threshold', val)}
                        min={-1.0}
                        max={0.0}
                        step={0.01}
                        mb="xs"
                      />
                      <Text size="xs" c="dimmed">Maximum loss threshold before forced selling consideration (-100% to 0%)</Text>
                    </div>

                    <div>
                      <Group justify="space-between" mb="xs">
                        <Text size="sm">Max Sell Percentage</Text>
                        <Text size="sm" fw={500}>
                          {(getConfigValue('max_sell_percentage', 0.20) * 100).toFixed(0)}%
                        </Text>
                      </Group>
                      <Slider
                        value={getConfigValue('max_sell_percentage', 0.20)}
                        onChange={(val) => updateConfig('max_sell_percentage', val)}
                        min={0.01}
                        max={1.0}
                        step={0.01}
                        mb="xs"
                      />
                      <Text size="xs" c="dimmed">Maximum percentage of position allowed to sell per transaction (1% to 100%)</Text>
                    </div>
                  </Stack>
                </Paper>
              </Stack>
            </Tabs.Panel>

            {/* Transaction Costs Tab */}
            <Tabs.Panel value="transaction" p="md">
              <Stack gap="md">
                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Transaction Costs</Text>
                  <Text size="xs" c="dimmed" mb="md">
                    Transaction costs are used to evaluate sequence quality.
                  </Text>
                  <Stack gap="sm">
                    <Group justify="space-between">
                      <div>
                        <Text size="sm">Fixed Cost</Text>
                        <Text size="xs" c="dimmed">Fixed cost per trade</Text>
                      </div>
                      <Group gap="xs">
                        <NumberInput
                          value={getConfigValue('transaction_cost_fixed', 5.0)}
                          onChange={(val) => updateConfig('transaction_cost_fixed', val)}
                          min={0}
                          step={0.5}
                          precision={2}
                          w={100}
                          size="sm"
                        />
                      </Group>
                    </Group>

                    <Group justify="space-between">
                      <div>
                        <Text size="sm">Variable Cost</Text>
                        <Text size="xs" c="dimmed">Percentage of trade value</Text>
                      </div>
                      <Group gap="xs">
                        <NumberInput
                          value={(getConfigValue('transaction_cost_percent', 0.001) * 100).toFixed(3)}
                          onChange={(val) => updateConfig('transaction_cost_percent', (val || 0) / 100)}
                          min={0}
                          step={0.001}
                          precision={3}
                          w={100}
                          size="sm"
                        />
                        <Text size="sm" c="dimmed">%</Text>
                      </Group>
                    </Group>
                  </Stack>
                </Paper>
              </Stack>
            </Tabs.Panel>

            {/* Opportunity Calculators Tab */}
            <Tabs.Panel value="calculators" p="md">
              <Stack gap="md">
                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Opportunity Calculators</Text>
                  <Text size="xs" c="dimmed" mb="md">
                    Enable or disable opportunity calculators that identify trading opportunities.
                  </Text>
                  <Stack gap="sm">
                    <Switch
                      label="Profit Taking Calculator"
                      checked={getConfigValue('enable_profit_taking_calc', true)}
                      onChange={(e) => updateConfig('enable_profit_taking_calc', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Averaging Down Calculator"
                      checked={getConfigValue('enable_averaging_down_calc', true)}
                      onChange={(e) => updateConfig('enable_averaging_down_calc', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Opportunity Buys Calculator"
                      checked={getConfigValue('enable_opportunity_buys_calc', true)}
                      onChange={(e) => updateConfig('enable_opportunity_buys_calc', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Rebalance Sells Calculator"
                      checked={getConfigValue('enable_rebalance_sells_calc', true)}
                      onChange={(e) => updateConfig('enable_rebalance_sells_calc', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Rebalance Buys Calculator"
                      checked={getConfigValue('enable_rebalance_buys_calc', true)}
                      onChange={(e) => updateConfig('enable_rebalance_buys_calc', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Weight Based Calculator"
                      checked={getConfigValue('enable_weight_based_calc', true)}
                      onChange={(e) => updateConfig('enable_weight_based_calc', e.currentTarget.checked)}
                    />
                  </Stack>
                </Paper>
              </Stack>
            </Tabs.Panel>

            {/* Pattern Generators Tab */}
            <Tabs.Panel value="patterns" p="md">
              <Stack gap="md">
                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Pattern Generators</Text>
                  <Text size="xs" c="dimmed" mb="md">
                    Enable or disable pattern generators that create trade action patterns.
                  </Text>
                  <Stack gap="sm">
                    <Switch
                      label="Direct Buy Pattern"
                      checked={getConfigValue('enable_direct_buy_pattern', true)}
                      onChange={(e) => updateConfig('enable_direct_buy_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Profit Taking Pattern"
                      checked={getConfigValue('enable_profit_taking_pattern', true)}
                      onChange={(e) => updateConfig('enable_profit_taking_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Rebalance Pattern"
                      checked={getConfigValue('enable_rebalance_pattern', true)}
                      onChange={(e) => updateConfig('enable_rebalance_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Averaging Down Pattern"
                      checked={getConfigValue('enable_averaging_down_pattern', true)}
                      onChange={(e) => updateConfig('enable_averaging_down_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Single Best Pattern"
                      checked={getConfigValue('enable_single_best_pattern', true)}
                      onChange={(e) => updateConfig('enable_single_best_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Multi Sell Pattern"
                      checked={getConfigValue('enable_multi_sell_pattern', true)}
                      onChange={(e) => updateConfig('enable_multi_sell_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Mixed Strategy Pattern"
                      checked={getConfigValue('enable_mixed_strategy_pattern', true)}
                      onChange={(e) => updateConfig('enable_mixed_strategy_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Opportunity First Pattern"
                      checked={getConfigValue('enable_opportunity_first_pattern', true)}
                      onChange={(e) => updateConfig('enable_opportunity_first_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Deep Rebalance Pattern"
                      checked={getConfigValue('enable_deep_rebalance_pattern', true)}
                      onChange={(e) => updateConfig('enable_deep_rebalance_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Cash Generation Pattern"
                      checked={getConfigValue('enable_cash_generation_pattern', true)}
                      onChange={(e) => updateConfig('enable_cash_generation_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Cost Optimized Pattern"
                      checked={getConfigValue('enable_cost_optimized_pattern', true)}
                      onChange={(e) => updateConfig('enable_cost_optimized_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Adaptive Pattern"
                      checked={getConfigValue('enable_adaptive_pattern', true)}
                      onChange={(e) => updateConfig('enable_adaptive_pattern', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Market Regime Pattern"
                      checked={getConfigValue('enable_market_regime_pattern', true)}
                      onChange={(e) => updateConfig('enable_market_regime_pattern', e.currentTarget.checked)}
                    />
                  </Stack>
                </Paper>
              </Stack>
            </Tabs.Panel>

            {/* Sequence Generators Tab */}
            <Tabs.Panel value="generators" p="md">
              <Stack gap="md">
                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Sequence Generators</Text>
                  <Text size="xs" c="dimmed" mb="md">
                    Enable or disable sequence generators that create action sequences.
                  </Text>
                  <Stack gap="sm">
                    <Switch
                      label="Combinatorial Generator"
                      checked={getConfigValue('enable_combinatorial_generator', true)}
                      onChange={(e) => updateConfig('enable_combinatorial_generator', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Enhanced Combinatorial Generator"
                      checked={getConfigValue('enable_enhanced_combinatorial_generator', true)}
                      onChange={(e) => updateConfig('enable_enhanced_combinatorial_generator', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Constraint Relaxation Generator"
                      checked={getConfigValue('enable_constraint_relaxation_generator', true)}
                      onChange={(e) => updateConfig('enable_constraint_relaxation_generator', e.currentTarget.checked)}
                    />
                  </Stack>
                </Paper>
              </Stack>
            </Tabs.Panel>

            {/* Filters Tab */}
            <Tabs.Panel value="filters" p="md">
              <Stack gap="md">
                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Filters</Text>
                  <Text size="xs" c="dimmed" mb="md">
                    Enable or disable filters that refine generated sequences.
                  </Text>
                  <Stack gap="sm">
                    <Switch
                      label="Correlation Aware Filter"
                      checked={getConfigValue('enable_correlation_aware_filter', true)}
                      onChange={(e) => updateConfig('enable_correlation_aware_filter', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Diversity Filter"
                      checked={getConfigValue('enable_diversity_filter', true)}
                      onChange={(e) => updateConfig('enable_diversity_filter', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Eligibility Filter"
                      checked={getConfigValue('enable_eligibility_filter', true)}
                      onChange={(e) => updateConfig('enable_eligibility_filter', e.currentTarget.checked)}
                    />
                    <Switch
                      label="Recently Traded Filter"
                      checked={getConfigValue('enable_recently_traded_filter', true)}
                      onChange={(e) => updateConfig('enable_recently_traded_filter', e.currentTarget.checked)}
                    />
                  </Stack>
                </Paper>
              </Stack>
            </Tabs.Panel>
          </Tabs>

          <Divider />

          <Group justify="flex-end" p="md">
            <Button
              variant="subtle"
              onClick={closePlannerManagementModal}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={saving || !getConfigValue('name')}
              loading={saving}
            >
              Save Configuration
            </Button>
          </Group>
        </>
      )}
    </Modal>
  );
}
