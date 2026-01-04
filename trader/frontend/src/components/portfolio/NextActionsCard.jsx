import { Card, Group, Text, Button, Badge, Progress, Stack, Paper, ActionIcon } from '@mantine/core';
import { IconRefresh, IconRotateClockwise } from '@tabler/icons-react';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { useSettingsStore } from '../../stores/settingsStore';
import { formatCurrency } from '../../utils/formatters';
import { useEffect } from 'react';

export function NextActionsCard() {
  const {
    recommendations,
    plannerStatus,
    loading,
    fetchRecommendations,
    executeRecommendation,
    regenerateSequences,
    startPlannerStatusStream,
    stopPlannerStatusStream,
  } = useAppStore();
  const { allocation } = usePortfolioStore();
  const { settings } = useSettingsStore();

  useEffect(() => {
    startPlannerStatusStream();
    return () => {
      stopPlannerStatusStream();
    };
  }, []);

  const handleRegenerateSequences = async () => {
    if (confirm('This will delete existing sequences and regenerate them with current settings. Existing evaluations will be preserved. Continue?')) {
      await regenerateSequences();
    }
  };

  const steps = recommendations?.steps || [];
  const hasRecommendations = steps.length > 0;

  return (
    <Card
      p="lg"
      style={{
        border: '2px solid rgba(59, 130, 246, 0.3)',
        backgroundColor: 'var(--mantine-color-dark-7)',
      }}
    >
      <Group justify="space-between" mb="md">
        <div style={{ flex: 1 }}>
          <Text size="lg" fw={700} c="blue" tt="uppercase" mb="xs">
            Next Actions
          </Text>
          <Text size="xs" c="dimmed">
            Automated portfolio management recommendations
          </Text>
        </div>
        <Group gap="md" visibleFrom="md">
          <div style={{ textAlign: 'right' }}>
            <Text size="xs" c="dimmed">Total Value</Text>
            <Text size="sm" fw={600} c="green" ff="monospace">
              {formatCurrency(allocation.total_value)}
            </Text>
          </div>
          <div style={{ width: '1px', height: '32px', backgroundColor: 'var(--mantine-color-dark-6)' }} />
          <div style={{ textAlign: 'right' }}>
            <Text size="xs" c="dimmed">Cash</Text>
            <Text size="sm" fw={600} c="dimmed" ff="monospace">
              {formatCurrency(allocation.cash_balance)}
            </Text>
          </div>
        </Group>
        <Group gap="xs">
          <ActionIcon
            variant="subtle"
            onClick={fetchRecommendations}
            loading={loading.recommendations}
            title="Refresh recommendations"
          >
            <IconRefresh size={18} />
          </ActionIcon>
          {settings.incremental_planner_enabled === 1 && (
            <ActionIcon
              variant="subtle"
              onClick={handleRegenerateSequences}
              title="Regenerate sequences"
            >
              <IconRotateClockwise size={18} />
            </ActionIcon>
          )}
        </Group>
      </Group>

      {/* Planner Status */}
      {plannerStatus && (
        <Paper p="md" mb="md" style={{ backgroundColor: 'var(--mantine-color-dark-8)', border: '2px solid rgba(59, 130, 246, 0.3)' }}>
          <Group gap="xs" mb="sm">
            {plannerStatus.is_planning && <Text c="blue">⏳</Text>}
            {!plannerStatus.is_planning && !plannerStatus.is_finished && plannerStatus.has_sequences && <Text c="dimmed">⏸</Text>}
            {plannerStatus.is_finished && <Text c="green">✓</Text>}
            <Text size="sm" fw={600} c={plannerStatus.is_planning ? 'blue' : plannerStatus.is_finished ? 'green' : 'dimmed'}>
              {plannerStatus.is_planning
                ? 'Planning...'
                : plannerStatus.is_finished
                ? 'Planning Complete'
                : plannerStatus.has_sequences
                ? 'Waiting...'
                : 'Generating Scenarios...'}
            </Text>
          </Group>

          {plannerStatus.has_sequences && (
            <div>
              <Progress
                value={Math.min(plannerStatus.progress_percentage || 0, 100)}
                size="sm"
                mb="xs"
                color="blue"
              />
              <Text size="xs" c="dimmed" ta="center">
                {(plannerStatus.evaluated_count || 0).toLocaleString()} / {(plannerStatus.total_sequences || 0).toLocaleString()} scenarios evaluated (
                {Math.round(plannerStatus.progress_percentage || 0)}%)
              </Text>
            </div>
          )}

          {!plannerStatus.has_sequences && (
            <Text size="sm" c="dimmed" ta="center">
              Generating scenarios...
            </Text>
          )}
        </Paper>
      )}

      {/* Empty State */}
      {!loading.recommendations && !hasRecommendations && (
        <Stack align="center" py="xl">
          <Text size="lg" fw={600} c="dimmed">
            No recommendations pending
          </Text>
          <Text size="sm" c="dimmed">
            Portfolio is optimally balanced
          </Text>
        </Stack>
      )}

      {/* Recommendations Sequence */}
      {hasRecommendations && (
        <Stack gap="md">
          {recommendations.evaluated_count !== undefined && (
            <Text size="sm" c="dimmed">
              Scenarios evaluated: {(recommendations.evaluated_count || 0).toLocaleString()}
            </Text>
          )}
          <Group justify="space-between">
            <Group gap="md">
              <Text size="sm" fw={600}>
                Optimal Sequence ({steps.length} step{steps.length > 1 ? 's' : ''})
              </Text>
              {recommendations.total_score_improvement > 0 && (
                <Badge color="green" variant="light">
                  +{recommendations.total_score_improvement.toFixed(1)} score
                </Badge>
              )}
              {recommendations.total_score_improvement < 0 && (
                <Badge color="red" variant="light">
                  {recommendations.total_score_improvement.toFixed(1)} score
                </Badge>
              )}
            </Group>
            <Text size="xs" c="dimmed" fs="italic">
              Trades execute automatically every {Math.round(settings.job_sync_cycle_minutes || 15)} minutes
            </Text>
          </Group>

          <Stack gap="md">
            {steps.map((step, index) => (
              <Paper
                key={`step-${step.step}`}
                p="md"
                style={{
                  border: '2px solid',
                  borderColor: step.is_emergency
                    ? 'rgba(249, 115, 22, 0.5)'
                    : step.side === 'SELL'
                    ? 'rgba(127, 29, 29, 0.5)'
                    : 'rgba(20, 83, 45, 0.5)',
                  backgroundColor: 'var(--mantine-color-dark-8)',
                }}
              >
                <Group justify="space-between" align="flex-start">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Group gap="xs" mb="xs" wrap="wrap">
                      <Badge size="sm" variant="filled" color="dark" ff="monospace">
                        Step {step.step}
                      </Badge>
                      {step.is_emergency && (
                        <Badge size="sm" color="orange" variant="light">
                          🚨 EMERGENCY
                        </Badge>
                      )}
                      <Badge
                        size="sm"
                        color={step.side === 'SELL' ? 'red' : 'green'}
                        variant="light"
                        ff="monospace"
                      >
                        {step.side}
                      </Badge>
                      <Text size="lg" fw={700} ff="monospace" c={step.side === 'SELL' ? 'red' : 'green'}>
                        {step.symbol}
                      </Text>
                    </Group>
                    <Text size="md" fw={500} mb="xs">
                      {step.name}
                    </Text>
                    <Text
                      size="sm"
                      mb="xs"
                      c={step.is_emergency ? 'orange' : 'dimmed'}
                      fw={step.is_emergency ? 600 : 400}
                    >
                      {step.reason}
                    </Text>
                    <Group gap="md" wrap="wrap">
                      <Text size="sm" c="dimmed">
                        Score: {step.portfolio_score_before.toFixed(1)} → {step.portfolio_score_after.toFixed(1)}
                      </Text>
                      {step.score_change > 0 && (
                        <Badge size="sm" color="green" variant="light">
                          +{step.score_change.toFixed(1)}
                        </Badge>
                      )}
                      {step.score_change < 0 && (
                        <Badge size="sm" color="red" variant="light">
                          {step.score_change.toFixed(1)}
                        </Badge>
                      )}
                    </Group>
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <Text
                      size="lg"
                      fw={700}
                      ff="monospace"
                      c={step.side === 'SELL' ? 'red' : 'green'}
                    >
                      {(step.side === 'SELL' ? '-' : '+')}€{step.estimated_value.toLocaleString()}
                    </Text>
                    <Text size="sm" c="dimmed">
                      {step.quantity} @ €{step.estimated_price}
                    </Text>
                    <Text size="xs" c="dimmed">
                      Cash: €{step.available_cash_before.toLocaleString()} → €{step.available_cash_after.toLocaleString()}
                    </Text>
                  </div>
                </Group>
              </Paper>
            ))}
          </Stack>

          {recommendations.final_available_cash && (
            <Text size="sm" c="dimmed" ta="center" mt="md">
              Final cash: <Text span fw={600} c="dimmed" ff="monospace">
                €{recommendations.final_available_cash.toLocaleString()}
              </Text>
            </Text>
          )}
        </Stack>
      )}
    </Card>
  );
}

