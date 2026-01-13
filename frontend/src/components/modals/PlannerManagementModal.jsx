import { useState, useEffect, useCallback } from 'react';
import { Modal, Tabs, Text, Button, TextInput, Textarea, Switch, NumberInput, Slider, Group, Stack, Paper, Alert, Loader, Divider, Tooltip, ActionIcon } from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';
import { useAppStore } from '../../stores/appStore';
import { api } from '../../api/client';
import { useNotifications } from '../../hooks/useNotifications';

const DEFAULT_CONFIG = {
  enable_batch_generation: true,
  enable_diverse_selection: true,
  diversity_weight: 0.3,
  transaction_cost_fixed: 5.0,
  transaction_cost_percent: 0.001,
  allow_sell: true,
  allow_buy: true,
  // Portfolio optimizer
  optimizer_target_return: 0.11,
  min_cash_reserve: 500.0,
  // Opportunity Calculators
  enable_profit_taking_calc: true,
  enable_averaging_down_calc: true,
  enable_opportunity_buys_calc: true,
  enable_rebalance_sells_calc: true,
  enable_rebalance_buys_calc: true,
  enable_weight_based_calc: true,
  // Portfolio optimizer
  optimizer_blend: 0.5,
  // Post-generation Filters (eligibility & recently_traded are now handled during generation)
  enable_correlation_aware_filter: true,
  enable_diversity_filter: true,
  // Tag filtering
  enable_tag_filtering: true,
};

// Default temperament settings (stored in global settings, not planner config)
const DEFAULT_TEMPERAMENT = {
  risk_tolerance: 0.5,       // Conservative (0) to Risk-Taking (1)
  temperament_aggression: 0.5, // Passive (0) to Aggressive (1)
  temperament_patience: 0.5,   // Impatient (0) to Patient (1)
};

export function PlannerManagementModal() {
  const { showPlannerManagementModal, closePlannerManagementModal } = useAppStore();
  const { showNotification } = useNotifications();
  const [activeTab, setActiveTab] = useState('temperament');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [temperament, setTemperament] = useState(DEFAULT_TEMPERAMENT);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch planner config and temperament settings in parallel
      const [plannerResponse, settingsResponse] = await Promise.all([
        api.fetchPlannerConfig(),
        api.fetchSettings(),
      ]);
      setConfig(plannerResponse.config || DEFAULT_CONFIG);

      // Extract temperament settings from global settings
      const settings = settingsResponse.settings || {};
      setTemperament({
        risk_tolerance: settings.risk_tolerance ?? 0.5,
        temperament_aggression: settings.temperament_aggression ?? 0.5,
        temperament_patience: settings.temperament_patience ?? 0.5,
      });
    } catch (error) {
      setError(`Failed to load configuration: ${error.message}`);
      showNotification(`Failed to load configuration: ${error.message}`, 'error');
      // Use defaults on error
      setConfig(DEFAULT_CONFIG);
      setTemperament(DEFAULT_TEMPERAMENT);
    } finally {
      setLoading(false);
    }
  }, [showNotification]);

  useEffect(() => {
    if (showPlannerManagementModal) {
      loadConfig();
    }
  }, [showPlannerManagementModal, loadConfig]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      // Save planner config and temperament settings
      await Promise.all([
        api.updatePlannerConfig(config, 'ui', 'Updated via UI'),
        api.updateSetting('risk_tolerance', temperament.risk_tolerance),
        api.updateSetting('temperament_aggression', temperament.temperament_aggression),
        api.updateSetting('temperament_patience', temperament.temperament_patience),
      ]);
      showNotification('Configuration saved successfully', 'success');
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

  const updateTemperament = (field, value) => {
    setTemperament({ ...temperament, [field]: value });
  };

  const getConfigValue = (field, defaultValue) => {
    return config[field] ?? defaultValue;
  };

  const getTemperamentValue = (field, defaultValue) => {
    return temperament[field] ?? defaultValue;
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
              <Tabs.Tab value="temperament">Temperament</Tabs.Tab>
              <Tabs.Tab value="general">General</Tabs.Tab>
              <Tabs.Tab value="planner">Planner</Tabs.Tab>
              <Tabs.Tab value="transaction">Costs</Tabs.Tab>
              <Tabs.Tab value="calculators">Calculators</Tabs.Tab>
              <Tabs.Tab value="filters">Filters</Tabs.Tab>
            </Tabs.List>

            {/* Temperament Tab */}
            <Tabs.Panel value="temperament" p="md">
              <Stack gap="md">
                <Alert color="blue" title="Investment Temperament" icon={<IconInfoCircle />}>
                  These three sliders control 150+ parameters across the system, defining how the planner behaves.
                  Move sliders to adjust your investment philosophy. Changes affect evaluation weights, thresholds,
                  hold periods, position sizing, and more.
                </Alert>

                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="md" tt="uppercase">Risk Tolerance</Text>
                  <Text size="xs" c="dimmed" mb="md">
                    Controls volatility acceptance, drawdown tolerance, position concentration, and quality floors.
                    Conservative investors prefer stable, high-quality positions while risk-takers accept more volatility for higher returns.
                  </Text>
                  <div>
                    <Group justify="space-between" mb="xs">
                      <Text size="sm">Conservative</Text>
                      <Text size="sm" fw={500}>
                        {(getTemperamentValue('risk_tolerance', 0.5) * 100).toFixed(0)}%
                      </Text>
                      <Text size="sm">Risk-Taking</Text>
                    </Group>
                    <Slider
                      value={getTemperamentValue('risk_tolerance', 0.5)}
                      onChange={(val) => updateTemperament('risk_tolerance', val)}
                      min={0}
                      max={1}
                      step={0.01}
                      marks={[
                        { value: 0, label: '0' },
                        { value: 0.25, label: '25' },
                        { value: 0.5, label: '50' },
                        { value: 0.75, label: '75' },
                        { value: 1, label: '100' },
                      ]}
                      mb="xl"
                    />
                  </div>
                </Paper>

                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="md" tt="uppercase">Aggression</Text>
                  <Text size="xs" c="dimmed" mb="md">
                    Controls scoring thresholds, action frequency, evaluation weights, position sizing, and opportunity pursuit.
                    Passive investors wait for clear opportunities while aggressive investors act more readily on signals.
                  </Text>
                  <div>
                    <Group justify="space-between" mb="xs">
                      <Text size="sm">Passive</Text>
                      <Text size="sm" fw={500}>
                        {(getTemperamentValue('temperament_aggression', 0.5) * 100).toFixed(0)}%
                      </Text>
                      <Text size="sm">Aggressive</Text>
                    </Group>
                    <Slider
                      value={getTemperamentValue('temperament_aggression', 0.5)}
                      onChange={(val) => updateTemperament('temperament_aggression', val)}
                      min={0}
                      max={1}
                      step={0.01}
                      marks={[
                        { value: 0, label: '0' },
                        { value: 0.25, label: '25' },
                        { value: 0.5, label: '50' },
                        { value: 0.75, label: '75' },
                        { value: 1, label: '100' },
                      ]}
                      mb="xl"
                    />
                  </div>
                </Paper>

                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="md" tt="uppercase">Patience</Text>
                  <Text size="xs" c="dimmed" mb="md">
                    Controls hold periods, cooldowns, windfall thresholds, rebalance triggers, and dividend focus.
                    Impatient investors seek quick wins while patient investors let positions mature.
                  </Text>
                  <div>
                    <Group justify="space-between" mb="xs">
                      <Text size="sm">Impatient</Text>
                      <Text size="sm" fw={500}>
                        {(getTemperamentValue('temperament_patience', 0.5) * 100).toFixed(0)}%
                      </Text>
                      <Text size="sm">Patient</Text>
                    </Group>
                    <Slider
                      value={getTemperamentValue('temperament_patience', 0.5)}
                      onChange={(val) => updateTemperament('temperament_patience', val)}
                      min={0}
                      max={1}
                      step={0.01}
                      marks={[
                        { value: 0, label: '0' },
                        { value: 0.25, label: '25' },
                        { value: 0.5, label: '50' },
                        { value: 0.75, label: '75' },
                        { value: 1, label: '100' },
                      ]}
                      mb="xl"
                    />
                  </div>
                </Paper>
              </Stack>
            </Tabs.Panel>

            {/* General Tab */}
            <Tabs.Panel value="general" p="md">
              <Stack gap="md">
                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Batch Processing</Text>
                  <Stack gap="sm">
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
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Sequence Selection</Text>
                  <Stack gap="md">
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
                    <Group justify="space-between">
                      <div>
                        <Text size="sm">Target Return</Text>
                        <Text size="xs" c="dimmed">Annual return goal for optimizer</Text>
                      </div>
                      <Group gap="xs">
                        <NumberInput
                          value={(getConfigValue('optimizer_target_return', 0.11) * 100).toFixed(0)}
                          onChange={(val) => updateConfig('optimizer_target_return', (val || 0) / 100)}
                          min={0}
                          step={1}
                          w={80}
                          size="sm"
                        />
                        <Text size="sm" c="dimmed">%</Text>
                      </Group>
                    </Group>

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
                          onChange={() => {}} // Read-only: algorithm-controlled
                          min={0}
                          max={1}
                          step={0.05}
                          style={{ flex: 1 }}
                          disabled
                        />
                        <Text size="xs" c="dimmed">HRP</Text>
                      </Group>
                      <Text size="xs" c="dimmed">
                        Algorithm-controlled based on market regime. 0% = Goal-directed (Mean-Variance), 100% = Robust (HRP)
                      </Text>
                    </div>

                    <Group justify="space-between">
                      <div>
                        <Text size="sm">Min Cash Reserve</Text>
                        <Text size="xs" c="dimmed">Never deploy below this amount</Text>
                      </div>
                      <Group gap="xs">
                        <Text size="sm" c="dimmed">EUR</Text>
                        <NumberInput
                          value={getConfigValue('min_cash_reserve', 500)}
                          onChange={(val) => updateConfig('min_cash_reserve', val)}
                          min={0}
                          step={50}
                          w={100}
                          size="sm"
                        />
                      </Group>
                    </Group>
                  </Stack>
                </Paper>

                <Alert color="gray" variant="light">
                  <Text size="xs">
                    Risk management settings (hold periods, cooldowns, loss thresholds, sell percentages)
                    are now controlled by the Temperament sliders. Adjust the Patience and Risk Tolerance
                    sliders to change these behaviors.
                  </Text>
                </Alert>
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

            {/* Filters Tab */}
            <Tabs.Panel value="filters" p="md">
              <Stack gap="md">
                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="xs" tt="uppercase">Post-Generation Filters</Text>
                  <Text size="xs" c="dimmed" mb="md">
                    Filters that refine generated sequences after generation.
                    Eligibility and cooloff checks are now performed during generation for early pruning.
                  </Text>
                  <Stack gap="sm">
                    <Switch
                      label="Correlation Aware Filter"
                      checked={getConfigValue('enable_correlation_aware_filter', true)}
                      onChange={(e) => updateConfig('enable_correlation_aware_filter', e.currentTarget.checked)}
                      description="Filters sequences with highly correlated actions"
                    />
                    <Switch
                      label="Diversity Filter"
                      checked={getConfigValue('enable_diversity_filter', true)}
                      onChange={(e) => updateConfig('enable_diversity_filter', e.currentTarget.checked)}
                      description="Ensures sequences include diverse actions"
                    />
                    <Divider my="sm" />
                    <Switch
                      label="Tag-Based Filtering"
                      checked={getConfigValue('enable_tag_filtering', true)}
                      onChange={(e) => updateConfig('enable_tag_filtering', e.currentTarget.checked)}
                      description="Enable tag-based pre-filtering for opportunity identification. When disabled, all active securities are considered (uses score-based quality checks instead)."
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
              disabled={saving}
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
