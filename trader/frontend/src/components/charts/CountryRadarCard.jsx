import { Card, Group, Text, Badge, Stack, Alert } from '@mantine/core';
import { AllocationRadar } from './AllocationRadar';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { formatPercent } from '../../utils/formatters';

export function CountryRadarCard() {
  const { alerts } = usePortfolioStore();

  const countryAlerts = alerts.filter(a => a.type === 'country');
  const hasCritical = countryAlerts.some(a => a.severity === 'critical');

  return (
    <Card p="md">
      <Group justify="space-between" mb="md">
        <Text size="xs" tt="uppercase" c="dimmed" fw={600}>
          Country Allocation
        </Text>
        {countryAlerts.length > 0 && (
          <Badge
            size="sm"
            color={hasCritical ? 'red' : 'yellow'}
            variant="light"
          >
            {countryAlerts.length} alert{countryAlerts.length > 1 ? 's' : ''}
          </Badge>
        )}
      </Group>

      <AllocationRadar type="country" />

      {/* Country Alerts */}
      {countryAlerts.length > 0 && (
        <Stack gap="xs" mt="md" pt="md" style={{ borderTop: '1px solid var(--mantine-color-dark-6)' }}>
          {countryAlerts.map((alert) => (
            <Alert
              key={alert.name}
              color={alert.severity === 'critical' ? 'red' : 'yellow'}
              variant="light"
              title={
                <Group justify="space-between" style={{ width: '100%' }}>
                  <Group gap="xs">
                    <Text size="xs">{alert.severity === 'critical' ? '🔴' : '⚠️'}</Text>
                    <Text size="sm" fw={500}>
                      {alert.name}
                    </Text>
                  </Group>
                  <Group gap="xs">
                    <Text size="sm" ff="monospace" fw={600}>
                      {formatPercent(alert.current_pct)}
                    </Text>
                    <Text size="xs" c="dimmed">
                      Limit: {formatPercent(alert.limit_pct, 0)}
                    </Text>
                  </Group>
                </Group>
              }
            />
          ))}
        </Stack>
      )}
    </Card>
  );
}

