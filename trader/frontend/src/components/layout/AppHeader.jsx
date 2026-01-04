import { Button, Group } from '@mantine/core';
import { IconSettings } from '@tabler/icons-react';
import { useAppStore } from '../../stores/appStore';
import { useSettingsStore } from '../../stores/settingsStore';

export function AppHeader() {
  const { tradernet, openSettingsModal } = useAppStore();
  const { tradingMode, toggleTradingMode } = useSettingsStore();

  return (
    <header style={{ padding: '12px 0', borderBottom: '1px solid var(--mantine-color-dark-6)' }}>
      <Group justify="space-between" align="center">
        <div>
          <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 'bold', color: 'var(--mantine-color-blue-4)' }}>
            Arduino Trader
          </h1>
          <p style={{ margin: 0, fontSize: '12px', color: 'var(--mantine-color-dark-2)' }}>
            Automated Portfolio Management
          </p>
        </div>
        <Group gap="md">
          {/* Tradernet Connection */}
          <Group gap="xs">
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: tradernet.connected ? 'var(--mantine-color-green-5)' : 'var(--mantine-color-red-5)',
              }}
            />
            <span style={{ fontSize: '12px', color: tradernet.connected ? 'var(--mantine-color-green-4)' : 'var(--mantine-color-red-4)' }}>
              {tradernet.connected ? 'Tradernet' : 'Offline'}
            </span>
          </Group>
          {/* Trading Mode Toggle */}
          <Button
            variant="light"
            size="xs"
            onClick={toggleTradingMode}
            color={tradingMode === 'research' ? 'yellow' : 'green'}
            title={tradingMode === 'research' ? 'Research Mode: Trades are simulated' : 'Live Mode: Trades are executed'}
          >
            <Group gap="xs">
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: tradingMode === 'research' ? 'var(--mantine-color-yellow-5)' : 'var(--mantine-color-green-5)',
                }}
              />
              <span style={{ fontSize: '12px', fontWeight: 500 }}>
                {tradingMode === 'research' ? 'Research' : 'Live'}
              </span>
            </Group>
          </Button>
          <Button
            variant="subtle"
            size="xs"
            onClick={openSettingsModal}
            title="Settings"
          >
            <IconSettings size={20} />
          </Button>
        </Group>
      </Group>
    </header>
  );
}
