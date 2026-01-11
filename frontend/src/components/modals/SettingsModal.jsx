import { useState, useEffect } from 'react';
import { Modal, Tabs, Text, Button, NumberInput, Switch, Slider, Group, Stack, Paper, Divider, Alert, TextInput, PasswordInput, Select } from '@mantine/core';
import { useAppStore } from '../../stores/appStore';
import { useSettingsStore } from '../../stores/settingsStore';
import { api } from '../../api/client';
import { useNotifications } from '../../hooks/useNotifications';
import { R2BackupModal } from './R2BackupModal';

export function SettingsModal() {
  const { showSettingsModal, closeSettingsModal } = useAppStore();
  const { settings, fetchSettings, updateSetting } = useSettingsStore();
  const { showNotification } = useNotifications();
  const [activeTab, setActiveTab] = useState('trading');
  const [loading, setLoading] = useState(false);
  const [syncingHistorical, setSyncingHistorical] = useState(false);
  const [testingR2Connection, setTestingR2Connection] = useState(false);
  const [backingUpToR2, setBackingUpToR2] = useState(false);
  const [showR2BackupModal, setShowR2BackupModal] = useState(false);
  const [riskToleranceValue, setRiskToleranceValue] = useState(0.5);

  useEffect(() => {
    if (showSettingsModal) {
      fetchSettings();
    }
  }, [showSettingsModal, fetchSettings]);

  useEffect(() => {
    setRiskToleranceValue(settings?.risk_tolerance ?? 0.5);
  }, [settings]);

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

  const handleTestR2Connection = async () => {
    setTestingR2Connection(true);
    try {
      const result = await api.testR2Connection();
      if (result.status === 'success') {
        showNotification('R2 connection successful', 'success');
      } else {
        showNotification(`R2 connection failed: ${result.message}`, 'error');
      }
    } catch (error) {
      showNotification(`Failed to test R2 connection: ${error.message}`, 'error');
    } finally {
      setTestingR2Connection(false);
    }
  };

  const handleBackupToR2 = async () => {
    setBackingUpToR2(true);
    try {
      await api.createR2Backup();
      showNotification('Backup job started successfully', 'success');
    } catch (error) {
      showNotification(`Failed to create backup: ${error.message}`, 'error');
    } finally {
      setBackingUpToR2(false);
    }
  };

  const handleViewR2Backups = () => {
    setShowR2BackupModal(true);
  };

  return (
    <>
      <Modal
        opened={showSettingsModal}
        onClose={closeSettingsModal}
        title="Settings"
        size="xl"
        styles={{ body: { padding: 0 } }}
      >
      <Tabs value={activeTab} onChange={setActiveTab}>
        <Tabs.List grow>
          <Tabs.Tab value="controller">Controller</Tabs.Tab>
          <Tabs.Tab value="trading">Trading</Tabs.Tab>
          <Tabs.Tab value="display">Display</Tabs.Tab>
          <Tabs.Tab value="system">System</Tabs.Tab>
          <Tabs.Tab value="backup">Backup</Tabs.Tab>
          <Tabs.Tab value="credentials">Credentials</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="controller" p="md">
          <Stack gap="md">
            {/* Risk Tolerance */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">Risk Tolerance</Text>
              <Text size="xs" c="dimmed" mb="md">
                Overall risk appetite: 0 = avoid risk at all costs, 1 = take more risks.
                This adjusts internal thresholds automatically throughout the system.
              </Text>
              <Stack gap="sm">
                <Slider
                  value={riskToleranceValue}
                  onChange={setRiskToleranceValue}
                  onChangeEnd={(val) => handleUpdateSetting('risk_tolerance', val)}
                  min={0}
                  max={1}
                  step={0.01}
                  marks={[
                    { value: 0, label: 'Avoid Risk' },
                    { value: 0.5, label: 'Neutral' },
                    { value: 1, label: 'Take Risks' }
                  ]}
                />
                <Group justify="space-between" mt="xs">
                  <Text size="xs" c="dimmed">Current: {(riskToleranceValue * 100).toFixed(0)}%</Text>
                  <Text size="xs" c="dimmed">Range: 0.0 - 1.0</Text>
                </Group>
                <Alert color="blue" variant="light" size="sm">
                  <Text size="xs">
                    Adjusting risk tolerance will automatically modify thresholds like minimum security scores,
                    affecting which securities are recommended and how the system evaluates opportunities.
                  </Text>
                </Alert>
              </Stack>
            </Paper>
          </Stack>
        </Tabs.Panel>

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

            {/* Limit Order Protection */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">Limit Order Protection</Text>
              <Stack gap="sm">
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Limit Order Buffer</Text>
                    <Text size="xs" c="dimmed">Price protection buffer for limit orders</Text>
                  </div>
                  <Group gap="xs">
                    <NumberInput
                      value={(getSetting('limit_order_buffer_percent', 0.05) * 100).toFixed(1)}
                      onChange={(val) => handleUpdateSetting('limit_order_buffer_percent', (val || 0) / 100)}
                      min={1}
                      max={15}
                      step={0.5}
                      precision={1}
                      w={80}
                      size="sm"
                    />
                    <Text size="sm" c="dimmed">%</Text>
                  </Group>
                </Group>
                <Alert color="blue" variant="light" styles={{message: {fontSize: '12px'}}}>
                  <Text size="xs">
                    <strong>Example:</strong> If Yahoo shows €30 and buffer is 5%, buy limit is €31.50.
                    If Tradernet real price is €600 (error), order won&apos;t fill. Money safe!
                  </Text>
                </Alert>
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
                  Reserves are calculated as percentage of total portfolio value, with a minimum floor set in Planner Configuration.
                </Text>
              </Stack>
            </Paper>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="display" p="md">
          <Stack gap="md">
            {/* Display Mode */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">Display Mode</Text>
              <Text size="xs" c="dimmed" mb="md">
                Choose what to show on the LED matrix display.
              </Text>
              <Select
                label="Display Mode"
                value={getSetting('display_mode', 'STATS') || 'STATS'}
                onChange={(val) => handleUpdateSetting('display_mode', val)}
                data={[
                  { value: 'STATS', label: 'System Stats (CPU/RAM visualization)' },
                  { value: 'TICKER', label: 'Ticker (Portfolio value, cash, actions)' },
                  { value: 'PORTFOLIO', label: 'Portfolio (Visual holdings representation)' }
                ]}
                description="Select which information to display on the LED matrix"
              />
            </Paper>

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
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="backup" p="md">
          <Stack gap="md">
            {/* Cloudflare R2 Backup */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">Cloudflare R2 Backup</Text>
              <Text size="xs" c="dimmed" mb="md">
                Automatically backup databases to Cloudflare R2 cloud storage. Backups include all 7 databases in a single compressed archive.
              </Text>
              <Stack gap="md">
                <Switch
                  label="Enable R2 backups"
                  checked={getSetting('r2_backup_enabled', 0) === 1}
                  onChange={(e) => handleUpdateSetting('r2_backup_enabled', e.currentTarget.checked ? 1 : 0)}
                  description="Automatically backup databases to Cloudflare R2 daily at 3:00 AM"
                />
                <Divider />
                <Text size="xs" fw={500} tt="uppercase" mb="xs">R2 Configuration</Text>
                <TextInput
                  label="Account ID"
                  value={getSetting('r2_account_id', '') || ''}
                  onChange={(e) => handleUpdateSetting('r2_account_id', e.target.value)}
                  placeholder="a1b2c3d4e5f6g7h8i9j0"
                  description="Your Cloudflare account ID"
                />
                <TextInput
                  label="Access Key ID"
                  value={getSetting('r2_access_key_id', '') || ''}
                  onChange={(e) => handleUpdateSetting('r2_access_key_id', e.target.value)}
                  placeholder="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
                  description="R2 access key ID for authentication"
                />
                <PasswordInput
                  label="Secret Access Key"
                  value={getSetting('r2_secret_access_key', '') || ''}
                  onChange={(e) => handleUpdateSetting('r2_secret_access_key', e.target.value)}
                  placeholder="Enter your R2 secret access key"
                  description="R2 secret access key (hidden for security)"
                />
                <TextInput
                  label="Bucket Name"
                  value={getSetting('r2_bucket_name', '') || ''}
                  onChange={(e) => handleUpdateSetting('r2_bucket_name', e.target.value)}
                  placeholder="sentinel-backups"
                  description="Name of your R2 bucket for backups"
                />
                <Select
                  label="Backup Schedule"
                  value={getSetting('r2_backup_schedule', 'daily') || 'daily'}
                  onChange={(val) => handleUpdateSetting('r2_backup_schedule', val)}
                  data={[
                    { value: 'daily', label: 'Daily (recommended)' },
                    { value: 'weekly', label: 'Weekly (Sundays)' },
                    { value: 'monthly', label: 'Monthly (1st of month)' }
                  ]}
                  description="How often to automatically backup to R2"
                />
                <Group justify="space-between">
                  <div>
                    <Text size="sm">Retention Days</Text>
                    <Text size="xs" c="dimmed">Keep backups for this many days (0 = forever)</Text>
                  </div>
                  <NumberInput
                    value={getSetting('r2_backup_retention_days', 90)}
                    onChange={(val) => handleUpdateSetting('r2_backup_retention_days', val)}
                    min={0}
                    step={1}
                    w={100}
                    size="sm"
                  />
                </Group>
                <Divider />
                <Text size="xs" fw={500} tt="uppercase" mb="xs">Actions</Text>
                <Group gap="sm">
                  <Button
                    size="sm"
                    variant="light"
                    onClick={handleTestR2Connection}
                    loading={testingR2Connection}
                    disabled={!getSetting('r2_account_id', '') || !getSetting('r2_access_key_id', '')}
                  >
                    Test Connection
                  </Button>
                  <Button
                    size="sm"
                    variant="light"
                    onClick={handleViewR2Backups}
                    disabled={!getSetting('r2_account_id', '') || !getSetting('r2_access_key_id', '')}
                  >
                    View Backups
                  </Button>
                  <Button
                    size="sm"
                    variant="filled"
                    onClick={handleBackupToR2}
                    loading={backingUpToR2}
                    disabled={!getSetting('r2_account_id', '') || !getSetting('r2_access_key_id', '')}
                  >
                    Backup Now
                  </Button>
                </Group>
                <Alert color="blue" size="sm">
                  <Text size="xs">
                    Backups are stored as compressed .tar.gz archives containing all databases.
                    Automatic backups run according to your schedule at 3:00 AM. Old backups are rotated based on retention policy.
                  </Text>
                </Alert>
              </Stack>
            </Paper>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="credentials" p="md">
          <Stack gap="md">
            {/* API Credentials */}
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs" tt="uppercase">API Credentials</Text>
              <Text size="xs" c="dimmed" mb="md">
                Configure API keys for external services. Credentials are stored securely in the database.
                The .env file is no longer required - all configuration can be managed through this UI.
              </Text>
              <Stack gap="md">
                <TextInput
                  label="Tradernet API Key"
                  value={getSetting('tradernet_api_key', '') || ''}
                  onChange={(e) => handleUpdateSetting('tradernet_api_key', e.target.value)}
                  placeholder="Enter your Tradernet API key"
                  description="Your Tradernet API key for accessing trading services"
                />
                <TextInput
                  label="Tradernet API Secret"
                  type="password"
                  value={getSetting('tradernet_api_secret', '') || ''}
                  onChange={(e) => handleUpdateSetting('tradernet_api_secret', e.target.value)}
                  placeholder="Enter your Tradernet API secret"
                  description="Your Tradernet API secret (hidden for security)"
                />
                <Divider />
                <TextInput
                  label="GitHub Token"
                  type="password"
                  value={getSetting('github_token', '') || ''}
                  onChange={(e) => handleUpdateSetting('github_token', e.target.value)}
                  placeholder="ghp_your_token_here"
                  description="GitHub personal access token for auto-deployment artifact downloads (requires repo and actions:read scopes)"
                />
                <Divider />
                <Alert color="blue" size="sm">
                  <Text size="xs">
                    Credentials are stored in the settings database and take precedence over environment variables.
                    Changes are applied immediately - no restart required.
                  </Text>
                </Alert>
              </Stack>
            </Paper>
          </Stack>
        </Tabs.Panel>
      </Tabs>
      </Modal>
      <R2BackupModal
        opened={showR2BackupModal}
        onClose={() => setShowR2BackupModal(false)}
      />
    </>
  );
}
