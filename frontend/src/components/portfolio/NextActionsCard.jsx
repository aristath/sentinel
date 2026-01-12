import { Card, Group, Text, Badge, Progress, Stack, Paper, ActionIcon, Loader } from '@mantine/core';
import { IconRefresh, IconRotateClockwise, IconX, IconPlus } from '@tabler/icons-react';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { useSettingsStore } from '../../stores/settingsStore';
import { formatCurrency } from '../../utils/formatters';
import { api } from '../../api/client';

export function NextActionsCard() {
  const {
    recommendations,
    runningJobs,
    loading,
    fetchRecommendations,
    triggerPlannerBatch,
  } = useAppStore();
  const { allocation } = usePortfolioStore();
  const { settings } = useSettingsStore();

  // Find planner_batch job in running jobs
  const plannerJob = Object.values(runningJobs).find(j => j.jobType === 'planner_batch');
  const isPlanning = !!plannerJob;

  const handleTriggerPlanner = async () => {
    if (confirm('This will trigger a new planning job to regenerate recommendations. Continue?')) {
      await triggerPlannerBatch();
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
          <ActionIcon
            variant="subtle"
            onClick={handleTriggerPlanner}
            disabled={isPlanning}
            title="Trigger planning job"
          >
            <IconRotateClockwise size={18} />
          </ActionIcon>
        </Group>
      </Group>

      {/* Planner Job Status */}
      {isPlanning && (
        <Paper p="md" mb="md" style={{ border: '1px solid var(--mantine-color-blue-0)', backgroundColor: 'var(--mantine-color-dark-7)' }}>
          <Group gap="xs" mb="sm">
            <Loader size={14} color="blue" />
            <Text size="sm" fw={600} c="blue">
              {plannerJob.description || 'Planning...'}
            </Text>
          </Group>

          {plannerJob.progress && plannerJob.progress.total > 0 && (
            <div>
              <Progress
                value={(plannerJob.progress.current / plannerJob.progress.total) * 100}
                size="sm"
                mb="xs"
                color="blue"
              />
              <Text size="xs" c="dimmed" ta="center">
                Step {plannerJob.progress.current} of {plannerJob.progress.total}
                {plannerJob.progress.description && ` - ${plannerJob.progress.description}`}
              </Text>
            </div>
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
            {recommendations?.rejected_opportunities && recommendations.rejected_opportunities.length > 0
              ? 'All opportunities were filtered out'
              : recommendations?.pre_filtered_securities && recommendations.pre_filtered_securities.length > 0
              ? 'All securities were pre-filtered - expand details below'
              : 'Portfolio is optimally balanced'}
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

      {/* Rejected Opportunities - Always visible when present */}
      {recommendations?.rejected_opportunities && recommendations.rejected_opportunities.length > 0 && (
        <div style={{
          marginTop: hasRecommendations ? '1rem' : '0',
          borderTop: hasRecommendations ? '1px solid var(--mantine-color-dark-6)' : 'none',
          paddingTop: hasRecommendations ? '1rem' : '0'
        }}>
          <Text size="sm" c="dimmed" fw={500} mb="sm" style={{ fontFamily: 'var(--mantine-font-family)' }}>
            Rejected Opportunities ({recommendations.rejected_opportunities.length})
          </Text>
          <Stack gap="xs">
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
        </div>
      )}

      {/* Pre-Filtered Securities - Securities excluded before reaching opportunity stage */}
      {recommendations?.pre_filtered_securities && recommendations.pre_filtered_securities.length > 0 && (() => {
        // Group pre-filtered securities by symbol/ISIN
        const groupedBySymbol = recommendations.pre_filtered_securities.reduce((acc, filtered) => {
          const key = filtered.symbol || filtered.isin;
          if (!acc[key]) {
            acc[key] = {
              symbol: filtered.symbol,
              isin: filtered.isin,
              name: filtered.name,
              reasons: [] // Array of { calculator, reasons }
            };
          }
          // Add calculator and its reasons
          acc[key].reasons.push({
            calculator: filtered.calculator,
            reasons: filtered.reasons || []
          });
          return acc;
        }, {});

        const groupedSecurities = Object.values(groupedBySymbol);

        return (
          <div style={{
            marginTop: (hasRecommendations || recommendations?.rejected_opportunities?.length > 0) ? '1rem' : '0',
            borderTop: (hasRecommendations || recommendations?.rejected_opportunities?.length > 0) ? '1px solid var(--mantine-color-dark-6)' : 'none',
            paddingTop: (hasRecommendations || recommendations?.rejected_opportunities?.length > 0) ? '1rem' : '0'
          }}>
            <Text size="sm" c="dimmed" fw={500} mb="sm" style={{ fontFamily: 'var(--mantine-font-family)' }}>
              Pre-Filtered Securities ({groupedSecurities.length} securities)
            </Text>
            <Text size="xs" c="dimmed" mb="sm" style={{ fontFamily: 'var(--mantine-font-family)', fontStyle: 'italic' }}>
              Securities excluded before reaching the opportunity identification stage
            </Text>
            <Stack gap="xs">
              {groupedSecurities.map((security) => (
                <Paper
                  key={`filtered-${security.isin}`}
                  p="sm"
                  style={{
                    border: '1px solid var(--mantine-color-dark-5)',
                    backgroundColor: 'var(--mantine-color-dark-8)',
                  }}
                >
                  <Group gap="xs" mb="xs" wrap="wrap">
                    <Text size="sm" fw={600} style={{ fontFamily: 'var(--mantine-font-family)' }} c="dimmed">
                      {security.symbol || security.isin}
                    </Text>
                    {security.name && (
                      <Text size="sm" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                        - {security.name}
                      </Text>
                    )}
                  </Group>
                  <Stack gap={4}>
                    {security.reasons.map((entry, entryIndex) => (
                      entry.reasons.map((reasonObj, reasonIndex) => {
                        // Handle both old format (string) and new format (object with reason & dismissed)
                        const reasonText = typeof reasonObj === 'string' ? reasonObj : reasonObj.reason;
                        const isDismissed = typeof reasonObj === 'object' && reasonObj.dismissed;

                        const handleToggleDismiss = async () => {
                          try {
                            if (isDismissed) {
                              await api.undismissFilter(security.isin, entry.calculator, reasonText);
                            } else {
                              await api.dismissFilter(security.isin, entry.calculator, reasonText);
                            }
                            // Refresh recommendations to update the UI
                            fetchRecommendations();
                          } catch (error) {
                            console.error('Failed to toggle dismiss:', error);
                          }
                        };

                        return (
                          <Group key={`${entryIndex}-${reasonIndex}`} gap="xs" wrap="nowrap">
                            <Text
                              size="xs"
                              c="dimmed"
                              td={isDismissed ? 'line-through' : undefined}
                              style={{ fontFamily: 'var(--mantine-font-family)', lineHeight: 1.4, flex: 1 }}
                            >
                              • <Text span size="xs" c="gray.5" style={{ fontFamily: 'var(--mantine-font-family)' }}>{entry.calculator}</Text> {reasonText}
                            </Text>
                            <ActionIcon
                              size="xs"
                              variant="subtle"
                              color={isDismissed ? 'green' : 'red'}
                              onClick={handleToggleDismiss}
                              title={isDismissed ? 'Re-enable this filter' : 'Dismiss this filter'}
                            >
                              {isDismissed ? <IconPlus size={12} /> : <IconX size={12} />}
                            </ActionIcon>
                          </Group>
                        );
                      })
                    ))}
                  </Stack>
                </Paper>
              ))}
            </Stack>
          </div>
        );
      })()}
    </Card>
  );
}
