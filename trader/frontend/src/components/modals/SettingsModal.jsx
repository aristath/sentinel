import { useState, useEffect } from 'react';
import { Modal, Tabs, Text, Button, NumberInput, Switch, Slider, Group, Stack, Paper, Divider, Alert } from '@mantine/core';
import { useAppStore } from '../../stores/appStore';
import { useSettingsStore } from '../../stores/settingsStore';
import { api } from '../../api/client';
import { useNotifications } from '../../hooks/useNotifications';
import { GroupingManager } from '../portfolio/GroupingManager';

export function SettingsModal() {
  const { showSettingsModal, closeSettingsModal } = useAppStore();
  const { settings, fetchSettings, updateSetting } = useSettingsStore();
  const { showNotification } = useNotifications();
  const [activeTab, setActiveTab] = useState('trading');
  const [loading, setLoading] = useState(false);
  const [syncingHistorical, setSyncingHistorical] = useState(false);

  useEffect(() => {
    if (showSettingsModal) {
      fetchSettings();
    }
  }, [showSettingsModal, fetchSettings]);

  const handleUpdateSetting = async (key, value) => {
    try {
      await updateSetting(key, value);
      showNotification('Setting updated', 'success');
    } catch (error) {
      showNotification(`Failed to update setting: ${error.message}`, 'error');
    }
  };

  const handleSyncHistorical = async () => {
    setSyncingHistorical(true);
    try {
      await api.syncHistorical();
      showNotification('Historical data sync started', 'success');
    } catch (error) {
      showNotification(`Failed to sync historical data: ${error.message}`, 'error');
    } finally {
      setSyncingHistorical(false);
    }
  };

  const handleResetCache = async () => {
    setLoading(true);
    try {
      await api.resetCache();
      showNotification('Cache reset successfully', 'success');
    } catch (error) {
      showNotification(`Failed to reset cache: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleRestartSystem = async () => {
    if (!confirm('Are you sure you want to restart the system?')) return;
    setLoading(true);
    try {
      await api.restartSystem();
      showNotification('System restart initiated', 'success');
    } catch (error) {
      showNotification(`Failed to restart system: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const getSetting = (key, defaultValue = 0) => {
    return settings[key] ?? defaultValue;
  };

  const minTradeWorthwhile = () => {
    const fixed = getSetting('transaction_cost_fixed', 2.0);
    const percent = getSetting('transaction_cost_percent', 0.002);
    return fixed / (0.01 - percent);
  };

  return (
    <Modal
      opened={showSettingsModal}
      onClose={closeSettingsModal}
      title="Settings"
      size="xl"
      styles={{ body: { padding: 0 } }}
    >
      <Tabs value={activeTab} onTabChange={setActiveTab}>
        <Tabs.List grow>
          <Tabs.Tab value="trading">Trading</Tabs.Tab>
          <Tabs.Tab value="portfolio">Portfolio</Tabs.Tab>
          <Tabs.Tab value="display">Display</Tabs.Tab>
          <Tabs.Tab value="system">System</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="trading" p="md">
          <Stack gap="md">
            {/* Trade Frequency Limits */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">Trade Frequency Limits</Text>
              <Text size="xs" c="dimmed" mb="md">
                Prevent excessive trading by enforcing minimum time between trades and daily/weekly limits.
              </Text>
              <Stack gap="sm">
                <Switch
                  label="Enable frequency limits"
                  checked={getSetting('trade_frequency_limits_enabled', 1) === 1}
                  onChange={(e) => handleUpdateSetting('trade_frequency_limits_enabled', e.currentTarget.checked ? 1 : 0)}
                />
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Min Time Between Trades</Text>
                    <Text size="xs" c="dimmed">Minimum minutes between any trades</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={getSetting('min_time_between_trades_minutes', 60)}
                      onChange={(val) => handleUpdateSetting('min_time_between_trades_minutes', val)}
                      min={0}
                      step={5}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">min</Text>
                  </Group>
                </Group>
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Max Trades Per Day</Text>
                    <Text size="xs" c="dimmed">Maximum trades per calendar day</Text>
                  </div>
                  <NumberInput
                    value={getSetting('max_trades_per_day', 4)}
                    onChange={(val) => handleUpdateSetting('max_trades_per_day', val)}
                    min={1}
                    step={1}
                    w={80}
                    size="sm"
                  />
                </Group>
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Max Trades Per Week</Text>
                    <Text size="xs" c="dimmed">Maximum trades per rolling 7-day window</Text>
                  </div>
                  <NumberInput
                    value={getSetting('max_trades_per_week', 10)}
                    onChange={(val) => handleUpdateSetting('max_trades_per_week', val)}
                    min={1}
                    step={1}
                    w={80}
                    size="sm"
                  />
                </Group>
              </Stack>
            </Paper>

            {/* Transaction Costs */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">Transaction Costs</Text>
              <Text size="xs" c="dimmed" mb="md">
                Freedom24 fee structure. Used to calculate minimum worthwhile trade size.
              </Text>
              <Stack gap="sm">
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Fixed Cost</Text>
                    <Text size="xs" c="dimmed">Per trade</Text>
                  </div>
                  <Group gap="xs">
                    <Text size="sm" c="dimmed">EUR</Text>
                    <NumberInput
                      value={getSetting('transaction_cost_fixed', 2.0)}
                      onChange={(val) => handleUpdateSetting('transaction_cost_fixed', val)}
                      min={0}
                      step={0.5}
                      w={80}
                      size="sm"
                    />
                  </Group>
                </Group>
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Variable Cost</Text>
                    <Text size="xs" c="dimmed">Percentage of trade</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={(getSetting('transaction_cost_percent', 0.002) * 100).toFixed(2)}
                      onChange={(val) => handleUpdateSetting('transaction_cost_percent', (val || 0) / 100)}
                      min={0}
                      step={0.01}
                      precision={2}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">%</Text>
                  </Group>
                </Group>
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Min Cash Reserve</Text>
                    <Text size="xs" c="dimmed">Never deploy below this</Text>
                  </div>
                  <Group gap="xs">
                    <Text size="sm" c="dimmed">EUR</Text>
                    <NumberInput
                      value={getSetting('min_cash_reserve', 500)}
                      onChange={(val) => handleUpdateSetting('min_cash_reserve', val)}
                      min={0}
                      step={50}
                      w={100}
                      size="sm"
                    />
                  </Group>
                </Group>
                <Divider />
                <Group justify="space-between">
                  <Text size="xs" c="dimmed">Min worthwhile trade (1% cost):</Text>
                  <Text size="sm" fw={500}>EUR {minTradeWorthwhile().toFixed(0)}</Text>
                </Group>
              </Stack>
            </Paper>

            {/* Scoring Parameters */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">Scoring Parameters</Text>
              <Stack gap="sm">
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Target Annual Return</Text>
                    <Text size="xs" c="dimmed">Target CAGR for scoring</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={(getSetting('target_annual_return', 0.11) * 100).toFixed(0)}
                      onChange={(val) => handleUpdateSetting('target_annual_return', (val || 0) / 100)}
                      min={0}
                      step={1}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">%</Text>
                  </Group>
                </Group>
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Market Avg P/E</Text>
                    <Text size="xs" c="dimmed">Baseline for valuation</Text>
                  </div>
                  <NumberInput
                    value={getSetting('market_avg_pe', 22)}
                    onChange={(val) => handleUpdateSetting('market_avg_pe', val)}
                    min={0}
                    step={0.1}
                    w={80}
                    size="sm"
                  />
                </Group>
              </Stack>
            </Paper>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="portfolio" p="md">
          <Stack gap="md">
            {/* Portfolio Optimizer */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">Portfolio Optimizer</Text>
              <Text size="xs" c="dimmed" mb="md">
                The optimizer calculates target portfolio weights using a blend of Mean-Variance and Hierarchical Risk Parity strategies.
              </Text>
              <Stack gap="md">
                <div>
                  <Group justify="space-between" mb="xs">
                    <Text size="sm">Strategy Blend</Text>
                    <Text size="sm" fw={500}>
                      {(getSetting('optimizer_blend', 0.5) * 100).toFixed(0)}%
                    </Text>
                  </Group>
                  <Group gap="xs" mb="xs">
                    <Text size="xs" c="dimmed">MV</Text>
                    <Slider
                      value={getSetting('optimizer_blend', 0.5)}
                      onChange={(val) => handleUpdateSetting('optimizer_blend', val)}
                      min={0}
                      max={1}
                      step={0.05}
                      style={{ flex: 1 }}
                    />
                    <Text size="xs" c="dimmed">HRP</Text>
                  </Group>
                  <Text size="xs" c="dimmed">0% = Goal-directed (Mean-Variance), 100% = Robust (HRP)</Text>
                </div>
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Target Return</Text>
                    <Text size="xs" c="dimmed">Annual return goal</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={(getSetting('optimizer_target_return', 0.11) * 100).toFixed(0)}
                      onChange={(val) => handleUpdateSetting('optimizer_target_return', (val || 0) / 100)}
                      min={0}
                      step={1}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">%</Text>
                  </Group>
                </Group>
              </Stack>
            </Paper>

            {/* Market Regime Detection */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">Market Regime Detection</Text>
              <Text size="xs" c="dimmed" mb="md">
                Cash reserves adjust automatically based on market conditions (SPY/QQQ 200-day MA).
              </Text>
              <Stack gap="sm">
                <Switch
                  label="Enable regime-based cash reserves"
                  checked={getSetting('market_regime_detection_enabled', 1) === 1}
                  onChange={(e) => handleUpdateSetting('market_regime_detection_enabled', e.currentTarget.checked ? 1 : 0)}
                />
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Bull Market Reserve</Text>
                    <Text size="xs" c="dimmed">Cash reserve percentage</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={(getSetting('market_regime_bull_cash_reserve', 0.02) * 100).toFixed(1)}
                      onChange={(val) => {
                        const v = Math.max(0.01, Math.min(0.40, (val || 0) / 100));
                        handleUpdateSetting('market_regime_bull_cash_reserve', v);
                      }}
                      min={1}
                      max={40}
                      step={0.5}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">%</Text>
                  </Group>
                </Group>
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Bear Market Reserve</Text>
                    <Text size="xs" c="dimmed">Cash reserve percentage</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={(getSetting('market_regime_bear_cash_reserve', 0.05) * 100).toFixed(1)}
                      onChange={(val) => {
                        const v = Math.max(0.01, Math.min(0.40, (val || 0) / 100));
                        handleUpdateSetting('market_regime_bear_cash_reserve', v);
                      }}
                      min={1}
                      max={40}
                      step={0.5}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">%</Text>
                  </Group>
                </Group>
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Sideways Market Reserve</Text>
                    <Text size="xs" c="dimmed">Cash reserve percentage</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={(getSetting('market_regime_sideways_cash_reserve', 0.03) * 100).toFixed(1)}
                      onChange={(val) => {
                        const v = Math.max(0.01, Math.min(0.40, (val || 0) / 100));
                        handleUpdateSetting('market_regime_sideways_cash_reserve', v);
                      }}
                      min={1}
                      max={40}
                      step={0.5}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">%</Text>
                  </Group>
                </Group>
                <Text size="xs" c="dimmed" mt="xs">
                  Reserves are calculated as percentage of total portfolio value, with a minimum floor of €500.
                </Text>
              </Stack>
            </Paper>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="display" p="md">
          <Stack gap="md">
            {/* LED Matrix */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">LED Matrix</Text>
              <Stack gap="sm">
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Ticker Speed</Text>
                    <Text size="xs" c="dimmed">Lower = faster scroll</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={getSetting('ticker_speed', 50)}
                      onChange={(val) => handleUpdateSetting('ticker_speed', val)}
                      min={1}
                      max={100}
                      step={1}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">ms</Text>
                  </Group>
                </Group>
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Brightness</Text>
                    <Text size="xs" c="dimmed">0-255 (default 150)</Text>
                  </div>
                  <NumberInput
                    value={getSetting('led_brightness', 150)}
                    onChange={(val) => handleUpdateSetting('led_brightness', val)}
                    min={0}
                    max={255}
                    step={10}
                    w={80}
                    size="sm"
                  />
                </Group>
                <Divider />
                <Text size="xs" fw={500} tt="uppercase" mb="xs">Ticker Content</Text>
                <Stack gap="xs">
                  <Switch
                    label="Portfolio value"
                    checked={getSetting('ticker_show_value', 1) === 1}
                    onChange={(e) => handleUpdateSetting('ticker_show_value', e.currentTarget.checked ? 1 : 0)}
                  />
                  <Switch
                    label="Cash balance"
                    checked={getSetting('ticker_show_cash', 1) === 1}
                    onChange={(e) => handleUpdateSetting('ticker_show_cash', e.currentTarget.checked ? 1 : 0)}
                  />
                  <Switch
                    label="Next actions"
                    checked={getSetting('ticker_show_actions', 1) === 1}
                    onChange={(e) => handleUpdateSetting('ticker_show_actions', e.currentTarget.checked ? 1 : 0)}
                  />
                  <Switch
                    label="Show amounts"
                    checked={getSetting('ticker_show_amounts', 1) === 1}
                    onChange={(e) => handleUpdateSetting('ticker_show_amounts', e.currentTarget.checked ? 1 : 0)}
                  />
                  <Group justify="space-between">
                    <Text size="sm">Max actions</Text>
                    <NumberInput
                      value={getSetting('ticker_max_actions', 3)}
                      onChange={(val) => handleUpdateSetting('ticker_max_actions', val)}
                      min={1}
                      max={10}
                      step={1}
                      w={80}
                      size="sm"
                    />
                  </Group>
                </Stack>
              </Stack>
            </Paper>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="system" p="md">
          <Stack gap="md">
            {/* Job Scheduling */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">Job Scheduling</Text>
              <Text size="xs" c="dimmed" mb="md">
                Simplified to 4 consolidated jobs: sync cycle (trading), daily pipeline (data), and maintenance.
              </Text>
              <Stack gap="sm">
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Sync Cycle</Text>
                    <Text size="xs" c="dimmed">Trades, prices, recommendations, execution</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={getSetting('job_sync_cycle_minutes', 15)}
                      onChange={(val) => handleUpdateSetting('job_sync_cycle_minutes', val)}
                      min={5}
                      max={60}
                      step={5}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">min</Text>
                  </Group>
                </Group>
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Maintenance</Text>
                    <Text size="xs" c="dimmed">Daily backup and cleanup hour</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={getSetting('job_maintenance_hour', 3)}
                      onChange={(val) => handleUpdateSetting('job_maintenance_hour', val)}
                      min={0}
                      max={23}
                      step={1}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">h</Text>
                  </Group>
                </Group>
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Auto-Deploy</Text>
                    <Text size="xs" c="dimmed">Check for updates and deploy changes</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={getSetting('job_auto_deploy_minutes', 5)}
                      onChange={(val) => handleUpdateSetting('job_auto_deploy_minutes', val)}
                      min={0}
                      step={1}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">min</Text>
                  </Group>
                </Group>
                <Divider />
                <Text size="xs" fw={500} tt="uppercase" mb="xs">Fixed Schedules</Text>
                <Text size="xs" c="dimmed">Daily Pipeline: Hourly (per-symbol data sync)</Text>
                <Text size="xs" c="dimmed">Weekly Maintenance: Sundays (integrity checks)</Text>
              </Stack>
            </Paper>

            {/* System Actions */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">System</Text>
              <Stack gap="sm">
                <Group justify="space-between">
                  <Text size="sm">Caches</Text>
                  <Button
                    size="xs"
                    variant="light"
                    onClick={handleResetCache}
                    loading={loading}
                  >
                    Reset
                  </Button>
                </Group>
                <Group justify="space-between">
                  <Text size="sm">Historical Data</Text>
                  <Button
                    size="xs"
                    variant="light"
                    onClick={handleSyncHistorical}
                    loading={syncingHistorical}
                  >
                    {syncingHistorical ? 'Syncing...' : 'Sync'}
                  </Button>
                </Group>
                <Group justify="space-between">
                  <Text size="sm">System</Text>
                  <Button
                    size="xs"
                    color="red"
                    variant="light"
                    onClick={handleRestartSystem}
                    loading={loading}
                  >
                    Restart
                  </Button>
                </Group>
              </Stack>
            </Paper>

            {/* Custom Grouping */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">Custom Grouping</Text>
              <Text size="xs" c="dimmed" mb="md">
                Create custom groups for countries and industries to simplify constraints and improve optimizer performance.
              </Text>
              <GroupingManager />
            </Paper>
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Modal>
  );
}
