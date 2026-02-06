import { AppShell, Group, Title, ActionIcon, Badge, Tooltip, Switch, Text } from '@mantine/core';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { IconSettings, IconClock, IconRefresh, IconChartLine, IconPlanet, IconReceipt, IconBrain } from '@tabler/icons-react';

import UnifiedPage from './pages/UnifiedPage';
import { SchedulerModal } from './components/SchedulerModal';
import { SettingsModal } from './components/SettingsModal';
import { BacktestModal } from './components/BacktestModal';
import { TradesModal } from './components/TradesModal';
import { getSchedulerStatus, refreshAll, getSettings, updateSetting, getLedStatus, setLedEnabled, getVersion, getResetStatus } from './api/client';
import { useState } from 'react';

function App() {
  const [schedulerOpen, setSchedulerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [backtestOpen, setBacktestOpen] = useState(false);
  const [tradesOpen, setTradesOpen] = useState(false);
  const [mlModalOpen, setMlModalOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: schedulerStatus } = useQuery({
    queryKey: ['scheduler'],
    queryFn: getSchedulerStatus,
    refetchInterval: 10000,
  });

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  });

  const { data: ledStatus } = useQuery({
    queryKey: ['ledStatus'],
    queryFn: getLedStatus,
    refetchInterval: 30000,
  });

  const { data: versionData } = useQuery({
    queryKey: ['version'],
    queryFn: getVersion,
    staleTime: Infinity,
  });

  const refreshMutation = useMutation({
    mutationFn: refreshAll,
    onSuccess: () => {
      queryClient.invalidateQueries();
    },
  });

  const tradingModeMutation = useMutation({
    mutationFn: (mode) => updateSetting('trading_mode', mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });

  const ledMutation = useMutation({
    mutationFn: setLedEnabled,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ledStatus'] });
    },
  });

  const { data: resetStatus } = useQuery({
    queryKey: ['resetStatus'],
    queryFn: getResetStatus,
    refetchInterval: (query) => {
      // Only poll frequently when a reset is running
      return query.state.data?.running ? 1000 : 10000;
    },
  });

  const runningJobs = schedulerStatus?.pending?.length || 0;
  const isRefreshing = refreshMutation.isPending || runningJobs > 0;
  const isLive = settings?.trading_mode === 'live';
  const ledEnabled = ledStatus?.enabled || false;
  const ledRunning = ledStatus?.running || false;

  return (
    <>
      <AppShell header={{ height: 50 }} padding="md" className="app">
        <AppShell.Header className="app__header">
          <Group h="100%" px="md" justify="space-between" className="app__header-content">
            <Group gap={8} align="baseline" className="app__logo">
              <Title order={3} c="blue">
                Sentinel
              </Title>
              {versionData?.version && (
                <Text size="xs" c="dimmed">
                  {versionData.version}
                </Text>
              )}
            </Group>

            <Group gap="md" className="app__controls">
              <Group gap="xs" className="app__trading-mode">
                <Text size="sm" c={isLive ? 'red' : 'dimmed'} className={`app__trading-mode-label ${isLive ? 'app__trading-mode-label--live' : 'app__trading-mode-label--research'}`}>
                  {isLive ? 'LIVE' : 'Research'}
                </Text>
                <Switch
                  checked={isLive}
                  onChange={(e) =>
                    tradingModeMutation.mutate(e.currentTarget.checked ? 'live' : 'research')
                  }
                  color="red"
                  size="sm"
                  disabled={tradingModeMutation.isPending}
                  className="app__trading-mode-switch"
                />
              </Group>

              <Group gap="xs" className="app__actions">
                <Tooltip label={ledEnabled ? (ledRunning ? 'LED Display Active' : 'LED Display Enabled') : 'LED Display Off'}>
                  <ActionIcon
                    variant={ledEnabled ? 'light' : 'subtle'}
                    color={ledEnabled ? (ledRunning ? 'teal' : 'blue') : 'gray'}
                    size="lg"
                    onClick={() => ledMutation.mutate(!ledEnabled)}
                    loading={ledMutation.isPending}
                    className="app__action-btn app__action-btn--led"
                  >
                    <IconPlanet size={20} />
                  </ActionIcon>
                </Tooltip>

                {!isLive && (
                  <Tooltip label="Backtest Portfolio">
                    <ActionIcon
                      variant="subtle"
                      size="lg"
                      onClick={() => setBacktestOpen(true)}
                      className="app__action-btn app__action-btn--backtest"
                    >
                      <IconChartLine size={20} />
                    </ActionIcon>
                  </Tooltip>
                )}

                <Tooltip label="Trade History">
                  <ActionIcon
                    variant="subtle"
                    size="lg"
                    onClick={() => setTradesOpen(true)}
                    className="app__action-btn app__action-btn--trades"
                  >
                    <IconReceipt size={20} />
                  </ActionIcon>
                </Tooltip>

                <Tooltip label="Refresh All (sync rates, portfolio, prices, scores)">
                  <ActionIcon
                    variant="subtle"
                    size="lg"
                    onClick={() => refreshMutation.mutate()}
                    loading={refreshMutation.isPending}
                    disabled={isRefreshing}
                    className="app__action-btn app__action-btn--refresh"
                  >
                    <IconRefresh size={20} />
                  </ActionIcon>
                </Tooltip>

                <Tooltip
                  label={resetStatus?.running
                    ? 'ML retraining in progress - open ML tuning'
                    : 'ML tuning and per-security projections'}
                >
                  <ActionIcon
                    variant="subtle"
                    size="lg"
                    color={resetStatus?.running ? 'orange' : undefined}
                    onClick={() => setMlModalOpen(true)}
                    className="app__action-btn app__action-btn--reset-retrain"
                  >
                    <IconBrain size={20} />
                  </ActionIcon>
                </Tooltip>

                <Tooltip label="Scheduler">
                  <ActionIcon
                    variant="subtle"
                    size="lg"
                    onClick={() => setSchedulerOpen(true)}
                    pos="relative"
                    className="app__action-btn app__action-btn--scheduler"
                  >
                    <IconClock size={20} />
                    {runningJobs > 0 && (
                      <Badge
                        size="sm"
                        color="blue"
                        circle
                        pos="absolute"
                        top={-4}
                        right={-4}
                        className="app__running-jobs-badge"
                      >
                        {runningJobs}
                      </Badge>
                    )}
                  </ActionIcon>
                </Tooltip>

                <Tooltip label="Settings">
                  <ActionIcon
                    variant="subtle"
                    size="lg"
                    onClick={() => setSettingsOpen(true)}
                    className="app__action-btn app__action-btn--settings"
                  >
                    <IconSettings size={20} />
                  </ActionIcon>
                </Tooltip>
              </Group>
            </Group>
          </Group>
        </AppShell.Header>

        <AppShell.Main className="app__main">
          <UnifiedPage mlModalOpen={mlModalOpen} onCloseMlModal={() => setMlModalOpen(false)} />
        </AppShell.Main>
      </AppShell>

      <SchedulerModal opened={schedulerOpen} onClose={() => setSchedulerOpen(false)} />
      <SettingsModal opened={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <BacktestModal opened={backtestOpen} onClose={() => setBacktestOpen(false)} />
      <TradesModal opened={tradesOpen} onClose={() => setTradesOpen(false)} />
    </>
  );
}

export default App;
