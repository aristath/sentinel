import { Paper, Group, Text } from '@mantine/core';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { formatCurrency, formatNumber } from '../../utils/formatters';

export function StatusBar() {
  const { status } = useAppStore();
  const { allocation, cashBreakdown } = usePortfolioStore();

  return (
    <Paper p="md" style={{ backgroundColor: 'var(--mantine-color-dark-7)' }}>
      {/* System Status Row */}
      <Group justify="space-between" mb="xs">
        <Group gap="md">
          <Group gap="xs">
            <div
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: status.status === 'healthy' ? 'var(--mantine-color-green-5)' : 'var(--mantine-color-red-5)',
              }}
            />
            <Text size="xs" c="dimmed">
              {status.status === 'healthy' ? 'System Online' : 'System Offline'}
            </Text>
          </Group>
          <Text size="xs" c="dimmed">|</Text>
          <Text size="xs" c="dimmed">
            Last sync: <span style={{ color: 'var(--mantine-color-dark-2)' }}>{status.last_sync || 'Never'}</span>
          </Text>
        </Group>
      </Group>

      {/* Portfolio Summary Row */}
      <Group justify="space-between">
        <Group gap="md" wrap="wrap">
          <Text size="xs" c="dimmed">
            Total Value: <span style={{ color: 'var(--mantine-color-green-4)', fontFamily: 'monospace' }}>
              {formatCurrency(allocation.total_value)}
            </span>
          </Text>
          <Text size="xs" c="dimmed">|</Text>
          <Text size="xs" c="dimmed">
            Cash: <span style={{ color: 'var(--mantine-color-dark-2)', fontFamily: 'monospace' }}>
              {formatCurrency(allocation.cash_balance)}
            </span>
          </Text>
          {cashBreakdown && cashBreakdown.length > 0 && (
            <>
              <Text size="xs" c="dimmed">
                ({cashBreakdown.map((cb, index) => (
                  <span key={cb.currency}>
                    {cb.currency === 'TEST' ? (
                      <span style={{ backgroundColor: 'rgba(34, 197, 94, 0.2)', padding: '2px 4px', borderRadius: '4px' }}>
                        <span style={{ color: 'var(--mantine-color-green-4)' }}>{cb.currency}</span>:
                        <span style={{ fontFamily: 'monospace', color: 'var(--mantine-color-green-4)' }}>
                          {formatNumber(cb.amount, 2)}
                        </span>
                      </span>
                    ) : (
                      <span>
                        {cb.currency}: <span style={{ fontFamily: 'monospace' }}>{formatNumber(cb.amount, 2)}</span>
                      </span>
                    )}
                    {index < cashBreakdown.length - 1 && ', '}
                  </span>
                ))})
              </Text>
            </>
          )}
          <Text size="xs" c="dimmed">|</Text>
          <Text size="xs" c="dimmed">
            Positions: <span style={{ color: 'var(--mantine-color-dark-2)', fontFamily: 'monospace' }}>
              {status.active_positions || 0}
            </span>
          </Text>
        </Group>
      </Group>
    </Paper>
  );
}
