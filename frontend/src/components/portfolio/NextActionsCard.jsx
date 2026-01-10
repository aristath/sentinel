import { Card, Group, Text, Badge, Progress, Stack, Paper, ActionIcon } from '@mantine/core';
import { IconRefresh, IconRotateClockwise } from '@tabler/icons-react';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { useSettingsStore } from '../../stores/settingsStore';
import { formatCurrency } from '../../utils/formatters';

export function NextActionsCard() {
  const {
    recommendations,
    plannerStatus,
    loading,
    fetchRecommendations,
    regenerateSequences,
  } = useAppStore();
  const { allocation } = usePortfolioStore();
  const { settings } = useSettingsStore();

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
        border: '1px solid var(--mantine-color-dark-6)',
        backgroundColor: 'var(--mantine-color-dark-7)',
      }}
    >
      <Group justify="space-between" mb="md">
        <div style={{ flex: 1 }}>
          <Text size="lg" fw={700} c="blue" tt="uppercase" mb="xs" style={{ fontFamily: 'var(--mantine-font-family)' }}>
            Next Actions
          </Text>
          <Text size="xs" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
            Automated portfolio management recommendations
          </Text>
        </div>
        <Group gap="md" visibleFrom="md">
          <div style={{ textAlign: 'right' }}>
            <Text size="xs" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>Total Value</Text>
            <Text size="sm" fw={600} c="green" style={{ fontFamily: 'var(--mantine-font-family)' }}>
              {formatCurrency(allocation.total_value)}
            </Text>
          </div>
          <div style={{ width: '1px', height: '32px', backgroundColor: 'var(--mantine-color-dark-6)' }} />
          <div style={{ textAlign: 'right' }}>
            <Text size="xs" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>Cash</Text>
            <Text size="sm" fw={600} c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
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
        <Paper p="md" mb="md" style={{ border: '1px solid var(--mantine-color-blue-0)', backgroundColor: 'var(--mantine-color-dark-7)' }}>
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
            {steps.map((step) => (
              <Paper
                key={`step-${step.step}`}
                p="md"
                style={{
                  border: '1px solid',
                  borderColor: step.is_emergency
                    ? 'var(--mantine-color-yellow-0)'
                    : step.side === 'SELL'
                    ? 'var(--mantine-color-red-0)'
                    : 'var(--mantine-color-green-0)',
                  backgroundColor: 'var(--mantine-color-dark-8)',
                }}
              >
                <Group justify="space-between" align="flex-start">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Group gap="xs" mb="xs" wrap="wrap">
                      <Badge size="sm" variant="filled" color="dark" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                        Step {step.step}
                      </Badge>
                      {step.is_emergency && (
                        <Badge size="sm" color="orange" variant="light" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                          🚨 EMERGENCY
                        </Badge>
                      )}
                      <Badge
                        size="sm"
                        color={step.side === 'SELL' ? 'red' : 'green'}
                        variant="light"
                        style={{ fontFamily: 'var(--mantine-font-family)' }}
                      >
                        {step.side}
                      </Badge>
                      <Text size="lg" fw={700} style={{ fontFamily: 'var(--mantine-font-family)' }} c={step.side === 'SELL' ? 'red' : 'green'}>
                        {step.symbol}
                      </Text>
                    </Group>
                    <Text size="md" fw={500} mb="xs" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                      {step.name}
                    </Text>
                    <Text
                      size="sm"
                      mb="xs"
                      c={step.is_emergency ? 'orange' : 'dimmed'}
                      fw={step.is_emergency ? 600 : 400}
                      style={{ fontFamily: 'var(--mantine-font-family)' }}
                    >
                      {step.reason}
                    </Text>
                    <Group gap="md" wrap="wrap">
                      <Text size="sm" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                        Score: {step.portfolio_score_before.toFixed(1)} → {step.portfolio_score_after.toFixed(1)}
                      </Text>
                      {step.score_change > 0 && (
                        <Badge size="sm" color="green" variant="light" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                          +{step.score_change.toFixed(1)}
                        </Badge>
                      )}
                      {step.score_change < 0 && (
                        <Badge size="sm" color="red" variant="light" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                          {step.score_change.toFixed(1)}
                        </Badge>
                      )}
                    </Group>
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <Text
                      size="lg"
                      fw={700}
                      style={{ fontFamily: 'var(--mantine-font-family)' }}
                      c={step.side === 'SELL' ? 'red' : 'green'}
                    >
                      {(step.side === 'SELL' ? '-' : '+')}€{step.estimated_value.toLocaleString()}
                    </Text>
                    <Text size="sm" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                      {step.quantity} @ €{step.estimated_price}
                    </Text>
                    <Text size="xs" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                      Cash: €{step.available_cash_before.toLocaleString()} → €{step.available_cash_after.toLocaleString()}
                    </Text>
                  </div>
                </Group>
              </Paper>
            ))}
          </Stack>

          {recommendations.final_available_cash && (
            <Text size="sm" c="dimmed" ta="center" mt="md" style={{ fontFamily: 'var(--mantine-font-family)' }}>
              Final cash: <Text span fw={600} c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                €{recommendations.final_available_cash.toLocaleString()}
              </Text>
            </Text>
          )}
        </Stack>
      )}

      {/* Rejected Opportunities */}
      {recommendations?.rejected_opportunities && recommendations.rejected_opportunities.length > 0 && (
        <details style={{ marginTop: '1rem', borderTop: '1px solid var(--mantine-color-dark-6)', paddingTop: '1rem' }}>
          <summary
            style={{
              cursor: 'pointer',
              padding: '0.5rem',
              fontSize: '0.875rem',
              color: 'var(--mantine-color-dimmed)',
              fontFamily: 'var(--mantine-font-family)',
              fontWeight: 500,
              listStyle: 'none',
            }}
          >
            <Text size="sm" c="dimmed" fw={500} style={{ fontFamily: 'var(--mantine-font-family)' }}>
              Rejected Opportunities ({recommendations.rejected_opportunities.length})
            </Text>
          </summary>
          <Stack gap="xs" mt="sm" style={{ paddingLeft: '1rem' }}>
            {recommendations.rejected_opportunities.map((rejected, index) => (
              <Paper
                key={`rejected-${rejected.symbol}-${rejected.side}-${index}`}
                p="sm"
                style={{
                  border: '1px solid var(--mantine-color-dark-6)',
                  backgroundColor: 'var(--mantine-color-dark-8)',
                }}
              >
                <Group gap="xs" mb="xs" wrap="wrap">
                  <Badge
                    size="sm"
                    color={rejected.side === 'SELL' ? 'red' : 'green'}
                    variant="light"
                    style={{ fontFamily: 'var(--mantine-font-family)' }}
                  >
                    {rejected.side}
                  </Badge>
                  <Text size="sm" fw={600} style={{ fontFamily: 'var(--mantine-font-family)' }} c="dimmed">
                    {rejected.symbol}
                  </Text>
                  {rejected.name && (
                    <Text size="sm" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                      - {rejected.name}
                    </Text>
                  )}
                </Group>
                {rejected.reasons && rejected.reasons.length > 0 && (
                  <Text size="xs" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)', lineHeight: 1.5 }}>
                    {rejected.reasons.join('; ')}
                  </Text>
                )}
              </Paper>
            ))}
          </Stack>
        </details>
      )}
    </Card>
  );
}
