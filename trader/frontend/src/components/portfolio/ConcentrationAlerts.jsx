import { Alert, Stack, Text } from '@mantine/core';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { formatPercent } from '../../utils/formatters';

export function ConcentrationAlerts() {
  const { alerts } = usePortfolioStore();

  const criticalAlerts = alerts.filter(a => a.severity === 'critical');
  const warningAlerts = alerts.filter(a => a.severity === 'warning');

  if (alerts.length === 0) {
    return null;
  }

  return (
    <Stack gap="xs">
      {criticalAlerts.length > 0 && (
        <Alert color="red" variant="light" title={`${criticalAlerts.length} Critical Alert${criticalAlerts.length > 1 ? 's' : ''}`}>
          <Stack gap="xs">
            {criticalAlerts.map((alert) => (
              <div key={alert.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text size="sm" fw={500}>
                  {alert.name} ({alert.type})
                </Text>
                <Text size="sm" ff="monospace" fw={600}>
                  {formatPercent(alert.current_pct)} / {formatPercent(alert.limit_pct, 0)} limit
                </Text>
              </div>
            ))}
          </Stack>
        </Alert>
      )}

      {warningAlerts.length > 0 && (
        <Alert color="yellow" variant="light" title={`${warningAlerts.length} Warning${warningAlerts.length > 1 ? 's' : ''}`}>
          <Stack gap="xs">
            {warningAlerts.map((alert) => (
              <div key={alert.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text size="sm" fw={500}>
                  {alert.name} ({alert.type})
                </Text>
                <Text size="sm" ff="monospace" fw={600}>
                  {formatPercent(alert.current_pct)} / {formatPercent(alert.limit_pct, 0)} limit
                </Text>
              </div>
            ))}
          </Stack>
        </Alert>
      )}
    </Stack>
  );
}

